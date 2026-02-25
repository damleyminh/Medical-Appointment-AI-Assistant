"""
graph.py — LangGraph middleware-driven orchestration for the
Appointment Assistance System.

Supported intents:
  REQUIRED (with HITL):
    reschedule        — move appointment to new slot
    cancel            — cancel an appointment
    prep_instructions — preparation instructions for procedures

  EXTENDED (no HITL, direct response):
    view_appointments — list/show current appointments
    book_appointment  — book a new appointment
    check_status      — check status of a specific appointment
    general_inquiry   — clinic hours, location, contact, parking

  SAFETY:
    emergency         — immediate escalation
    unknown           — NEED_INFO fallback

Terminal statuses: READY | NEED_INFO | ESCALATE
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Optional

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.middleware.pii import PIIMiddleware
from src.middleware.moderation import ModerationMiddleware
from src.middleware.call_limits import CallLimitMiddleware
from src.middleware.hitl import HumanInTheLoopMiddleware
from src.middleware.retry import ModelRetryMiddleware, ToolRetryMiddleware
from src.middleware.fallback import ModelFallbackMiddleware
from src.middleware.context_editing import ContextEditingMiddleware
from src.utils.logger import RunLogger
from src.tools.appointment_tools import (
    get_available_slots,
    get_prep_instructions,
    get_appointments_summary,
    get_clinic_info,
    get_appointment_types_list,
    book_appointment,
    lookup_appointment,
)

# ─── Shared middleware instances ───────────────────────────────────────────────
pii_mw        = PIIMiddleware()
mod_mw        = ModerationMiddleware()
limit_mw      = CallLimitMiddleware(max_calls=6)
hitl_mw       = HumanInTheLoopMiddleware()
model_retry   = ModelRetryMiddleware(max_retries=3, backoff=1.5)
tool_retry    = ToolRetryMiddleware(max_retries=3)
ctx_editor    = ContextEditingMiddleware(
                    max_tokens=3000,
                    system_prompt="You are a professional medical appointment coordinator.")
run_log       = RunLogger()

# Intents that require HITL review (the 3 required ones)
HITL_INTENTS = {
    "reschedule", "cancel", "prep_instructions", "book_appointment"
}

# These intents auto-answer immediately — no staff review needed
AUTO_INTENTS = {
    "view_appointments", "check_status", "general_inquiry"
}


# ─── State Schema ──────────────────────────────────────────────────────────────
class AppointmentState(TypedDict):
    run_id:             str
    timestamp:          str
    messages:           Annotated[list, add_messages]
    raw_input:          str
    latest_message:     Optional[str]   # the new message only, without history prefix
    intent:             Optional[str]
    pii_masked_input:   Optional[str]
    pii_map:            Optional[dict]
    moderation_flagged: bool
    mod_categories:     list
    call_count:         int
    draft_response:     Optional[str]
    final_response:     Optional[str]
    hitl_action:        Optional[str]
    status:             Optional[str]
    route_path:         list
    error:              Optional[str]
    hitl_pending:       bool
    hitl_api_action:    Optional[str]
    hitl_api_edit:      Optional[str]
    api_mode:           Optional[bool]


# ─── LLM factory ──────────────────────────────────────────────────────────────
def _make_llm(fallback: bool = False) -> ChatOpenAI:
    model = (
        os.getenv("OPENAI_FALLBACK_MODEL", "gpt-3.5-turbo")
        if fallback
        else os.getenv("OPENAI_MODEL", "gpt-4o")
    )
    return ChatOpenAI(model=model, temperature=0.3, api_key=os.getenv("OPENAI_API_KEY"))


def _llm_invoke(messages, state, skip_context_edit: bool = False) -> tuple[str, int]:
    """Call LLM with call-limit, retry, fallback, and context editing."""
    count = limit_mw.check_and_increment(state["call_count"])
    # ContextEditingMiddleware: trim/inject context before sending
    # Skip for intent classifier — it has its own system prompt that must not be overridden
    edited = messages if skip_context_edit else ctx_editor.edit(messages)
    # ModelFallbackMiddleware: try primary then fallback
    fallback_mw = ModelFallbackMiddleware(models=[_make_llm(), _make_llm(fallback=True)])
    # ModelRetryMiddleware: retry each model up to 3 times
    try:
        response = model_retry.invoke(fallback_mw.models[0], edited)
    except Exception as exc:
        run_log.log("llm", "retry_failed_using_fallback", str(exc))
        response = fallback_mw.invoke(edited)
    return response.content, count


# ─── Node: init_run ────────────────────────────────────────────────────────────
def node_init_run(state: AppointmentState) -> dict:
    run_id = str(uuid.uuid4())[:8].upper()
    ts = datetime.utcnow().isoformat() + "Z"
    run_log.start(run_id)
    run_log.log("init_run", "started", f"run_id={run_id}")
    return {
        "run_id": run_id, "timestamp": ts,
        "route_path": ["init_run"], "call_count": 0,
        "moderation_flagged": False, "mod_categories": [],
        "hitl_pending": False, "pii_map": {},
    }


# ─── Node: pii_filter ─────────────────────────────────────────────────────────
def node_pii_filter(state: AppointmentState) -> dict:
    masked, pii_map = pii_mw.mask(state["raw_input"])
    run_log.log("pii_filter", "pii_detected" if pii_map else "clean", f"{len(pii_map)} tokens")
    return {
        "pii_masked_input": masked, "pii_map": pii_map,
        "route_path": state["route_path"] + ["pii_filter"],
    }


# ─── Node: moderation_check ───────────────────────────────────────────────────
def node_moderation_check(state: AppointmentState) -> dict:
    text = state.get("pii_masked_input") or state["raw_input"]
    flagged, categories = mod_mw.check(text)
    run_log.log("moderation_check", "flagged" if flagged else "pass", categories or None)
    return {
        "moderation_flagged": flagged, "mod_categories": categories,
        "route_path": state["route_path"] + ["moderation_check"],
    }


def edge_after_moderation(state: AppointmentState) -> str:
    # Second pass (HITL approval) — skip re-running handlers, go straight to hitl_review
    if state.get("hitl_api_action"):
        return "hitl_review"
    return "handle_emergency" if state["moderation_flagged"] else "intent_classifier"


# ─── Node: intent_classifier ──────────────────────────────────────────────────
INTENT_SYSTEM = """You are an intent classifier for a medical appointment-assistance system.
The input may contain a [Conversation so far] section, a patient health profile, and a new message.
Use all context to determine the correct intent.

