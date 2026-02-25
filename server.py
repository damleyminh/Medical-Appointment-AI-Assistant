"""
server.py — FastAPI backend for the Appointment Assistance System web UI.

"""
from __future__ import annotations

import os
import json
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Appointment Assistance System", version="1.0.0")

# In-memory store: run_id → state dict
_runs: dict[str, dict] = {}


# ─── Request / Response models ────────────────────────────────────────────────

class RunRequest(BaseModel):
    message: str
    conversation_history: list = []  # [{role, content}] from previous turns
    session_intent: Optional[str] = None  # carry intent across turns
    patient_name: Optional[str] = None   # set after login
    health_profile: Optional[str] = None  # full health profile text from check-in form

class LoginRequest(BaseModel):
    username: str
    password: str

class HITLResponse(BaseModel):
    run_id: str
    action: str          # approved | edited | escalated
    edited_text: Optional[str] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _initial_state(message: str, history: list = None, session_intent: str = None,
                   patient_name: str = None, health_profile: str = None) -> dict:
    identity = f"[Logged-in patient: {patient_name}]\n" if patient_name else ""
    # Inject health profile so EVERY node can see it directly in raw_input
    profile_block = f"[Patient Health Profile]\n{health_profile}\n\n" if health_profile else ""
    # Also extract profile from conversation history if not passed directly
    if not profile_block and history:
        for h in history:
            if h.get("role") == "system" and "PATIENT PROFILE" in h.get("content", ""):
                profile_block = f"[Patient Health Profile]\n{h['content']}\n\n"
                break
    # Build history text — skip system/profile messages
    if history:
        history_msgs = [h for h in history if h.get("role") != "system"]
        history_text = "\n".join(
            f"{'Patient' if h['role'] == 'user' else 'Agent'}: {h['content']}"
            for h in history_msgs[-6:]
        )
        raw = f"{identity}{profile_block}[Conversation so far]\n{history_text}\n\n[New patient message]\n{message}"
    else:
        raw = f"{identity}{profile_block}{message}"
    return {
        "raw_input":          raw,
        "latest_message":     message,   # only the new message — shown to staff
        "messages":           [],
        "intent":             None,
        "pii_masked_input":   None,
        "pii_map":            {},
        "moderation_flagged": False,
        "mod_categories":     [],
        "call_count":         0,
        "draft_response":     None,
        "final_response":     None,
        "hitl_action":        None,
        "status":             None,
        "route_path":         [],
        "error":              None,
        "hitl_pending":       False,
        "hitl_api_action":    None,
        "api_mode":            True,
        "hitl_api_edit":      None,
        "run_id":             "",
        "timestamp":          "",
    }


def _safe_state(state: dict) -> dict:
    """Strip non-serialisable fields."""
    return {k: v for k, v in state.items() if k != "messages"}


# ─── API Routes ───────────────────────────────────────────────────────────────

@app.post("/api/run")
async def start_run(req: RunRequest):
    """
    Phase 1: Run the graph up to (and including) draft generation.
    For normal intents the graph stops before HITL, returning the draft.
    Emergency and unknown intents resolve immediately.
    """
    from src.agents.graph import appointment_graph

    try:
        state = _initial_state(req.message, req.conversation_history, req.session_intent,
                               req.patient_name, req.health_profile)
        state["patient_name"] = req.patient_name or ""
        state["conversation_history"] = req.conversation_history
        result = appointment_graph.invoke(state)
    except Exception as exc:
        import traceback, logging
        logging.error("Graph error in /api/run: %s\n%s", exc, traceback.format_exc())
        return {
            "run_id": "ERROR", "status": "NEED_INFO", "intent": "unknown",
            "draft": "Sorry, something went wrong processing your request. Please try again.",
            "final": "Sorry, something went wrong processing your request. Please try again.",
            "hitl_needed": False, "route_path": ["error"],
            "pii_detected": False, "moderation_flagged": False,
            "call_count": 0, "timestamp": "", "error": str(exc),
        }

    run_id = result.get("run_id", "UNKNOWN")
    _runs[run_id] = result

    response = _safe_state(result)

    # HITL needed: draft exists but no final_response yet (first pass)
    needs_hitl = (
        result.get("draft_response") is not None
        and result.get("final_response") is None
        and result.get("hitl_action") not in ("auto-escalated", "auto-need-info")
        and result.get("status") not in ("ESCALATE", "NEED_INFO")
    )

    return {
        "run_id":       run_id,
        "status":       result.get("status"),
        "intent":       result.get("intent"),
        "draft":        result.get("draft_response"),
        "final":        result.get("final_response"),
        "hitl_needed":  needs_hitl,
        "route_path":   result.get("route_path", []),
        "pii_detected": bool(result.get("pii_map")),
        "moderation_flagged": result.get("moderation_flagged"),
        "call_count":   result.get("call_count"),
        "timestamp":    result.get("timestamp"),
    }


@app.post("/api/hitl/respond")
async def hitl_respond(resp: HITLResponse):
    """
    Phase 2: Accept human reviewer decision, re-run finalize node.
    """
    from src.agents.graph import appointment_graph

    state = _runs.get(resp.run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Run {resp.run_id} not found.")

    if resp.action not in ("approved", "edited", "escalated"):
        raise HTTPException(status_code=400, detail="action must be: approved | edited | escalated")

    try:
        # Inject HITL decision
        state["hitl_api_action"] = resp.action
        state["hitl_api_edit"]   = resp.edited_text
        # Clear final_response so edge_needs_hitl routes through hitl_review
        state["final_response"]  = None

        result = appointment_graph.invoke(state)
        _runs[resp.run_id] = result

        return {
            "run_id":       resp.run_id,
            "status":       result.get("status"),
            "hitl_action":  result.get("hitl_action"),
            "final":        result.get("final_response"),
            "route_path":   result.get("route_path", []),
        }
    except Exception as exc:
        import traceback, logging
        logging.error("Graph error in /api/hitl/respond: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/run/{run_id}")
async def get_run(run_id: str):
    state = _runs.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return _safe_state(state)


@app.get("/api/appointments")
async def list_appointments():
    from src.tools.appointment_tools import list_appointments as _list
    return {"appointments": _list()}


@app.get("/api/health")
async def health():
    return {"status": "ok", "model": os.getenv("OPENAI_MODEL", "gpt-4o")}


@app.get("/api/queue")
async def get_queue():
    """Returns all runs for the staff HITL review queue."""
    return {"runs": [_safe_state(r) for r in _runs.values()]}


# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/api/login")
async def login(req: LoginRequest):
    from src.tools.appointment_tools import authenticate_patient
    patient = authenticate_patient(req.username, req.password)
    if not patient:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return {"success": True, "patient": patient}


# ─── Static files / SPA ───────────────────────────────────────────────────────
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def serve_patient_ui():
    """Patient-facing portal."""
    index = static_dir / "patient" / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"message": "Patient UI not found."})


@app.get("/staff")
async def serve_staff_ui():
    """Staff HITL review portal."""
    index = static_dir / "staff" / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"message": "Staff UI not found."})


if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading

    port = 8000

    print("\n" + "─" * 52)
    print("  🏥  MedSchedule AI — Appointment Assistant")
    print("─" * 52)
    print(f"  ✅  Server starting on port {port}")
    print(f"  👤  Patient Portal:  http://localhost:{port}/")
    print(f"  🔐  Staff Portal:    http://localhost:{port}/staff")
    print(f"  ⏹   Press CTRL+C to stop")
    print("─" * 52 + "\n")

    def _open_browser():
        import time
        time.sleep(1.5)  # wait for server to be ready
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)