"""SQLite implementation of the database engine."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any

import aiosqlite

from calx.serve.db.engine import (
    ContextRow,
    CorrectionRow,
    DecisionRow,
    MetricRow,
    PipelineRow,
    RuleRow,
)
from calx.serve.db.schema import PRAGMA_WAL, SCHEMA_VERSION, TABLES_DDL

BUSY_RETRIES = 3
BUSY_DELAYS = [0.05, 0.1, 0.2]  # 50ms, 100ms, 200ms

_CORRECTION_FIELDS = {f.name for f in dataclass_fields(CorrectionRow)}
_RULE_FIELDS = {f.name for f in dataclass_fields(RuleRow)}


class SQLiteEngine:
    """Async SQLite backend for calx serve."""

    def __init__(self, db_path: str | Path = ":memory:"):
        self._db_path = str(db_path)
        self._conn: aiosqlite.Connection | None = None
        self._in_transaction: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute(PRAGMA_WAL)
        await self._conn.executescript(TABLES_DDL)
        # Record schema version if fresh
        version = await self.get_schema_version()
        if version == 0:
            await self.set_schema_version(SCHEMA_VERSION)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @asynccontextmanager
    async def transaction(self):
        """Transaction context manager. Commits on success, rolls back on failure."""
        assert self._conn is not None
        await self._conn.execute("BEGIN IMMEDIATE")
        self._in_transaction = True
        try:
            yield
            await self._conn.commit()
        except Exception:
            await self._conn.rollback()
            raise
        finally:
            self._in_transaction = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _execute_with_retry(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute SQL with retry on SQLITE_BUSY (database is locked)."""
        assert self._conn is not None
        for attempt in range(BUSY_RETRIES + 1):
            try:
                cursor = await self._conn.execute(sql, params)
                return cursor
            except Exception as e:
                if "database is locked" in str(e) and attempt < BUSY_RETRIES:
                    await asyncio.sleep(BUSY_DELAYS[attempt])
                    continue
                raise

    async def _execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        assert self._conn is not None
        cursor = await self._execute_with_retry(sql, params)
        if not self._in_transaction:
            await self._conn.commit()
        return cursor

    async def _fetchone(self, sql: str, params: tuple = ()) -> Any:
        assert self._conn is not None
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchone()

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[Any]:
        assert self._conn is not None
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchall()

    # ------------------------------------------------------------------
    # Corrections
    # ------------------------------------------------------------------

    async def insert_correction(self, c: CorrectionRow) -> str:
        await self._execute(
            """INSERT INTO corrections
               (id, uuid, correction, domain, category, severity, confidence,
                surface, task_context, briefing_state, keywords,
                recurrence_of, root_correction_id, recurrence_count,
                promoted, quarantined, quarantine_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (c.id, c.uuid, c.correction, c.domain, c.category, c.severity,
             c.confidence, c.surface, c.task_context, c.briefing_state,
             c.keywords, c.recurrence_of, c.root_correction_id,
             c.recurrence_count, c.promoted, c.quarantined, c.quarantine_reason),
        )
        return c.id

    async def get_correction(self, correction_id: str) -> CorrectionRow | None:
        row = await self._fetchone(
            "SELECT * FROM corrections WHERE id = ?", (correction_id,)
        )
        return self._row_to_correction(row) if row else None

    async def correction_exists(self, uuid: str) -> bool:
        row = await self._fetchone(
            "SELECT 1 FROM corrections WHERE uuid = ?", (uuid,)
        )
        return row is not None

    async def max_correction_num(self) -> int:
        """Return the highest numeric suffix from all correction IDs (including quarantined)."""
        row = await self._fetchone(
            "SELECT MAX(CAST(SUBSTR(id, 2) AS INTEGER)) as max_num FROM corrections",
        )
        return int(row["max_num"]) if row and row["max_num"] is not None else 0

    async def find_corrections(
        self, domain: str | None = None, limit: int = 100,
    ) -> list[CorrectionRow]:
        if domain:
            rows = await self._fetchall(
                """SELECT * FROM corrections
                   WHERE domain = ? AND quarantined = 0
                   ORDER BY created_at DESC LIMIT ?""",
                (domain, limit),
            )
        else:
            rows = await self._fetchall(
                """SELECT * FROM corrections
                   WHERE quarantined = 0
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            )
        return [self._row_to_correction(r) for r in rows]

    async def find_corrections_by_keywords(
        self, keywords: list[str], domain: str | None = None, limit: int = 200,
    ) -> list[CorrectionRow]:
        """Find corrections matching any of the given keywords."""
        if not keywords:
            return await self.find_corrections(domain=domain, limit=limit)

        conditions: list[str] = ["quarantined = 0"]
        params: list[object] = []

        keyword_clauses = []
        for kw in keywords[:5]:  # cap at top 5 keywords
            keyword_clauses.append("keywords LIKE ?")
            params.append(f"%{kw}%")
        conditions.append(f"({' OR '.join(keyword_clauses)})")

        if domain:
            conditions.append("domain = ?")
            params.append(domain)

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM corrections WHERE {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = await self._fetchall(sql, tuple(params))
        return [self._row_to_correction(r) for r in rows]

    async def increment_recurrence_count(self, correction_id: str) -> int:
        """Atomically increment recurrence_count. Returns new count."""
        assert self._conn is not None
        await self._execute_with_retry(
            "UPDATE corrections SET recurrence_count = recurrence_count + 1 WHERE id = ?",
            (correction_id,),
        )
        if not self._in_transaction:
            await self._conn.commit()
        cursor = await self._conn.execute(
            "SELECT recurrence_count FROM corrections WHERE id = ?",
            (correction_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def update_correction(self, correction_id: str, **fields: object) -> None:
        if not fields:
            return
        invalid = set(fields.keys()) - _CORRECTION_FIELDS
        if invalid:
            raise ValueError(f"Invalid fields for correction: {invalid}")
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = tuple(fields.values()) + (correction_id,)
        await self._execute(
            f"UPDATE corrections SET {set_clause} WHERE id = ?", values
        )

    @staticmethod
    def _row_to_correction(row: Any) -> CorrectionRow:
        return CorrectionRow(
            id=row["id"], uuid=row["uuid"], correction=row["correction"],
            domain=row["domain"], category=row["category"],
            severity=row["severity"], confidence=row["confidence"],
            surface=row["surface"], task_context=row["task_context"],
            briefing_state=row["briefing_state"], keywords=row["keywords"],
            recurrence_of=row["recurrence_of"],
            root_correction_id=row["root_correction_id"],
            recurrence_count=row["recurrence_count"],
            promoted=row["promoted"], quarantined=row["quarantined"],
            quarantine_reason=row["quarantine_reason"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------

    async def insert_rule(self, r: RuleRow) -> str:
        await self._execute(
            """INSERT INTO rules
               (id, rule_text, domain, surface, source_correction_id, active, health_score)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (r.id, r.rule_text, r.domain, r.surface,
             r.source_correction_id, r.active, r.health_score),
        )
        return r.id

    async def get_rule(self, rule_id: str) -> RuleRow | None:
        row = await self._fetchone("SELECT * FROM rules WHERE id = ?", (rule_id,))
        return self._row_to_rule(row) if row else None

    async def rule_exists(self, rule_id: str) -> bool:
        row = await self._fetchone("SELECT 1 FROM rules WHERE id = ?", (rule_id,))
        return row is not None

    async def find_rules(
        self, domain: str | None = None, active_only: bool = True,
    ) -> list[RuleRow]:
        conditions = []
        params: list[Any] = []
        if domain:
            conditions.append("domain = ?")
            params.append(domain)
        if active_only:
            conditions.append("active = 1")
        where = " AND ".join(conditions) if conditions else "1=1"
        rows = await self._fetchall(
            f"SELECT * FROM rules WHERE {where} ORDER BY created_at", tuple(params)
        )
        return [self._row_to_rule(r) for r in rows]

    async def next_rule_id(self, domain: str) -> str:
        row = await self._fetchone(
            "SELECT id FROM rules WHERE domain = ? ORDER BY id DESC LIMIT 1",
            (domain,),
        )
        if row:
            # Parse "domain-R003" -> 3, return "domain-R004"
            current_id = row["id"]
            num_part = current_id.rsplit("-R", 1)[-1]
            next_num = int(num_part) + 1
            return f"{domain}-R{next_num:03d}"
        return f"{domain}-R001"

    async def update_rule(self, rule_id: str, **fields: object) -> None:
        if not fields:
            return
        invalid = set(fields.keys()) - _RULE_FIELDS
        if invalid:
            raise ValueError(f"Invalid fields for rule: {invalid}")
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = tuple(fields.values()) + (rule_id,)
        await self._execute(
            f"UPDATE rules SET {set_clause} WHERE id = ?", values
        )

    @staticmethod
    def _row_to_rule(row: Any) -> RuleRow:
        return RuleRow(
            id=row["id"], rule_text=row["rule_text"], domain=row["domain"],
            surface=row["surface"], source_correction_id=row["source_correction_id"],
            active=row["active"], health_score=row["health_score"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    async def insert_metric(
        self, name: str, value: float,
        source: str | None = None, metadata: dict | None = None,
    ) -> int:
        meta_json = json.dumps(metadata) if metadata else None
        cursor = await self._execute(
            "INSERT INTO metrics (name, value, source, metadata) VALUES (?, ?, ?, ?)",
            (name, value, source, meta_json),
        )
        return cursor.lastrowid or 0

    async def get_latest_metrics(self, name: str | None = None) -> list[MetricRow]:
        if name:
            rows = await self._fetchall(
                """SELECT * FROM metrics WHERE name = ?
                   ORDER BY id DESC LIMIT 1""",
                (name,),
            )
        else:
            # Latest value per metric name (by rowid, not timestamp -- timestamps can collide)
            rows = await self._fetchall(
                """SELECT m.* FROM metrics m
                   INNER JOIN (
                       SELECT name, MAX(id) as max_id
                       FROM metrics GROUP BY name
                   ) latest ON m.id = latest.max_id
                   ORDER BY m.name"""
            )
        return [
            MetricRow(
                id=r["id"], name=r["name"], value=r["value"],
                source=r["source"], metadata=r["metadata"],
                measured_at=r["measured_at"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    async def upsert_pipeline(
        self, investor: str,
        status: str | None = None, gate: str | None = None, notes: str | None = None,
    ) -> None:
        existing = await self._fetchone(
            "SELECT * FROM pipeline WHERE investor = ?", (investor,)
        )
        if existing:
            updates = {}
            if status is not None:
                updates["status"] = status
            if gate is not None:
                updates["gate"] = gate
            if notes is not None:
                updates["notes"] = notes
            if updates:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                set_clause += ", updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
                values = tuple(updates.values()) + (investor,)
                await self._execute(
                    f"UPDATE pipeline SET {set_clause} WHERE investor = ?", values
                )
        else:
            await self._execute(
                "INSERT INTO pipeline (investor, status, gate, notes) VALUES (?, ?, ?, ?)",
                (investor, status, gate, notes),
            )

    async def get_pipeline(self, investor: str | None = None) -> list[PipelineRow]:
        if investor:
            rows = await self._fetchall(
                "SELECT * FROM pipeline WHERE investor = ?", (investor,),
            )
        else:
            rows = await self._fetchall(
                "SELECT * FROM pipeline ORDER BY updated_at DESC"
            )
        return [
            PipelineRow(
                investor=r["investor"], status=r["status"],
                gate=r["gate"], notes=r["notes"], updated_at=r["updated_at"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    async def insert_decision(
        self, decision: str, context: str | None = None, surface: str | None = None,
    ) -> int:
        cursor = await self._execute(
            "INSERT INTO decisions (decision, context, surface) VALUES (?, ?, ?)",
            (decision, context, surface),
        )
        return cursor.lastrowid or 0

    async def get_decisions(self, since: str | None = None) -> list[DecisionRow]:
        if since:
            rows = await self._fetchall(
                "SELECT * FROM decisions WHERE created_at >= ? ORDER BY created_at DESC",
                (since,),
            )
        else:
            rows = await self._fetchall(
                "SELECT * FROM decisions ORDER BY created_at DESC"
            )
        return [
            DecisionRow(
                id=r["id"], decision=r["decision"], context=r["context"],
                surface=r["surface"], created_at=r["created_at"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    async def set_context(
        self, key: str, value: str, category: str | None = None,
    ) -> None:
        await self._execute(
            """INSERT INTO context (key, value, category)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   category = COALESCE(excluded.category, context.category),
                   updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')""",
            (key, value, category),
        )

    async def get_context(self, category: str | None = None) -> list[ContextRow]:
        if category:
            rows = await self._fetchall(
                "SELECT * FROM context WHERE category = ? ORDER BY key",
                (category,),
            )
        else:
            rows = await self._fetchall("SELECT * FROM context ORDER BY key")
        return [
            ContextRow(
                key=r["key"], value=r["value"],
                category=r["category"], updated_at=r["updated_at"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    async def log_telemetry(
        self, event_type: str, tool_or_resource: str,
        surface: str | None = None, params: dict | None = None,
        response_status: str | None = None, latency_ms: float | None = None,
    ) -> None:
        params_json = json.dumps(params) if params else None
        import contextlib

        with contextlib.suppress(Exception):
            await self._execute(
                """INSERT INTO telemetry
                   (event_type, tool_or_resource, surface, params,
                    response_status, latency_ms)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event_type, tool_or_resource, surface, params_json,
                 response_status, latency_ms),
            )

    # ------------------------------------------------------------------
    # Schema version
    # ------------------------------------------------------------------

    async def get_schema_version(self) -> int:
        try:
            row = await self._fetchone(
                "SELECT MAX(version) as v FROM schema_version"
            )
            return row["v"] if row and row["v"] is not None else 0
        except Exception:
            return 0

    async def set_schema_version(self, version: int) -> None:
        await self._execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
            (version,),
        )