If the new message is a follow-up (e.g. providing a name, date, or confirmation after the agent asked),
classify it as the SAME intent as the previous conversation turn.

Classify into exactly one of these intents:

  reschedule        — patient wants to move, change, or reschedule their appointment
  cancel            — patient wants to cancel or remove their appointment
  prep_instructions — patient asking how to prepare for a procedure, exam, scan, or imaging
  view_appointments — patient wants to see, list, check, or view their appointments or schedule
  book_appointment  — patient wants to book, schedule, make, or create a new appointment
  check_status      — patient asking about the status or details of a specific appointment
  general_inquiry   — clinic hours, location, parking, or general health questions with no current symptom
  emergency         — clearly life-threatening RIGHT NOW, needs 911 immediately
  triage_needed     — patient reports a current physical symptom about themselves
  unknown           — does not clearly match any of the above

EMERGENCY (911 now, no hesitation):
  - Chest pain + arm/jaw numbness/sweating → heart attack
  - Face drooping + arm weakness + slurred speech → stroke
  - Throat swelling/can't breathe after allergen → anaphylaxis
  - Loss of consciousness, uncontrolled bleeding, active seizure
  - Suspected overdose or poisoning, severe burns on face/airway
  - "I am dying", "call an ambulance", active suicidal attempt

TRIAGE_NEEDED (patient mentions a current symptom — needs risk assessment):
  ANY physical symptom the patient is experiencing right now:
  headache, dizziness, chest discomfort, shortness of breath, pain anywhere,
  nausea, fatigue, swelling, fever, confusion, vision changes, palpitations,
  numbness/tingling, weakness, back pain, stomach pain, rash, bleeding

NOT triage, NOT emergency:
  - "I have diabetes" / "I have hypertension" (condition statement, no current symptom)
  - "What causes headaches?" (general question, not about themselves)
  - Anything appointment/clinic related

Examples:
  "I have chest pain and my left arm is numb" → emergency
  "I think I'm having a stroke" → emergency
  "I can't breathe at all" → emergency
  "I'm having a seizure" → emergency
  "I have a headache" → triage_needed
  "I feel dizzy" → triage_needed
  "I have chest discomfort" → triage_needed
  "My back hurts" → triage_needed
  "I feel short of breath" → triage_needed
  "I've been feeling really tired lately" → triage_needed
  "I have a fever and stiff neck" → triage_needed
  "I have nausea" → triage_needed
  "I have diabetes" → general_inquiry
  "What time do you open?" → general_inquiry
  "I want to book a new appointment" → book_appointment
  "Show me my appointments" → view_appointments

Respond with ONLY the intent label. Nothing else."""

def node_intent_classifier(state: AppointmentState) -> dict:
    text = state.get("pii_masked_input") or state["raw_input"]
    valid = {"reschedule", "cancel", "prep_instructions", "view_appointments",
             "book_appointment", "check_status", "general_inquiry", "emergency",
             "triage_needed", "unknown"}
    try:
        content, count = _llm_invoke(
            [SystemMessage(content=INTENT_SYSTEM), HumanMessage(content=text)], state,
            skip_context_edit=True
        )
        intent = content.strip().lower()
        if intent not in valid:
            intent = "unknown"
    except RuntimeError as e:
        run_log.log("intent_classifier", "call_limit", str(e))
        return {"intent": "unknown", "call_count": state["call_count"], "error": str(e),
                "route_path": state["route_path"] + ["intent_classifier"]}
    except Exception as e:
        run_log.log("intent_classifier", "error", str(e))
        intent, count = "unknown", state["call_count"]

    run_log.log("intent_classifier", "classified", intent)
    return {
        "intent": intent, "call_count": count,
        "route_path": state["route_path"] + ["intent_classifier"],
        "messages": [HumanMessage(content=text)],
    }


def edge_route_intent(state: AppointmentState) -> str:
    return {
        "reschedule":        "handle_reschedule",
        "cancel":            "handle_cancel",
        "prep_instructions": "handle_prep",
        "view_appointments": "handle_view_appointments",
        "book_appointment":  "handle_book_appointment",
        "check_status":      "handle_check_status",
        "general_inquiry":   "handle_general_inquiry",
        "emergency":         "handle_emergency",
        "triage_needed":     "handle_triage",
        "unknown":           "handle_unknown",
    }.get(state.get("intent", "unknown"), "handle_unknown")


# ─── REQUIRED: handle_reschedule (HITL) ───────────────────────────────────────
RESCHEDULE_SYSTEM = """You are a friendly, professional medical appointment coordinator.

Read the FULL conversation carefully before responding.

If the patient has already confirmed a specific date and time (e.g. "Monday 9am works", "I'll take slot 3", "Please reschedule to Feb 27"):
- Confirm the reschedule enthusiastically with the exact new date/time
- Tell them their appointment has been updated
- Do NOT show slots again

If the patient hasn't chosen a slot yet:
- Acknowledge their request warmly
- Present available slots in a clear numbered list
- Ask them to confirm their preferred slot
- Mention they can call if none work

