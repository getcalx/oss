"""HTTP enforcement endpoints served on port 4195.

Starlette ASGI app handling session registration, orientation,
tool-call counting, collapse guard, and session end.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from calx.serve import __version__
from calx.serve.config import ServerConfig
from calx.serve.db.engine import SessionRow
from calx.serve.engine.state_writer import (
    remove_session_state,
    write_active_session,
    write_session_state,
)
from calx.serve.resources.briefing import build_briefing


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compute_action(token_estimate: int, soft_cap: int, ceiling: int) -> str:
    if token_estimate >= ceiling:
        return "block"
    if token_estimate >= soft_cap:
        return "warn"
    return "allow"


def create_enforcement_app(
    db: object,
    config: ServerConfig,
    state_dir: Path,
) -> Starlette:
    """Create the Starlette ASGI app for enforcement endpoints."""

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "version": __version__})

    async def register_session(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"status": "error", "message": "invalid JSON"}, status_code=400,
            )

        surface = body.get("surface")
        if not surface:
            return JSONResponse(
                {"status": "error", "message": "surface is required"}, status_code=400,
            )

        session_id = body.get("session_id") or f"sess_{uuid.uuid4().hex[:12]}"

        # End any active session first
        active = await db.get_active_session()
        if active and active.id != session_id:
            await db.update_session(active.id, ended_at=_now())
            remove_session_state(state_dir, active.id)

        # Check if session already exists (idempotent)
        existing = await db.get_session(session_id)
        if existing:
            briefing = await build_briefing(db, surface)
            return JSONResponse({
                "session_id": session_id,
                "oriented": bool(existing.oriented),
                "briefing": briefing,
                "state_file": f".calx/state/session-{session_id}.json",
            })

        session = SessionRow(
            id=session_id,
            surface=surface,
            surface_type=surface,
            soft_cap=config.soft_cap,
            ceiling=config.ceiling,
            server_fail_mode=config.server_fail_mode,
            collapse_fail_mode=config.collapse_fail_mode,
            started_at=_now(),
        )
        await db.insert_session(session)

        # Build briefing
        briefing = await build_briefing(db, surface)

        # Get rules for state file
        rules = await db.find_rules(active_only=True)
        rules_data = [{"id": r.id, "text": r.rule_text} for r in rules]

        # Write state files
        write_session_state(
            state_dir=state_dir,
            session_id=session_id,
            surface=surface,
            oriented=False,
            token_estimate=0,
            tool_call_count=0,
            soft_cap=config.soft_cap,
            ceiling=config.ceiling,
            server_fail_mode=config.server_fail_mode,
            collapse_fail_mode=config.collapse_fail_mode,
            started_at=session.started_at,
            rules=rules_data,
        )
        write_active_session(state_dir, session_id)

        return JSONResponse({
            "session_id": session_id,
            "oriented": False,
            "briefing": briefing,
            "state_file": f".calx/state/session-{session_id}.json",
        })

    async def orientation(request: Request) -> JSONResponse:
        session_id = request.query_params.get("session_id")
        if not session_id:
            return JSONResponse(
                {"status": "error", "message": "session_id is required"},
                status_code=400,
            )

        session = await db.get_session(session_id)
        if not session:
            return JSONResponse(
                {"status": "error", "message": "session not found"},
                status_code=404,
            )

        if session.oriented:
            return JSONResponse({"oriented": True})
        else:
            rules = await db.find_rules(active_only=True)
            rules_data = [{"id": r.id, "text": r.rule_text} for r in rules]
            return JSONResponse({
                "oriented": False,
                "rules": rules_data,
                "message": "Read project rules before editing files.",
            })

    async def mark_oriented(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"status": "error", "message": "invalid JSON"}, status_code=400,
            )

        session_id = body.get("session_id")
        if not session_id:
            return JSONResponse(
                {"status": "error", "message": "session_id is required"},
                status_code=400,
            )

        session = await db.get_session(session_id)
        if not session:
            return JSONResponse(
                {"status": "error", "message": "session not found"},
                status_code=404,
            )

        await db.update_session(session_id, oriented=1)

        # Update state file
        rules = await db.find_rules(active_only=True)
        rules_data = [{"id": r.id, "text": r.rule_text} for r in rules]
        write_session_state(
            state_dir=state_dir,
            session_id=session_id,
            surface=session.surface,
            oriented=True,
            token_estimate=session.token_estimate,
            tool_call_count=session.tool_call_count,
            soft_cap=session.soft_cap,
            ceiling=session.ceiling,
            server_fail_mode=session.server_fail_mode,
            collapse_fail_mode=session.collapse_fail_mode,
            started_at=session.started_at,
            rules=rules_data,
        )

        return JSONResponse({"status": "ok"})

    async def token_budget(request: Request) -> JSONResponse:
        session_id = request.query_params.get("session_id")
        if not session_id:
            return JSONResponse(
                {"status": "error", "message": "session_id is required"},
                status_code=400,
            )

        session = await db.get_session(session_id)
        if not session:
            return JSONResponse(
                {"status": "error", "message": "session not found"},
                status_code=404,
            )

        action = _compute_action(
            session.token_estimate, session.soft_cap, session.ceiling,
        )

        return JSONResponse({
            "soft_cap": session.soft_cap,
            "ceiling": session.ceiling,
            "estimated_current": session.token_estimate,
            "action": action,
        })

    async def increment_tool_call(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"status": "error", "message": "invalid JSON"}, status_code=400,
            )

        session_id = body.get("session_id")
        if not session_id:
            return JSONResponse(
                {"status": "error", "message": "session_id is required"},
                status_code=400,
            )

        session = await db.get_session(session_id)
        if not session:
            return JSONResponse(
                {"status": "error", "message": "session not found"},
                status_code=404,
            )

        new_count = session.tool_call_count + 1
        new_estimate = new_count * config.tokens_per_call
        await db.update_session(
            session_id,
            tool_call_count=new_count,
            token_estimate=new_estimate,
        )

        action = _compute_action(new_estimate, session.soft_cap, session.ceiling)

        # Update state file
        rules = await db.find_rules(active_only=True)
        rules_data = [{"id": r.id, "text": r.rule_text} for r in rules]
        write_session_state(
            state_dir=state_dir,
            session_id=session_id,
            surface=session.surface,
            oriented=bool(session.oriented),
            token_estimate=new_estimate,
            tool_call_count=new_count,
            soft_cap=session.soft_cap,
            ceiling=session.ceiling,
            server_fail_mode=session.server_fail_mode,
            collapse_fail_mode=session.collapse_fail_mode,
            started_at=session.started_at,
            rules=rules_data,
        )

        return JSONResponse({
            "status": "ok",
            "tool_call_count": new_count,
            "token_estimate": new_estimate,
            "action": action,
        })

    async def update_tokens(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"status": "error", "message": "invalid JSON"}, status_code=400,
            )

        session_id = body.get("session_id")
        token_estimate = body.get("token_estimate")
        if not session_id:
            return JSONResponse(
                {"status": "error", "message": "session_id is required"},
                status_code=400,
            )

        session = await db.get_session(session_id)
        if not session:
            return JSONResponse(
                {"status": "error", "message": "session not found"},
                status_code=404,
            )

        await db.update_session(session_id, token_estimate=token_estimate)
        action = _compute_action(token_estimate, session.soft_cap, session.ceiling)

        return JSONResponse({"status": "ok", "action": action})

    async def end_session(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"status": "error", "message": "invalid JSON"}, status_code=400,
            )

        session_id = body.get("session_id")
        if not session_id:
            return JSONResponse(
                {"status": "error", "message": "session_id is required"},
                status_code=400,
            )

        session = await db.get_session(session_id)
        if not session:
            return JSONResponse(
                {"status": "error", "message": "session not found"},
                status_code=404,
            )

        if session.ended_at:
            return JSONResponse(
                {"status": "error", "message": "session already ended"},
                status_code=409,
            )

        now = _now()
        await db.update_session(session_id, ended_at=now)
        remove_session_state(state_dir, session_id)

        # Count corrections logged during this session
        corrections = await db.find_corrections(limit=1000)
        session_corrections = [
            c for c in corrections
            if c.created_at >= session.started_at
        ]

        # Compute duration
        try:
            started = datetime.fromisoformat(session.started_at.replace("Z", "+00:00"))
            ended = datetime.fromisoformat(now.replace("Z", "+00:00"))
            duration_minutes = int((ended - started).total_seconds() / 60)
        except (ValueError, AttributeError):
            duration_minutes = 0

        return JSONResponse({
            "status": "ok",
            "corrections_logged": len(session_corrections),
            "duration_minutes": duration_minutes,
        })

    async def log_correction(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"status": "error", "message": "invalid JSON"}, status_code=400)

        correction = body.get("correction")
        domain = body.get("domain")
        category = body.get("category", "procedural")
        if not correction or not domain:
            return JSONResponse({"status": "error", "message": "correction and domain required"}, status_code=400)

        from calx.serve.tools.log_correction import handle_log_correction
        result = await handle_log_correction(
            db, correction, domain, category,
            severity=body.get("severity", "medium"),
            confidence=body.get("confidence", "medium"),
            surface=body.get("surface", "cli"),
            task_context=body.get("task_context"),
            learning_mode=body.get("learning_mode", "unknown"),
        )
        return JSONResponse(result)

    async def rule_health(request: Request) -> JSONResponse:
        from calx.serve.engine.health import score_all_rules
        results = await score_all_rules(db)

        role_filter = request.query_params.get("role")
        if role_filter:
            filtered = []
            for r in results:
                rule = await db.get_rule(r.rule_id)
                if rule and (rule.role is None or rule.role == role_filter):
                    filtered.append(r)
            results = filtered

        return JSONResponse({
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "score": r.new_score,
                    "status": r.new_status,
                    "old_score": r.old_score,
                    "old_status": r.old_status,
                    "decay_factors": r.decay_factors,
                }
                for r in results
            ]
        })

    async def compilations(request: Request) -> JSONResponse:
        from calx.serve.engine.compilation import get_compilation_stats, get_compilation_candidates
        stats = await get_compilation_stats(db)
        candidates = await get_compilation_candidates(db)
        return JSONResponse({
            "stats": stats,
            "candidates": [
                {"id": c.id, "domain": c.domain, "rule_text": c.rule_text, "learning_mode": c.learning_mode}
                for c in candidates
            ],
        })

    async def promotion_candidates(request: Request) -> JSONResponse:
        corrections = await db.find_corrections(limit=1000)
        from calx.serve.engine.promotion import PROMOTION_THRESHOLD
        candidates = [
            c for c in corrections
            if c.recurrence_count >= PROMOTION_THRESHOLD and not c.promoted and not c.quarantined
        ]
        return JSONResponse({
            "candidates": [
                {"id": c.id, "domain": c.domain, "correction": c.correction, "recurrence_count": c.recurrence_count}
                for c in candidates
            ]
        })

    async def promote(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"status": "error", "message": "invalid JSON"}, status_code=400)

        correction_id = body.get("correction_id")
        rule_text = body.get("rule_text")
        if not correction_id or not rule_text:
            return JSONResponse({"status": "error", "message": "correction_id and rule_text required"}, status_code=400)

        from calx.serve.tools.promote_correction import handle_promote_correction
        result = await handle_promote_correction(db, correction_id, rule_text)
        status_code = 200
        if result.get("status") == "not_found":
            status_code = 404
        elif result.get("status") == "conflict":
            status_code = 409
        return JSONResponse(result, status_code=status_code)

    async def board(request: Request) -> JSONResponse:
        items = await db.get_board_state()
        return JSONResponse({
            "items": [
                {"id": i.id, "domain": i.domain, "description": i.description, "status": i.status}
                for i in items
            ]
        })

    async def foil_review(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"status": "error", "message": "invalid JSON"}, status_code=400)

        spec_reference = body.get("spec_reference")
        reviewer_domain = body.get("reviewer_domain")
        verdict = body.get("verdict")
        if not spec_reference or not reviewer_domain or not verdict:
            return JSONResponse(
                {"status": "error", "message": "spec_reference, reviewer_domain, and verdict required"},
                status_code=400,
            )

        from calx.serve.tools.record_foil_review import handle_record_foil_review
        result = await handle_record_foil_review(
            db, spec_reference, reviewer_domain, verdict,
            findings=body.get("findings"),
            round=body.get("round", 1),
        )
        return JSONResponse(result)

    async def foil_reviews_list(request: Request) -> JSONResponse:
        reviews = await db.get_foil_reviews()
        return JSONResponse({
            "reviews": [
                {
                    "id": r.id,
                    "spec_reference": r.spec_reference,
                    "reviewer_domain": r.reviewer_domain,
                    "verdict": r.verdict,
                    "findings": r.findings,
                    "round": r.round,
                    "session_id": r.session_id,
                    "created_at": r.created_at,
                }
                for r in reviews
            ]
        })

    async def review_gaps(request: Request) -> JSONResponse:
        from calx.serve.tools.record_foil_review import get_review_gaps
        gaps = await get_review_gaps(db)
        return JSONResponse({"domains": gaps})

    async def plan_endpoint(request: Request) -> JSONResponse:
        if request.method == "GET":
            plan = await db.get_active_plan()
            if not plan:
                return JSONResponse({"status": "no_active_plan"})
            import json as _json
            chunks = _json.loads(plan.chunks)
            edges = _json.loads(plan.dependency_edges)
            from calx.serve.engine.orchestration import compute_waves, get_next_dispatchable
            waves = compute_waves(chunks, edges)
            next_disp = get_next_dispatchable(chunks, edges, plan.current_wave - 1)
            return JSONResponse({
                "status": "ok",
                "plan_id": plan.id,
                "task_description": plan.task_description,
                "phase": plan.phase,
                "current_wave": plan.current_wave,
                "total_waves": len(waves),
                "chunks": chunks,
                "next_dispatchable": next_disp,
            })
        else:
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({"status": "error", "message": "invalid JSON"}, status_code=400)
            task = body.get("task_description")
            chunks = body.get("chunks")
            edges = body.get("dependency_edges")
            if not task or chunks is None or edges is None:
                return JSONResponse({"status": "error", "message": "task_description, chunks, and dependency_edges required"}, status_code=400)
            from calx.serve.tools.create_plan import handle_create_plan
            import json as _json
            result = await handle_create_plan(
                db, task,
                _json.dumps(chunks) if isinstance(chunks, list) else chunks,
                _json.dumps(edges) if isinstance(edges, list) else edges,
            )
            return JSONResponse(result)

    async def advance_plan_endpoint(request: Request) -> JSONResponse:
        plan = await db.get_active_plan()
        if not plan:
            return JSONResponse({"status": "no_active_plan"}, status_code=404)
        from calx.serve.engine.orchestration import advance_phase
        new_phase, message = await advance_phase(db, plan.id)
        return JSONResponse({
            "status": "ok",
            "phase": new_phase,
            "message": message,
        })

    async def update_plan_endpoint(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"status": "error", "message": "invalid JSON"}, status_code=400)
        plan_id = body.get("plan_id")
        if not plan_id:
            return JSONResponse({"status": "error", "message": "plan_id required"}, status_code=400)
        from calx.serve.tools.update_plan import handle_update_plan
        result = await handle_update_plan(
            db, plan_id,
            chunk_id=body.get("chunk_id"),
            chunk_status=body.get("chunk_status"),
            block_reason=body.get("block_reason"),
            spec_file=body.get("spec_file"),
            test_files=body.get("test_files"),
            review_id=body.get("review_id"),
        )
        return JSONResponse(result)

    async def dispatch_endpoint(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"status": "error", "message": "invalid JSON"}, status_code=400)
        plan_id = body.get("plan_id")
        chunk_id = body.get("chunk_id")
        if not plan_id or not chunk_id:
            return JSONResponse({"status": "error", "message": "plan_id and chunk_id required"}, status_code=400)
        from calx.serve.tools.dispatch_chunk import handle_dispatch_chunk
        result = await handle_dispatch_chunk(db, plan_id, chunk_id)
        return JSONResponse(result)

    async def redispatch_endpoint(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"status": "error", "message": "invalid JSON"}, status_code=400)
        plan_id = body.get("plan_id")
        chunk_id = body.get("chunk_id")
        if not plan_id or not chunk_id:
            return JSONResponse({"status": "error", "message": "plan_id and chunk_id required"}, status_code=400)
        from calx.serve.tools.redispatch_chunk import handle_redispatch_chunk
        result = await handle_redispatch_chunk(db, plan_id, chunk_id)
        return JSONResponse(result)

    async def verify_endpoint(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"status": "error", "message": "invalid JSON"}, status_code=400)
        plan_id = body.get("plan_id")
        wave_id = body.get("wave_id")
        if not plan_id or wave_id is None:
            return JSONResponse({"status": "error", "message": "plan_id and wave_id required"}, status_code=400)
        from calx.serve.tools.verify_wave import handle_verify_wave
        result = await handle_verify_wave(db, plan_id, wave_id, manual_notes=body.get("manual_notes"))
        return JSONResponse(result)

    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/enforce/register-session", register_session, methods=["POST"]),
        Route("/enforce/orientation", orientation, methods=["GET"]),
        Route("/enforce/mark-oriented", mark_oriented, methods=["POST"]),
        Route("/enforce/token-budget", token_budget, methods=["GET"]),
        Route("/enforce/increment-tool-call", increment_tool_call, methods=["POST"]),
        Route("/enforce/update-tokens", update_tokens, methods=["POST"]),
        Route("/enforce/end-session", end_session, methods=["POST"]),
        Route("/enforce/log-correction", log_correction, methods=["POST"]),
        Route("/enforce/rule-health", rule_health, methods=["GET"]),
        Route("/enforce/compilations", compilations, methods=["GET"]),
        Route("/enforce/promotion-candidates", promotion_candidates, methods=["GET"]),
        Route("/enforce/promote", promote, methods=["POST"]),
        Route("/enforce/board", board, methods=["GET"]),
        Route("/enforce/foil-review", foil_review, methods=["POST"]),
        Route("/enforce/foil-reviews", foil_reviews_list, methods=["GET"]),
        Route("/enforce/review-gaps", review_gaps, methods=["GET"]),
        Route("/enforce/plan", plan_endpoint, methods=["GET", "POST"]),
        Route("/enforce/plan/advance", advance_plan_endpoint, methods=["POST"]),
        Route("/enforce/plan/update", update_plan_endpoint, methods=["POST"]),
        Route("/enforce/dispatch", dispatch_endpoint, methods=["POST"]),
        Route("/enforce/redispatch", redispatch_endpoint, methods=["POST"]),
        Route("/enforce/verify", verify_endpoint, methods=["POST"]),
    ]

    return Starlette(routes=routes)
