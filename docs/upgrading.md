# Upgrading

How Calx handles version upgrades, schema migrations, and data safety.

---

## Upgrade process

```bash
pip install --upgrade getcalx
```

The next time `calx serve` starts, it checks the database schema version against the version expected by the code. If the schema is behind, migrations run automatically before the server accepts connections.

No manual migration step. No downtime commands. Upgrade the package, start the server, done.

---

## Schema migration guarantees

Three invariants hold across all upgrades:

1. **Automatic migration.** Schema changes apply on startup. You never run a separate migration command.
2. **Backup before migration.** Before any schema change, Calx copies the current database to `.calx/calx.db.backup.v{N}` where `{N}` is the pre-migration schema version. If something goes wrong, your previous state is intact.
3. **Version check.** If the database schema version is newer than what the installed code expects, the server refuses to start. This prevents data corruption from running old code against a newer schema. Upgrade the package to match.

---

## What migrations do

Migrations add new tables and columns. They do not modify or delete existing data.

Your corrections, rules, recurrence chains, and quarantine records are preserved across every upgrade. The append-only event log is never rewritten.

---

## Changes in v0.7.0

v0.7.0 removes the compilation engine, learning mode classifier, and `compile_rule` MCP tool from the OSS package. The `calx compilations` CLI command is also removed. Compilation is now proprietary (available in Calx Pro).

No migration needed. The compilation-related tables remain in the schema but are unused by the OSS package. No data is deleted.

---

## Breaking changes in v0.6.0

v0.6.0 introduces schema v6 with significant structural changes:

**Schema v6** adds tables for compilation tracking, session management, board state, plan orchestration, and foil reviews. Existing tables gain new columns but no existing columns are removed or renamed.

**Enforcement layer.** `enforce.py` replaces the previous `orientation_gate.py` and `collapse_guard.py` hooks. The two separate PreToolUse gates are consolidated into a single enforcement gate that handles orientation checks, token counting, and collapse prevention in one pass.

After upgrading, `calx init` will update your `.claude/settings.json` to point to the new hook. The old hook files remain in `.calx/hooks/` but are no longer referenced.

**Hook restructuring:**

| Before (v0.5.x) | After (v0.6.0) |
|---|---|
| `orientation-gate.sh` | Removed (merged into enforce) |
| `collapse-guard.sh` | Removed (merged into enforce) |
| `session-start.sh` | Updated (registers with enforcement server) |
| `session-end.sh` | Updated (ends session, writes handoff, sends telemetry) |
| -- | `enforce.sh` (new consolidated PreToolUse gate) |

**Data safety:** Your corrections and rules are preserved. Migrations add new tables and columns without touching existing data. The backup created before migration gives you a rollback path if needed.

---

## Downgrading

Not officially supported. If you need to revert:

1. Restore the backup: `cp .calx/calx.db.backup.v{N} .calx/calx.db`
2. Install the previous version: `pip install getcalx==0.5.1`

The backup file contains the exact database state before the migration ran.