IMPORTANT: Write only the final message text. Do NOT include stage directions, narration, or
phrases like "[After a brief pause]", "[pause]", "(a moment later)", or any bracketed actions.
Write as if you are sending a direct message to the patient — nothing else.
Do NOT give any medical advice."""

def node_handle_reschedule(state: AppointmentState) -> dict:
    slots = tool_retry.call(get_available_slots, "general")
    slots_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(slots))
    prompt = f"Patient request: {state.get('pii_masked_input') or state['raw_input']}\n\nAvailable slots:\n{slots_text}"
    try:
        draft, count = _llm_invoke(
            [SystemMessage(content=RESCHEDULE_SYSTEM), HumanMessage(content=prompt)], state
        )
    except Exception:
        draft = "Thank you for reaching out. Please call our scheduling team to find a suitable time."
        count = state["call_count"]
    run_log.log("handle_reschedule", "draft_ready", None)
    return {"draft_response": draft, "call_count": count, "status": "READY",
            "route_path": state["route_path"] + ["handle_reschedule"]}


# ─── REQUIRED: handle_cancel (HITL) ──────────────────────────────────────────
CANCEL_SYSTEM = """You are a friendly, professional medical appointment coordinator.
The patient wants to cancel. Write an empathetic response that:
1. Acknowledges the cancellation request.
2. Confirms the appointment will be cancelled.
3. Lets them know they can re-book any time.
4. Asks if there is anything else you can help with.
IMPORTANT: Write only the final message text. Do NOT include stage directions, narration, or
phrases like "[After a brief pause]", "[pause]", "(a moment later)", or any bracketed actions.
Write as if you are sending a direct message to the patient — nothing else.
Do NOT give any medical advice."""

def node_handle_cancel(state: AppointmentState) -> dict:
    prompt = f"Patient request: {state.get('pii_masked_input') or state['raw_input']}"
    try:
        draft, count = _llm_invoke(
            [SystemMessage(content=CANCEL_SYSTEM), HumanMessage(content=prompt)], state
        )
    except Exception:
        draft = "We've received your cancellation request and will process it shortly. Feel free to re-book any time."
        count = state["call_count"]
    run_log.log("handle_cancel", "draft_ready", None)
    return {"draft_response": draft, "call_count": count, "status": "READY",
            "route_path": state["route_path"] + ["handle_cancel"]}


# ─── REQUIRED: handle_prep (HITL) ─────────────────────────────────────────────
PREP_SYSTEM = """You are a friendly, professional medical appointment coordinator.
The patient's health profile is injected directly into the message under [Patient Health Profile].
Read it carefully and use it to personalise every response.

PERSONALISATION RULES:
- Address the patient by their first name
- If they have ALLERGIES to iodine/contrast and need a CT or MRI with contrast — warn them proactively
- If they have a PACEMAKER or metal IMPLANT and need an MRI — flag this as critical, tell them to inform the radiologist
- If they are on METFORMIN (diabetes medication) and need a CT with contrast — warn them to hold metformin 48h before
- If they have DIABETES and need fasting blood work — advise extra care with insulin/medication timing
- If they have a known ALLERGY to latex — mention gloves may be latex-free on request
- If they have a HEALTH CARD on file — remind them to bring it
- Be warm and reassuring — acknowledge any conditions that might make the procedure feel more daunting
Do NOT give medical advice beyond preparation instructions."""

def node_handle_prep(state: AppointmentState) -> dict:
    raw_text = state.get("pii_masked_input") or state["raw_input"]
    exam_type = "general"
    for kw in ["mri", "ct", "xray", "x-ray", "ultrasound", "imaging", "blood"]:
        if kw in raw_text.lower():
            exam_type = kw.replace("-", "")
            break
    prep_info = get_prep_instructions(exam_type)
    prompt = f"Patient request: {raw_text}\n\nPreparation information:\n{prep_info}"
    try:
        draft, count = _llm_invoke(
            [SystemMessage(content=PREP_SYSTEM), HumanMessage(content=prompt)], state
        )
    except Exception:
        draft = prep_info
        count = state["call_count"]
    run_log.log("handle_prep", "draft_ready", exam_type)
    return {"draft_response": draft, "call_count": count, "status": "READY",
            "route_path": state["route_path"] + ["handle_prep"]}


# ─── EXTENDED: handle_view_appointments (no HITL) ────────────────────────────
VIEW_SYSTEM = """You are a friendly, personalised medical appointment coordinator.
The patient's health profile appears in the message under [Patient Health Profile] — read it and use it.

DISPLAY RULES:
- Address patient by first name
- Show ONLY their appointments (already filtered)
- Format each clearly: type, date/time, provider, location, status, and any notes
- If appointment notes say "bring results from APT-XXX" — highlight that reminder
- If they have upcoming blood work AND are diabetic — remind them about fasting/medication timing
- If they have an MRI AND have listed metal implants — remind them to inform the team
- If no appointments found — say so warmly and offer to book one
Do NOT show other patients' records. Do NOT give medical advice."""

def node_handle_view_appointments(state: AppointmentState) -> dict:
    raw = state.get("pii_masked_input") or state["raw_input"]

    # Extract patient name — priority: state field → raw_input prefix → history scan
    import re as _re2
    patient_name = (state.get("patient_name") or "").strip()

    if not patient_name:
        # Extract from "[Logged-in patient: Name]" prefix in raw_input
        m = _re2.search(r"Logged-in patient:\s*([^\]\n]+)", state.get("raw_input", ""))
        if m: patient_name = m.group(1).strip()

    if not patient_name:
        # Extract from "PATIENT PROFILE — Name" in conversation history
        history = state.get("conversation_history", [])
        for msg in history:
            c = msg.get("content","") if isinstance(msg,dict) else str(msg)
            m = _re2.search(r"PATIENT PROFILE\s*[—-]+\s*([^\n|]+)", c)
            if m:
                patient_name = m.group(1).strip()
                break

    if not patient_name:
        # Last resort: scan history for name introduction
        history = state.get("conversation_history", [])
        for msg in history:
            c = msg.get("content","") if isinstance(msg,dict) else str(msg)
            m = _re2.search(r"(?:my name is|i(?:'m| am)|this is)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)+)", c, _re2.I)
            if m:
                patient_name = m.group(1)
                break

    summary = get_appointments_summary(patient_name)
    context = f"Showing appointments for: {patient_name}" if patient_name else "No patient logged in — showing all records (demo mode)"
    prompt = f"Patient request: {raw}\n\n{context}\n\nAppointment data:\n{summary}"
    try:
        response, count = _llm_invoke(
            [SystemMessage(content=VIEW_SYSTEM), HumanMessage(content=prompt)], state
        )
    except Exception:
        response = f"Here are your appointments:\n\n{summary}"
        count = state["call_count"]
    run_log.log("handle_view_appointments", "auto-answered", None)
    return {
        "draft_response": response, "final_response": response,
        "hitl_action": "auto-answered",
        "call_count": count, "status": "READY",
        "route_path": state["route_path"] + ["handle_view_appointments"],
    }


