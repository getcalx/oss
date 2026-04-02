"""SQLite implementation of the database engine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

from calx.serve.db.engine import (
    BoardStateRow, CompilationEventRow, ContextRow,
    CorrectionRow, DecisionRow, FoilReviewRow,
    HandoffRow, MetricRow, PipelineRow, PlanRow, RuleRow, SessionRow,
)
from calx.serve.db.schema import PRAGMA_WAL, SCHEMA_VERSION


class SQLiteEngine:
    """Async SQLite backend for calx serve."""

    def __init__(self, db_path: str | Path = ":memory:"):
        self._db_path = str(db_path)
        self._conn: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        cursor = await self._conn.execute(PRAGMA_WAL)
        await cursor.close()
        cursor = await self._conn.execute("PRAGMA busy_timeout=5000")
        await cursor.close()
        cursor = await self._conn.execute("PRAGMA foreign_keys=ON")
        await cursor.close()

        backup_path = None
        fresh = await self._is_fresh_db()

        if fresh:
            from calx.serve.db.migrate import run_sql_migrations
            await run_sql_migrations(self)
        else:
            db_version = await self.get_schema_version()
            if db_version > SCHEMA_VERSION:
                await self.close()
                raise SystemExit(
                    f"This database was created by a newer version of calx "
                    f"(schema v{db_version}). You are running schema "
                    f"v{SCHEMA_VERSION}. Please upgrade: "
                    f"pip install --upgrade getcalx"
                )
            if db_version < SCHEMA_VERSION:
                from calx.serve.db.migrate import run_sql_migrations
                backup_path = await run_sql_migrations(self)

        await self.validate_schema(backup_path=backup_path)

    async def _is_fresh_db(self) -> bool:
        """Check if this is a fresh database (no schema_version table)."""
        row = await self._fetchone(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='schema_version'"
        )
        return row is None

    async def validate_schema(self, backup_path: str | None = None) -> None:
        """Validate live schema against dataclass expectations."""
        import dataclasses
        from calx.serve.db.schema import (
            PYTHON_TO_SQLITE_TYPE, _get_dataclass_table_map,
        )

        table_map = _get_dataclass_table_map()
        errors = []

        for dc_class, table_name in table_map.items():
            rows = await self._fetchall(
                f"PRAGMA table_info({table_name})"
            )
            db_columns = {}
            for row in rows:
                db_columns[row[1]] = {
                    "type": row[2].upper() if row[2] else "",
                    "notnull": bool(row[3]),
                    "pk": bool(row[5]),
                }

            for field in dataclasses.fields(dc_class):
                col_name = field.name
                if col_name not in db_columns:
                    errors.append(
                        f"Table '{table_name}': missing column '{col_name}'"
                    )
                    continue

                expected_type = PYTHON_TO_SQLITE_TYPE.get(field.type)
                if expected_type is None:
                    errors.append(
                        f"Table '{table_name}': column '{col_name}': "
                        f"unmapped Python type '{field.type}'"
                    )
                    continue

                if db_columns[col_name]["type"] != expected_type:
                    errors.append(
                        f"Table '{table_name}': column '{col_name}': "
                        f"expected type {expected_type}, "
                        f"found {db_columns[col_name]['type']}"
                    )

                if not db_columns[col_name]["pk"]:
                    expect_notnull = "| None" not in field.type
                    actual_notnull = db_columns[col_name]["notnull"]
                    if expect_notnull != actual_notnull:
                        errors.append(
                            f"Table '{table_name}': column '{col_name}': "
                            f"expected {'NOT NULL' if expect_notnull else 'nullable'}, "
                            f"found {'NOT NULL' if actual_notnull else 'nullable'}"
                        )

        if errors:
            db_version = await self.get_schema_version()
            error_msg = (
                f"Schema mismatch (DB at version {db_version}, "
                f"code expects version {SCHEMA_VERSION}):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )
            if backup_path:
                error_msg += f"\nBackup available at: {backup_path}"
            error_msg += (
                "\nPlease report this at github.com/getcalx/calx/issues"
            )
            raise SystemExit(error_msg)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        assert self._conn is not None
        cursor = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cursor

    async def _fetchone(self, sql: str, params: tuple = ()) -> Any:
        assert self._conn is not None
        cursor = await self._conn.execute(sql, params)
        result = await cursor.fetchone()
        await cursor.close()
        return result

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[Any]:
        assert self._conn is not None
        cursor = await self._conn.execute(sql, params)
        result = await cursor.fetchall()
        await cursor.close()
        return result

    # ------------------------------------------------------------------
    # Corrections
    # ------------------------------------------------------------------

    async def insert_correction(self, c: CorrectionRow) -> str:
        await self._execute(
            """INSERT INTO corrections
               (id, uuid, correction, domain, category, severity, confidence,
                surface, task_context, briefing_state, keywords,
                recurrence_of, root_correction_id, recurrence_count,
                promoted, quarantined, quarantine_reason, learning_mode)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (c.id, c.uuid, c.correction, c.domain, c.category, c.severity,
             c.confidence, c.surface, c.task_context, c.briefing_state,
             c.keywords, c.recurrence_of, c.root_correction_id,
             c.recurrence_count, c.promoted, c.quarantined, c.quarantine_reason,
             c.learning_mode),
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
        if not keywords:
            return []
        conditions = ["quarantined = 0"]
        params: list[Any] = []
        if domain:
            conditions.append("domain = ?")
            params.append(domain)
        keyword_conditions = []
        for kw in keywords:
            keyword_conditions.append("keywords LIKE ?")
            params.append(f"%{kw}%")
        conditions.append(f"({' OR '.join(keyword_conditions)})")
        params.append(limit)
        where = " AND ".join(conditions)
        rows = await self._fetchall(
            f"SELECT * FROM corrections WHERE {where} LIMIT ?",
            tuple(params),
        )
        return [self._row_to_correction(r) for r in rows]

    async def update_correction(self, correction_id: str, **fields: object) -> None:
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = tuple(fields.values()) + (correction_id,)
        await self._execute(
            f"UPDATE corrections SET {set_clause} WHERE id = ?", values
        )

    async def increment_recurrence_count(self, correction_id: str) -> int:
        await self._execute(
            "UPDATE corrections SET recurrence_count = recurrence_count + 1 WHERE id = ?",
            (correction_id,),
        )
        row = await self._fetchone(
            "SELECT recurrence_count FROM corrections WHERE id = ?",
            (correction_id,),
        )
        return row["recurrence_count"] if row else 0

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
            learning_mode=row["learning_mode"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------

    async def insert_rule(self, r: RuleRow) -> str:
        await self._execute(
            """INSERT INTO rules
               (id, rule_text, domain, surface, source_correction_id,
                learning_mode, health_score, health_status,
                last_validated_at, compiled_at, compiled_via,
                compiled_from_mode, recurrence_at_compilation, role, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r.id, r.rule_text, r.domain, r.surface,
             r.source_correction_id, r.learning_mode, r.health_score,
             r.health_status, r.last_validated_at, r.compiled_at,
             r.compiled_via, r.compiled_from_mode,
             r.recurrence_at_compilation, r.role, r.active),
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
            current_id = row["id"]
            num_part = current_id.rsplit("-R", 1)[-1]
            next_num = int(num_part) + 1
            return f"{domain}-R{next_num:03d}"
        return f"{domain}-R001"

    async def update_rule(self, rule_id: str, **fields: object) -> None:
        if not fields:
            return
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
            learning_mode=row["learning_mode"],
            health_score=row["health_score"],
            health_status=row["health_status"],
            last_validated_at=row["last_validated_at"],
            compiled_at=row["compiled_at"],
            compiled_via=row["compiled_via"],
            compiled_from_mode=row["compiled_from_mode"],
            recurrence_at_compilation=row["recurrence_at_compilation"],
            deactivation_reason=row["deactivation_reason"],
            role=row["role"],
            active=row["active"], created_at=row["created_at"],
            updated_at=row["updated_at"],
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
                "SELECT * FROM metrics WHERE name = ? ORDER BY id DESC LIMIT 1",
                (name,),
            )
        else:
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
        try:
            await self._execute(
                """INSERT INTO telemetry
                   (event_type, tool_or_resource, surface, params,
                    response_status, latency_ms)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event_type, tool_or_resource, surface, params_json,
                 response_status, latency_ms),
            )
        except Exception:
            pass  # Fire-and-forget

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    async def insert_session(self, s: SessionRow) -> str:
        await self._execute(
            """INSERT INTO sessions
               (id, surface, surface_type, oriented, token_estimate,
                soft_cap, ceiling, tool_call_count,
                server_fail_mode, collapse_fail_mode, started_at, ended_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (s.id, s.surface, s.surface_type, s.oriented, s.token_estimate,
             s.soft_cap, s.ceiling, s.tool_call_count,
             s.server_fail_mode, s.collapse_fail_mode, s.started_at, s.ended_at),
        )
        return s.id

    async def get_session(self, session_id: str) -> SessionRow | None:
        row = await self._fetchone(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        return self._row_to_session(row) if row else None

    async def update_session(self, session_id: str, **fields: object) -> None:
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = tuple(fields.values()) + (session_id,)
        await self._execute(
            f"UPDATE sessions SET {set_clause} WHERE id = ?", values
        )

    async def get_active_session(self) -> SessionRow | None:
        row = await self._fetchone(
            "SELECT * FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
        )
        return self._row_to_session(row) if row else None

    @staticmethod
    def _row_to_session(row) -> SessionRow:
        return SessionRow(
            id=row["id"], surface=row["surface"],
            surface_type=row["surface_type"], oriented=row["oriented"],
            token_estimate=row["token_estimate"], soft_cap=row["soft_cap"],
            ceiling=row["ceiling"], tool_call_count=row["tool_call_count"],
            server_fail_mode=row["server_fail_mode"],
            collapse_fail_mode=row["collapse_fail_mode"],
            started_at=row["started_at"], ended_at=row["ended_at"],
        )

    # ------------------------------------------------------------------
    # Handoffs
    # ------------------------------------------------------------------

    async def insert_handoff(self, h: HandoffRow) -> int:
        cursor = await self._execute(
            """INSERT INTO handoffs
               (session_id, what_changed, what_others_need,
                decisions_deferred, next_priorities, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (h.session_id, h.what_changed, h.what_others_need,
             h.decisions_deferred, h.next_priorities, h.created_at),
        )
        return cursor.lastrowid or 0

    async def get_latest_handoff(
        self, session_id: str | None = None,
    ) -> HandoffRow | None:
        if session_id:
            row = await self._fetchone(
                "SELECT * FROM handoffs WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            )
        else:
            row = await self._fetchone(
                "SELECT * FROM handoffs ORDER BY created_at DESC LIMIT 1"
            )
        if not row:
            return None
        return HandoffRow(
            id=row["id"], session_id=row["session_id"],
            what_changed=row["what_changed"],
            what_others_need=row["what_others_need"],
            decisions_deferred=row["decisions_deferred"],
            next_priorities=row["next_priorities"],
            created_at=row["created_at"],
        )

    # ------------------------------------------------------------------
    # Board state
    # ------------------------------------------------------------------

    async def insert_board_item(self, item: BoardStateRow) -> int:
        cursor = await self._execute(
            """INSERT INTO board_state
               (domain, description, status, blocked_reason, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (item.domain, item.description, item.status,
             item.blocked_reason, item.updated_at),
        )
        return cursor.lastrowid or 0

    async def get_board_state(
        self, status: str | None = None,
    ) -> list[BoardStateRow]:
        if status:
            rows = await self._fetchall(
                "SELECT * FROM board_state WHERE status = ? ORDER BY updated_at DESC",
                (status,),
            )
        else:
            rows = await self._fetchall(
                "SELECT * FROM board_state ORDER BY updated_at DESC"
            )
        return [
            BoardStateRow(
                id=r["id"], domain=r["domain"],
                description=r["description"], status=r["status"],
                blocked_reason=r["blocked_reason"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    async def update_board_item(self, item_id: int, **fields: object) -> None:
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = tuple(fields.values()) + (item_id,)
        await self._execute(
            f"UPDATE board_state SET {set_clause} WHERE id = ?", values
        )

    # ------------------------------------------------------------------
    # Foil reviews
    # ------------------------------------------------------------------

    async def insert_foil_review(self, review: FoilReviewRow) -> int:
        cursor = await self._execute(
            """INSERT INTO foil_reviews
               (spec_reference, reviewer_domain, verdict, findings,
                round, session_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (review.spec_reference, review.reviewer_domain, review.verdict,
             review.findings, review.round, review.session_id,
             review.created_at),
        )
        return cursor.lastrowid or 0

    async def get_foil_reviews(
        self, spec_reference: str | None = None,
    ) -> list[FoilReviewRow]:
        if spec_reference:
            rows = await self._fetchall(
                "SELECT * FROM foil_reviews WHERE spec_reference = ? ORDER BY created_at DESC",
                (spec_reference,),
            )
        else:
            rows = await self._fetchall(
                "SELECT * FROM foil_reviews ORDER BY created_at DESC"
            )
        return [
            FoilReviewRow(
                id=r["id"], spec_reference=r["spec_reference"],
                reviewer_domain=r["reviewer_domain"], verdict=r["verdict"],
                findings=r["findings"], round=r["round"],
                session_id=r["session_id"], created_at=r["created_at"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Compilation events
    # ------------------------------------------------------------------

    async def insert_compilation_event(self, event: CompilationEventRow) -> int:
        cursor = await self._execute(
            """INSERT INTO compilation_events
               (rule_id, source_correction_id, rule_text, learning_mode_before,
                mechanism_type, mechanism_description, mechanism_reference,
                recurrence_count_at_compilation, rule_age_days,
                correction_chain_length, post_compilation_recurrence,
                verified_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event.rule_id, event.source_correction_id, event.rule_text,
             event.learning_mode_before, event.mechanism_type,
             event.mechanism_description, event.mechanism_reference,
             event.recurrence_count_at_compilation, event.rule_age_days,
             event.correction_chain_length, event.post_compilation_recurrence,
             event.verified_at, event.created_at),
        )
        return cursor.lastrowid or 0

    async def get_compilation_events(
        self, rule_id: str | None = None,
    ) -> list[CompilationEventRow]:
        if rule_id:
            rows = await self._fetchall(
                "SELECT * FROM compilation_events WHERE rule_id = ? ORDER BY created_at DESC",
                (rule_id,),
            )
        else:
            rows = await self._fetchall(
                "SELECT * FROM compilation_events ORDER BY created_at DESC"
            )
        return [self._row_to_compilation_event(r) for r in rows]

    async def update_compilation_event(
        self, event_id: int, **fields: object,
    ) -> None:
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = tuple(fields.values()) + (event_id,)
        await self._execute(
            f"UPDATE compilation_events SET {set_clause} WHERE id = ?", values
        )

    @staticmethod
    def _row_to_compilation_event(row) -> CompilationEventRow:
        return CompilationEventRow(
            id=row["id"], rule_id=row["rule_id"],
            source_correction_id=row["source_correction_id"],
            rule_text=row["rule_text"],
            learning_mode_before=row["learning_mode_before"],
            mechanism_type=row["mechanism_type"],
            mechanism_description=row["mechanism_description"],
            mechanism_reference=row["mechanism_reference"],
            recurrence_count_at_compilation=row["recurrence_count_at_compilation"],
            rule_age_days=row["rule_age_days"],
            correction_chain_length=row["correction_chain_length"],
            post_compilation_recurrence=row["post_compilation_recurrence"],
            verified_at=row["verified_at"],
            created_at=row["created_at"],
        )

    # ------------------------------------------------------------------
    # Plans
    # ------------------------------------------------------------------

    async def insert_plan(self, plan: PlanRow) -> int:
        cursor = await self._execute(
            """INSERT INTO plans
               (task_description, chunks, dependency_edges, phase,
                spec_file, test_files, review_id, current_wave,
                wave_verification, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (plan.task_description, plan.chunks, plan.dependency_edges,
             plan.phase, plan.spec_file, plan.test_files, plan.review_id,
             plan.current_wave, plan.wave_verification, plan.status),
        )
        return cursor.lastrowid or 0

    async def get_plan(self, plan_id: int) -> PlanRow | None:
        row = await self._fetchone(
            "SELECT * FROM plans WHERE id = ?", (plan_id,)
        )
        return self._row_to_plan(row) if row else None

    async def get_active_plan(self) -> PlanRow | None:
        row = await self._fetchone(
            "SELECT * FROM plans WHERE status = 'active' ORDER BY id DESC LIMIT 1"
        )
        return self._row_to_plan(row) if row else None

    async def update_plan(self, plan_id: int, **fields: object) -> None:
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = tuple(fields.values()) + (plan_id,)
        await self._execute(
            f"UPDATE plans SET {set_clause} WHERE id = ?", values
        )

    @staticmethod
    def _row_to_plan(row: Any) -> PlanRow:
        return PlanRow(
            id=row["id"],
            task_description=row["task_description"],
            chunks=row["chunks"],
            dependency_edges=row["dependency_edges"],
            phase=row["phase"],
            spec_file=row["spec_file"],
            test_files=row["test_files"],
            review_id=row["review_id"],
            current_wave=row["current_wave"],
            wave_verification=row["wave_verification"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
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
