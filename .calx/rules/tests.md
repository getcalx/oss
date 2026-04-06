# Rules: tests

### tests-R001: Never rewrite a file from scratch -- always delta edit
Source: seed | Added: 2026-03-22 | Status: active | Type: process

When modifying existing files, use targeted edits (Edit tool) rather than
full rewrites (Write tool). Full rewrites lose accumulated content and
introduce inconsistencies. This rule is pre-loaded so you can see the
injection mechanism work immediately.

### tests-R002: Every migration must be self-contained at its position in the chain
Source: correction | Added: 2026-04-06 | Status: active | Type: architectural

A migration N may only reference tables and columns that exist after
migrations 1..(N-1) have run. No forward references to objects created
by later migrations. Enforced by TestMigrationOrdering.test_no_forward_references
in tests/serve/db/test_schema_contract.py.