# ─── EXTENDED: handle_book_appointment (no HITL) ──────────────────────────────
BOOK_SYSTEM = """You are a friendly, warm medical appointment coordinator having a real conversation with a patient.

Read the FULL conversation carefully before responding.

STEP 1 — If patient hasn't specified appointment type: ask which type they need from the list provided.

STEP 2 — If they've chosen a type but NOT a hospital/location yet:
- Show the available locations for that type (from the locations list provided)
- Ask which location they prefer
- Do NOT show time slots yet

STEP 3 — If they've chosen type AND location but NOT a time slot:
- If the patient asked for a specific day (e.g. "any Friday slots?"), show ONLY slots on that day
- Otherwise show the next available slots in a numbered list
- Ask them to pick one

STEP 4 — If the patient has confirmed a specific date/time (e.g. "slot 2", "Feb 27 at 9AM", "I'll take slot 1"):
- This must be a POSITIVE SELECTION, not a question
- "no slots on Friday?" or "are there Friday slots?" is a QUESTION — show Friday slots, do NOT confirm a booking
- Confirm the booking with: exact date/time, chosen location, appointment type
- Give a confirmation number (format: APT-XXXX with random 4 digits)
- Remind them to bring health card and referral if needed
- Do NOT show slots again

Keep tone warm and conversational. Address the patient by their first name.
PERSONALISATION: The patient health profile is in the message under [Patient Health Profile]. Use it:
- If booking MRI and patient has metal implants/pacemaker — remind them to disclose this to the imaging team
- If booking CT with contrast and patient has iodine allergy — flag it proactively
- If booking blood work and patient is diabetic on insulin — remind them about fasting medication guidance
- If booking eye care and patient is on certain medications — note they may need to arrange a driver (eye dilation)
- Always confirm health card if on file. Do NOT give medical advice."""

def node_handle_book_appointment(state: AppointmentState) -> dict:
    from src.tools.appointment_tools import get_locations_for_type
    import re as _re
    raw = state.get("pii_masked_input") or state["raw_input"]
    raw_lower = raw.lower()
    types_text = get_appointment_types_list()

    # ── Detect appointment type — scan ONLY recent messages, not old history ────
    # Use last 3 patient messages + current to avoid cross-session type contamination
    history = state.get("conversation_history", [])
    recent_patient_msgs = []
    for msg in history:
        c = msg.get("content","") if isinstance(msg,dict) else str(msg)
        role = msg.get("role","") if isinstance(msg,dict) else ""
        if role in ("user", "patient", "") and "PATIENT PROFILE" not in c:
            recent_patient_msgs.append(c)
    recent_context = raw + " " + " ".join(recent_patient_msgs[-4:])
    full_context = raw + " " + " ".join(
        (msg.get("content","") if isinstance(msg,dict) else str(msg)) for msg in history
    )
    recent_lower = recent_context.lower()
    full_lower = full_context.lower()

    # Ordered longest-match first to avoid "ct" matching inside "blood work" context etc.
    type_map_ordered = [
        ("blood work", "Blood Work"), ("blood test", "Blood Work"),
        ("bone density", "Bone Density Scan"),
        ("ct scan", "CT Scan"),
        ("x-ray", "X-Ray"), ("xray", "X-Ray"), ("x ray", "X-Ray"),
        ("ultrasound", "Ultrasound"),
        ("mri", "MRI Imaging"),
        ("specialist", "Specialist Consultation"),
        ("orthopedic", "Orthopedic Assessment"),
        ("annual physical", "Annual Physical"), ("physical", "Annual Physical"),
        ("follow-up", "Follow-up Visit"), ("follow up", "Follow-up Visit"),
        ("vaccination", "Vaccination"), ("vaccine", "Vaccination"),
        ("eye care", "Eye Care"),
        ("ct", "CT Scan"),  # short match last
    ]
    # Prefer match from recent patient messages; fall back to full context
    detected_type = next((v for k, v in type_map_ordered if k in recent_lower), None)
    if not detected_type:
        detected_type = next((v for k, v in type_map_ordered if k in full_lower), None)

    # ── Detect location from full conversation ──────────────────────────────────
    loc_map = {
        "infirmary": "QEII Halifax Infirmary — 1799 Robie St, Halifax",
        "victoria general": "QEII Victoria General (VG) — 1278 Tower Rd, Halifax",
        " vg ": "QEII Victoria General (VG) — 1278 Tower Rd, Halifax",
        "dartmouth": "Dartmouth General Hospital — 325 Pleasant St, Dartmouth",
        "bayers lake": "Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres",
        "bayers": "Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres",
        "iwk": "IWK Health Centre — 5850 University Ave, Halifax",
        "clayton": "Clayton Park Medical Clinic — 278 Lacewood Dr",
        "bedford": "ScotiaMed — 955 Bedford Hwy, Bedford",
    }
    detected_location = next((v for k, v in loc_map.items() if k in full_lower), None)

    # ── Detect preferred day of week from current message ─────────────────────
    day_keywords = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    preferred_day = next((d for d in day_keywords if d in raw_lower), "")

    # ── Detect "next week <day>" — resolve to actual date ─────────────────────
    next_week_match = _re.search(
        r"next\s+week\s+(monday|tuesday|wednesday|thursday|friday)", raw_lower)
    resolved_slot = None
    if next_week_match:
        target_day = next_week_match.group(1)
        preferred_day = target_day
        day_num = ["monday","tuesday","wednesday","thursday","friday",
                   "saturday","sunday"].index(target_day)
        today = datetime.now()
        days_until = (day_num - today.weekday() + 7) % 7
        if days_until == 0: days_until = 7   # "next week" means at least 7 days away
        days_until += 7 if days_until < 7 else 0
        target_date = today + timedelta(days=days_until)
        resolved_slot = target_date.strftime("%Y-%m-%d 09:00")

    # ── Detect confirmed slot (affirmative selection, NOT a question) ──────────
    # First detect intent-to-browse / slot-request phrases — these are NEVER confirmations
    is_browsing = any(w in raw_lower for w in [
        "schedule", "show me", "let me know", "what time", "what are",
        "available", "any slot", "any time", "is there", "do you have",
        "are there", "no slot", "no slots", "not available", "don't have",
        "options", "show slots", "see slots", "what slots", "when can",
        "this week", "next week slots",
    ])
    is_question = raw_lower.strip().endswith("?") or is_browsing

    slot_patterns = [
        r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}',   # 2026-03-05 09:00
        r'(?:slot|option)\s*[1-6]',                  # slot 1 / option 2
        r'(?:march|feb|jan|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d+',  # March 5
    ]
    # slot pattern only counts as confirmation if NOT a browsing/question message
    slot_confirmed = (not is_question) and any(_re.search(p, raw_lower) for p in slot_patterns)
    slot_confirmed = slot_confirmed or bool(next_week_match and not is_browsing)
    slot_confirmed = slot_confirmed or ((not is_question) and any(w in raw_lower for w in
        ["yes please", "book it", "confirm", "that works", "please book", "go ahead", "i'll take",
         "sounds good", "perfect", "that one", "i'd like slot", "i'll take slot",
         "book slot", "book that", "i want slot"]))
    # Bare number reply (e.g. "1", "2 please", "number 3") — only if not browsing
    if not is_question and not slot_confirmed:
        bare_num = _re.match(r'^\s*(?:number\s*)?([1-6])(?:\s+please)?\s*$', raw_lower.strip())
        if bare_num:
            slot_confirmed = True

    # ── Extract patient name — multiple fallback sources ─────────────────────
    patient_name = (state.get("patient_name") or "").strip()

    if not patient_name:
        m = _re.search(r"Logged-in patient:\s*([^\]\n]+)", state.get("raw_input", ""))
        if m: patient_name = m.group(1).strip()

    if not patient_name:
        for msg in history:
            c = msg.get("content","") if isinstance(msg,dict) else str(msg)
            m = _re.search(r"PATIENT PROFILE\s*[—-]+\s*([^\n|]+)", c)
            if m:
                patient_name = m.group(1).strip()
                break

    if not patient_name:
        for msg in history:
            c = msg.get("content","") if isinstance(msg,dict) else str(msg)
            m = _re.search(r"Patient name:\s*([^\n|]+)", c)
            if m:
                patient_name = m.group(1).strip()
                break

    patient_name = patient_name or "Patient"

    # ── If slot confirmed AND we have type + location: actually SAVE the booking ─
    # Only save on first pass — second pass (hitl_api_action set) just confirms, no duplicate
    booked_apt = None
    already_reviewed = bool(state.get("hitl_api_action"))
    if slot_confirmed and detected_type and detected_location and not already_reviewed:
        # Priority 1: resolved natural language date (e.g. "next week Monday")
        # Priority 2: slot number selected (find it in the last agent message)
        # Priority 3: explicit date mentioned by patient
        # Priority 4: first date found in agent-offered slots in history
        slot = resolved_slot  # may be None

        if not slot:
            # Look for "slot N" or "option N" in patient message and find that slot in agent history
            slot_num_match = _re.search(r'(?:slot|option)\s*([1-6])', raw_lower)
            if slot_num_match:
                slot_num = int(slot_num_match.group(1)) - 1
                # Find the last agent message containing available slots
                for msg in reversed(history):
                    c = msg.get("content","") if isinstance(msg,dict) else str(msg)
                    role = msg.get("role","") if isinstance(msg,dict) else "agent"
                    if role in ("agent","assistant") or "Available slots" in c:
                        all_slots = _re.findall(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', c)
                        if all_slots and slot_num < len(all_slots):
                            slot = all_slots[slot_num]
                            break

        if not slot:
            # Look for explicit date/time in patient's current message only
            m = _re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', raw)
            if m: slot = m.group(1)

        if not slot:
            # Fall back: first slot from last agent message that listed slots
            for msg in reversed(history):
                c = msg.get("content","") if isinstance(msg,dict) else str(msg)
                role = msg.get("role","") if isinstance(msg,dict) else "agent"
                if role in ("agent","assistant"):
                    slots_found = _re.findall(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', c)
                    if slots_found:
                        slot = slots_found[0]
                        break

        if not slot:
            # Last resort: generate a slot matching preferred day
            available = get_available_slots(detected_type, 21, detected_location, preferred_day)
            slot = available[0] if available else datetime.now().strftime("%Y-%m-%d 09:00")

        result = book_appointment(
            patient_name=patient_name,
            apt_type=detected_type,
            slot=slot,
            location=detected_location,
        )
        booked_apt = result.get("appointment")

    # ── Build LLM prompt ────────────────────────────────────────────────────────
    locations_text = get_locations_for_type(detected_type) if detected_type else ""
    slots_text = ""
    if detected_location and not slot_confirmed:
        slots = get_available_slots(detected_type or "general", 21, detected_location, preferred_day)
        day_label = f" on {preferred_day.capitalize()}s" if preferred_day else ""
        slots_text = f"Available slots{day_label} at chosen location:\n" + "\n".join(
            f"  {i+1}. {s}" for i, s in enumerate(slots))
    elif not detected_location and not slot_confirmed and preferred_day:
        # Patient asked for a specific day but no location chosen yet — show locations first
        slots_text = f"Patient prefers {preferred_day.capitalize()} appointments. Show locations first, then slots."

    booking_confirmation = ""
    if booked_apt:
        booking_confirmation = (
            f"BOOKING SAVED SUCCESSFULLY:\n"
            f"  Confirmation ID: {booked_apt['id']}\n"
            f"  Type: {booked_apt['type']}\n"
            f"  Date/Time: {booked_apt['datetime']}\n"
            f"  Location: {booked_apt['location']}\n"
            f"  Patient: {booked_apt['patient_name']}\n"
            f"  Status: CONFIRMED\n\n"
            f"Tell the patient their booking is confirmed with these exact details."
        )

    prompt = "\n\n".join(filter(None, [
        f"Patient request: {raw}",
        booking_confirmation,
        types_text if not booked_apt else "",
        locations_text if not booked_apt else "",
        slots_text if not booked_apt else "",
    ]))

    try:
        response, count = _llm_invoke(
            [SystemMessage(content=BOOK_SYSTEM), HumanMessage(content=prompt)], state
        )
    except Exception:
        if booked_apt:
            response = (f"Your {booked_apt['type']} appointment has been confirmed!\n"
                       f"📅 Date/Time: {booked_apt['datetime']}\n"
                       f"📍 Location: {booked_apt['location']}\n"
                       f"🔖 Confirmation: {booked_apt['id']}\n"
                       f"Please bring your health card and referral.")
        else:
            response = f"I'd be happy to book an appointment!\n\n{types_text}\n\nWhich type do you need, and which location is most convenient for you?"
        count = state["call_count"]
    run_log.log("handle_book_appointment", "done", None)
    return {
        "draft_response": response,
        "call_count": count, "status": "READY",
        "route_path": state["route_path"] + ["handle_book_appointment"],
    }


# ─── EXTENDED: handle_check_status (no HITL) ─────────────────────────────────
STATUS_SYSTEM = """You are a friendly medical appointment coordinator.
The patient is asking about the status of their appointment.
Using the appointment data provided, give a clear, helpful status update.
Include appointment ID, type, date/time, provider, and current status.
IMPORTANT: Write only the final message text. Do NOT include stage directions, narration, or
phrases like "[After a brief pause]", "[pause]", "(a moment later)", or any bracketed actions.
Write as if you are sending a direct message to the patient — nothing else.
Do NOT give any medical advice."""

def node_handle_check_status(state: AppointmentState) -> dict:
    summary = get_appointments_summary()
    prompt = f"Patient request: {state.get('pii_masked_input') or state['raw_input']}\n\nAppointment records:\n{summary}"
    try:
        response, count = _llm_invoke(
            [SystemMessage(content=STATUS_SYSTEM), HumanMessage(content=prompt)], state
        )
    except Exception:
        response = f"Here is the current appointment status information:\n\n{summary}"
        count = state["call_count"]
    run_log.log("handle_check_status", "auto-answered", None)
    return {
        "draft_response": response, "final_response": response,
        "hitl_action": "auto-answered",
        "call_count": count, "status": "READY",
        "route_path": state["route_path"] + ["handle_check_status"],
    }


# ─── EXTENDED: handle_general_inquiry (no HITL) ───────────────────────────────
INQUIRY_SYSTEM = """You are a friendly medical clinic receptionist.
Answer the patient's general inquiry about the clinic using the information provided.
Be warm, concise, and helpful. Cover only what they asked about.
Do NOT give any medical advice or clinical information."""

def node_handle_general_inquiry(state: AppointmentState) -> dict:
    raw_text = state.get("pii_masked_input") or state["raw_input"]
    clinic_info = get_clinic_info(raw_text)
    prompt = f"Patient question: {raw_text}\n\nClinic information:\n{clinic_info}"
    try:
        response, count = _llm_invoke(
            [SystemMessage(content=INQUIRY_SYSTEM), HumanMessage(content=prompt)], state
        )
    except Exception:
        response = clinic_info
        count = state["call_count"]
    run_log.log("handle_general_inquiry", "auto-answered", None)
    return {
        "draft_response": response, "final_response": response,
        "hitl_action": "auto-answered",
        "call_count": count, "status": "READY",
        "route_path": state["route_path"] + ["handle_general_inquiry"],
    }


# ─── SAFETY: handle_emergency ─────────────────────────────────────────────────
def node_handle_emergency(state: AppointmentState) -> dict:
    """Clearly life-threatening — skip triage, go straight to 911 card."""
    run_log.log("handle_emergency", "triggered",
                "moderation" if state.get("moderation_flagged") else "intent")
    draft = "TRIAGE_CALL_999|||Life-threatening emergency detected.|||Call 911 immediately.|||None"
    return {
        "draft_response": draft, "final_response": draft,
        "status": "ESCALATE", "hitl_action": "auto-escalated",
        "route_path": state["route_path"] + ["handle_emergency"],
    }


# ─── TRIAGE: assess symptom severity using patient health profile ─────────────
TRIAGE_SYSTEM = """You are a medical triage assistant for a hospital appointment booking system.
A patient has reported a symptom or health concern. Assess severity using BOTH their message AND health profile.

SEVERITY LEVELS — pick exactly one:

  CALL_999   : Life-threatening right now. Call 911 / ambulance immediately.
  GO_ED      : Serious — go to Emergency Department today. Do not wait.
  URGENT_CARE: Needs attention within 24 hours. Walk-in clinic or call 811 today.
  MONITOR    : Mild symptom — safe to manage at home. Offer to book appointment.

─── ALWAYS CALL_999 — these are life-threatening: ──────────────────────────────
  Heart attack signs: chest pain/pressure/tightness + arm, jaw, or shoulder pain, sweating, nausea
  Stroke (FAST): Face drooping, Arm weakness, Speech difficulty, Time to call 911
  Anaphylaxis: throat/tongue swelling + hives + breathing difficulty after exposure
  Severe breathing difficulty: can't speak in full sentences, lips turning blue
  Uncontrolled major bleeding: bleeding that won't stop after 10 min pressure
  Loss of consciousness / unresponsive
  Active seizure lasting >5 minutes or repeated seizures
  Suspected overdose (drugs, alcohol, medication)
  Severe burns covering large body area or face/airway
  Suicidal with specific plan or intent to act now
  Drowning, choking, near-suffocation
  Suspected spinal/neck injury after trauma

─── ALWAYS GO_ED — serious but not immediate 911: ──────────────────────────────
  Seizure that has now stopped (first-time or changed pattern)
  Suspected broken bone / dislocation
  Deep wound likely needing stitches
  High fever (>39°C / 102°F) with confusion or stiff neck
  Sudden severe "thunderclap" headache — worst of life
  Chest pain not meeting CALL_999 criteria
  Moderate breathing difficulty
  Severe abdominal pain with rigid abdomen
  Leg pain + swelling + shortness of breath (DVT/PE concern)
  Vision changes + headache together
  Head injury with confusion, vomiting, or loss of consciousness
  Psychiatric crisis — not immediate self-harm risk but needs assessment

─── ALWAYS URGENT_CARE — needs same-day care: ──────────────────────────────────
  High fever (>38.5°C / 101°F) without confusion — adults
  Suspected UTI with fever
  Ear infection with severe pain
  Pink eye with vision changes
  Minor laceration possibly needing stitches
  Moderate pain not controlled by over-the-counter medication

─── PROFILE ESCALATION — upgrade level based on medical history: ────────────────
  Diabetes + dizziness / confusion / shaking / sweating    → GO_ED (hypoglycemia risk)
  Diabetes + chest pain / pressure                         → CALL_999
  Diabetes + very high blood sugar symptoms (extreme thirst, confusion) → GO_ED
  Heart disease / pacemaker + chest discomfort / palpitations / fainting → CALL_999
  Hypertension + sudden severe headache + vision changes   → GO_ED (hypertensive crisis)
  Hypertension + chest pain                                → CALL_999
  Blood thinners (warfarin/rivaroxaban/aspirin) + any bleeding → GO_ED
  Kidney disease + severe swelling / shortness of breath / no urine → GO_ED
  Asthma/COPD + breathing difficulty not relieved by inhaler → CALL_999
  Pregnant + severe headache / blurred vision / abdominal pain → CALL_999 (preeclampsia)
  Pregnant + any vaginal bleeding                          → GO_ED
  Cancer / immunocompromised + fever ≥38.5°C               → GO_ED (neutropenic sepsis)
  Known severe allergy (anaphylaxis history) + any allergic symptoms → CALL_999
  Elderly (70+) + fall / head injury / sudden confusion    → GO_ED
  Mental health condition + expressing suicidal thoughts   → GO_ED

─── SYMPTOM COMBINATIONS — always escalate these pairs: ────────────────────────
  Headache + fever + stiff neck                            → CALL_999 (meningitis)
  Headache + sudden onset described as worst ever          → CALL_999 (subarachnoid bleed)
  Chest pain + shortness of breath + sweating              → CALL_999
  Confusion + fever                                        → GO_ED
  Leg swelling + shortness of breath                       → GO_ED (DVT/PE)
  Abdominal pain + rigid/board-like abdomen                → GO_ED
  Any symptom + near-fainting / can't stand / collapse     → GO_ED
  Vomiting + headache + sensitivity to light               → GO_ED
  Rash + fever + joint pain                                → URGENT_CARE

─── SINGLE MILD SYMPTOMS → MONITOR (if no risk factors): ──────────────────────
  Mild headache alone, mild nausea, fatigue, common cold/flu,
  minor backache, sore throat, mild dizziness alone, mild stomach upset,
  minor skin irritation, mild anxiety, general tiredness.
  For these → offer home advice + offer to book appointment.

Respond ONLY with this exact JSON (no markdown, no extra text):
{
  "level": "CALL_999|GO_ED|URGENT_CARE|MONITOR",
  "reason": "one sentence clinical reason",
  "symptom_summary": "brief description of what patient reported",
  "risk_factor": "name the health profile condition that raised severity, or null",
  "home_advice": "for MONITOR level only — 1-2 practical self-care tips, else null",
  "recommendation": "for URGENT_CARE level only — specific Halifax clinic suggestion, else null"
}"""


def node_handle_triage(state: AppointmentState) -> dict:
    """Assess symptom severity using the patient health profile, route to appropriate response."""
    import json as _json
    raw = state.get("pii_masked_input") or state["raw_input"]

    # Extract health profile — prefer raw_input injection (most reliable), fall back to history
    import re as _re_t
    profile_text = ""

    # Check raw_input for [Patient Health Profile] block (injected by server)
    raw_full = state.get("raw_input", "")
    ph_match = _re_t.search(r"\[Patient Health Profile\]\n(.*?)(?=\[|$)", raw_full, _re_t.DOTALL)
    if ph_match:
        profile_text = ph_match.group(1).strip()

    # Fall back to conversation history
    if not profile_text:
        history = state.get("conversation_history", [])
        for msg in history:
            c = msg.get("content", "") if isinstance(msg, dict) else str(msg)
            if "PATIENT PROFILE" in c or "Medical conditions" in c:
                profile_text = c
                break

    profile_block = f"Patient health profile:\n{profile_text}" if profile_text else "No health profile provided."
    triage_prompt = f"{profile_block}\n\nPatient current message: {raw}"
    run_log.log("handle_triage", "assessing", raw[:80])

    try:
        triage_raw, count = _llm_invoke(
            [SystemMessage(content=TRIAGE_SYSTEM), HumanMessage(content=triage_prompt)],
            state, skip_context_edit=True
        )
        clean = triage_raw.strip()
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"): clean = clean[4:]
        result = _json.loads(clean.strip())
        level = result.get("level", "MONITOR")
    except Exception as e:
        run_log.log("handle_triage", "parse_error", str(e))
        result = {
            "level": "MONITOR",
            "reason": "Could not fully assess — defaulting to monitor",
            "symptom_summary": raw,
            "home_advice": "Rest and stay hydrated. If symptoms worsen, visit the nearest ED.",
        }
        level = "MONITOR"
        count = state["call_count"]

    reason   = result.get("reason", "")
    summary  = result.get("symptom_summary", raw)
    risk     = result.get("risk_factor", "")
    advice   = result.get("home_advice", "")
    rec      = result.get("recommendation", "")

    sep = "|||"
    if level == "CALL_999":
        draft = f"TRIAGE_CALL_999{sep}{reason}{sep}{summary}{sep}{risk}"
        status = "ESCALATE"
    elif level == "GO_ED":
        draft = f"TRIAGE_GO_ED{sep}{reason}{sep}{summary}{sep}{risk}"
        status = "ESCALATE"
    elif level == "URGENT_CARE":
        draft = f"TRIAGE_URGENT{sep}{reason}{sep}{summary}{sep}{rec}"
        status = "READY"
    else:
        draft = f"TRIAGE_MONITOR{sep}{reason}{sep}{summary}{sep}{advice}"
        status = "READY"

    run_log.log("handle_triage", level, reason)
    return {
        "draft_response": draft, "final_response": draft,
        "status": status,
        "hitl_action": "auto-answered",
        "call_count": count,
        "route_path": state["route_path"] + ["handle_triage"],
    }


# ─── FALLBACK: handle_unknown ─────────────────────────────────────────────────
def node_handle_unknown(state: AppointmentState) -> dict:
    run_log.log("handle_unknown", "triggered", None)
    draft = (
        "Thank you for reaching out to our appointment centre. "
        "I wasn't able to fully understand your request.\n\n"
        "I can help you with:\n"
        "• Rescheduling or cancelling an appointment\n"
        "• Preparation instructions for imaging or procedures\n"
        "• Viewing your current appointments\n"
        "• Booking a new appointment\n"
        "• Checking appointment status\n"
        "• Clinic hours, location, parking, and contact information\n\n"
        "Could you please clarify what you need?"
    )
    return {
        "draft_response": draft, "final_response": draft,
        "status": "NEED_INFO", "hitl_action": "auto-need-info",
        "route_path": state["route_path"] + ["handle_unknown"],
    }


# ─── Node: hitl_review ────────────────────────────────────────────────────────
def node_hitl_review(state: AppointmentState) -> dict:
    if state.get("hitl_api_action"):
        action, final = hitl_mw.review_api(
            draft=state.get("draft_response") or "",
            action=state["hitl_api_action"],
            edited_text=state.get("hitl_api_edit"),
        )
        status = "ESCALATE" if action == "escalated" else state.get("status", "READY")
        run_log.log("hitl_review", f"api:{action}", None)
        return {
            "hitl_action": action, "final_response": final,
            "hitl_pending": False, "status": status,
            "route_path": state["route_path"] + ["hitl_review"],
        }
    # CLI mode
    action, final = hitl_mw.review_cli(state["draft_response"])
    status = "ESCALATE" if action == "escalated" else state.get("status", "READY")
    run_log.log("hitl_review", f"cli:{action}", None)
    return {
        "hitl_action": action, "final_response": final, "status": status,
        "route_path": state["route_path"] + ["hitl_review"],
    }


def edge_needs_hitl(state: AppointmentState) -> str:
    """Route to HITL or finalize.
    
    API mode (server sets api_mode=True):
      - First pass:  no hitl_api_action yet → skip hitl_review, stop at finalize with draft
      - Second pass: hitl_api_action is set → go through hitl_review then finalize
    CLI mode (api_mode not set):
      - Always goes through hitl_review (blocks terminal)
    """
    if state.get("final_response"):
        return "finalize"
    if state.get("intent") in HITL_INTENTS:
        if state.get("api_mode") and not state.get("hitl_api_action"):
            # API first pass: return draft without HITL, server will pause
            return "finalize"
        return "hitl_review"
    return "finalize"


# ─── Node: finalize ───────────────────────────────────────────────────────────
def node_finalize(state: AppointmentState) -> dict:
    # API first pass: if HITL intent but no review yet, don't set final_response
    # This keeps final_response=None so second pass knows to go through hitl_review
    intent = state.get("intent")
    is_api_first_pass = (
        state.get("api_mode")
        and intent in HITL_INTENTS
        and not state.get("hitl_api_action")
        and state.get("hitl_action") not in ("auto-escalated", "auto-need-info")
        and state.get("status") not in ("ESCALATE", "NEED_INFO")
    )
    if is_api_first_pass:
        # Return without setting final_response — server will pause here
        run_log.log("finalize", "awaiting_hitl", None)
        run_log.flush()
        return {"route_path": state["route_path"] + ["finalize"]}

    final = state.get("final_response") or state.get("draft_response", "")
    pii_map = state.get("pii_map") or {}
    if pii_map:
        final = pii_mw.unmask(final, pii_map)
    run_log.log("finalize", state.get("status", "READY"), None)
    run_log.flush()
    return {"final_response": final, "route_path": state["route_path"] + ["finalize"]}


# ─── Graph assembly ───────────────────────────────────────────────────────────
def build_graph():
    g = StateGraph(AppointmentState)

    nodes = {
        "init_run":                  node_init_run,
        "pii_filter":                node_pii_filter,
        "moderation_check":          node_moderation_check,
        "intent_classifier":         node_intent_classifier,
        "handle_reschedule":         node_handle_reschedule,
        "handle_cancel":             node_handle_cancel,
        "handle_prep":               node_handle_prep,
        "handle_view_appointments":  node_handle_view_appointments,
        "handle_book_appointment":   node_handle_book_appointment,
        "handle_check_status":       node_handle_check_status,
        "handle_general_inquiry":    node_handle_general_inquiry,
        "handle_emergency":          node_handle_emergency,
        "handle_triage":             node_handle_triage,
        "handle_unknown":            node_handle_unknown,
        "hitl_review":               node_hitl_review,
        "finalize":                  node_finalize,
    }
    for name, fn in nodes.items():
        g.add_node(name, fn)

    g.set_entry_point("init_run")
    g.add_edge("init_run",   "pii_filter")
    g.add_edge("pii_filter", "moderation_check")

    g.add_conditional_edges(
        "moderation_check", edge_after_moderation,
        {"intent_classifier": "intent_classifier", "handle_emergency": "handle_emergency", "handle_triage": "handle_triage", "hitl_review": "hitl_review"},
    )
    g.add_conditional_edges(
        "intent_classifier", edge_route_intent,
        {
            "handle_reschedule":        "handle_reschedule",
            "handle_cancel":            "handle_cancel",
            "handle_prep":              "handle_prep",
            "handle_view_appointments": "handle_view_appointments",
            "handle_book_appointment":  "handle_book_appointment",
            "handle_check_status":      "handle_check_status",
            "handle_general_inquiry":   "handle_general_inquiry",
            "handle_emergency":         "handle_emergency",
            "handle_triage":            "handle_triage",
            "handle_unknown":           "handle_unknown",
        },
    )

    all_handlers = [
        "handle_reschedule", "handle_cancel", "handle_prep",
        "handle_view_appointments", "handle_book_appointment",
        "handle_check_status", "handle_general_inquiry",
        "handle_emergency", "handle_triage", "handle_unknown",
    ]
    for h in all_handlers:
        g.add_conditional_edges(
            h, edge_needs_hitl,
            {"hitl_review": "hitl_review", "finalize": "finalize"},
        )

    g.add_edge("hitl_review", "finalize")
    g.add_edge("finalize", END)

    return g.compile()


appointment_graph = build_graph()