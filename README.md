# MedSchedule AI
**Minh Dam - MBAN 5510 Final Project · Saint Mary's University · Sobey School of Business**

A middleware-driven appointment assistant built with LangGraph and GPT-4o. Patients check in, chat with an AI agent, and receive staff-reviewed responses — with intelligent triage for symptom escalation.

---

## Demo Video
**LinkedIn:** https://www.linkedin.com/feed/update/urn:li:ugcPost:7432497461941899264/

The demo shows all the usage of this system: book/cancel/reschedule appointment, prep instructions, genereal inquiry and escalation. 

---

## Setup

**Requirements:** Python 3.11+, [uv](https://docs.astral.sh/uv/), OpenAI API key (gpt-4o)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone <your-repo-url>
cd appointment-agent
uv sync

# Configure environment
cp .env.example .env
# Add your OPENAI_API_KEY to .env
```

**.env file:**
```env
OPENAI_API_KEY=sk-...your-key...
OPENAI_MODEL=gpt-4o
OPENAI_FALLBACK_MODEL=gpt-3.5-turbo
LANGGRAPH_TRACE=false
```

> ⚠️ Never commit `.env` — it is in `.gitignore`

---

## Running the Application

**Web UI (recommended):**
```bash
uv run python server.py
```

| Portal | URL |
|---|---|
| Patient Portal | `http://localhost:8000` |
| Staff Review Portal | `http://localhost:8000/staff` |

**CLI:**
```bash
uv run python cli.py                                                        # interactive
uv run python cli.py --message "How do I prepare for my CT scan?"          # single message
uv run python cli.py --message "I have severe chest pain"                  # escalation
uv run python cli.py --message "Cancel my appointment" --json              # JSON output
uv run python cli.py --demo                                                 # all scenarios, auto-approved HITL
```

**Expected output — normal run:**
```
╭─────────────────────────────╮
│  Terminal Status:  READY    │
╰─────────────────────────────╯

 Field        │ Value
──────────────┼──────────────────────────────────────────────────────────────
 Run ID       │ 4A3F2B1C
 Timestamp    │ 2026-02-25T10:14:22Z
 Intent       │ prep_instructions
 Route Path   │ init_run → pii_filter → moderation_check →
              │ intent_classifier → handle_prep → hitl_review → finalize
 HITL Action  │ approved
 LLM Calls    │ 2
 PII Detected │ No
 Mod Flagged  │ No

╭─ Final Response ─────────────────────────────────────────────────╮
│ Here is how to prepare for your CT scan...                        │
╰───────────────────────────────────────────────────────────────────╯
```

**Expected output — escalation run:**
```
╭──────────────────────────────────╮
│  Terminal Status:  ESCALATE      │
╰──────────────────────────────────╯

 Route Path   │ init_run → pii_filter → moderation_check →
              │ handle_emergency → finalize
 HITL Action  │ auto-escalated
```

---

## Architecture

```
Patient Message
      │
      ▼
init_run → pii_filter → moderation_check
                               │
               ┌───────────────┴──────────────────┐
               ▼                                  ▼
       handle_emergency                  intent_classifier
       (instant CALL_999)                         │
                              ┌───────────────────┤
                              │  HITL intents:    │  Auto intents:
                              │  reschedule       │  view_appointments
                              │  cancel           │  check_status
                              │  prep_instructions│  general_inquiry
                              │  book_appointment │  triage → handle_triage
                              └────────┬──────────┘
                                       │
                                  hitl_review
                                       │
                                    finalize
                                       │
                              READY | NEED_INFO | ESCALATE
```

**Terminal statuses:**

| Status | Meaning |
|---|---|
| `READY` | Response processed and delivered |
| `NEED_INFO` | Unclear request — patient asked to clarify |
| `ESCALATE` | Emergency, moderation flag, staff escalation, or call limit breach |

---

## HITL Workflow

Action intents (`reschedule`, `cancel`, `prep_instructions`, `book_appointment`) pause after draft generation for staff review. All other intents auto-answer instantly.

```
[Pass 1] Draft generated → patient sees "being reviewed..."
                │
        Staff sees draft in /staff portal
                │
     ┌──────────┼──────────┐
  Approve     Edit       Escalate
     └──────────┘
[Pass 2] Final response delivered to patient
```

- **CLI:** Terminal prompts `[A]pprove / [E]dit / E[x]calate`
- **Web UI:** Staff portal shows draft with Approve, Edit, and Escalate buttons

---

## Middleware Stack

Each component is a dedicated LangGraph node or called inside `_llm_invoke()`. All components are implemented in `src/middleware/`.

| # | Middleware | Where in graph | Role | Status |
|---|---|---|---|---|
| 1 | **PIIMiddleware** | `pii_filter` node | Masks phone/email/health card before LLM. Restores in `finalize` via `pii_map` in state. | ✅ Active |
| 2 | **ModerationMiddleware** | `moderation_check` node | OpenAI Moderation API. Flagged input bypasses intent classifier → emergency. | ✅ Active |
| 3 | **CallLimitMiddleware** | Inside `_llm_invoke()` | Max 6 LLM calls per run. Breach → `RuntimeError` → ESCALATE. | ✅ Active |
| 4 | **HumanInTheLoopMiddleware** | `hitl_review` node | Two-pass: draft on Pass 1, staff action triggers Pass 2 via `hitl_api_action` state field. | ✅ Active |
| 5 | **ModelRetryMiddleware** | Inside `_llm_invoke()` | Retries LLM up to 3× with 1.5× exponential backoff before fallback. | ✅ Active |
| 6 | **ModelFallbackMiddleware** | Inside `_llm_invoke()` | GPT-4o failure → GPT-3.5-turbo. Model names from `.env`. | ✅ Active |
| 7 | **ContextEditingMiddleware** | Inside `_llm_invoke()` | Trims history to 3000 tokens. Injects system prompt. Skipped for intent classifier. | ✅ Active |
| 8 | **SummarizationMiddleware** | `summarization.py` | Summarizes long histories. Implemented — not activated; ContextEditingMiddleware handles token limits. | ⚙️ Implemented |
| 9 | **SubAgentMiddleware** | `subagent.py` | Delegates sub-tasks to a focused agent. Implemented — not activated in current single-agent flow. | ⚙️ Implemented |

---

## Patient Check-In & Personalization

Patients check in with a 2-step form before chatting.

**Step 1 — Basic Info:** Name *(required)*, DOB, NS Health Card, Phone

**Step 2 — Health Profile:** Conditions, medications, allergies, surgeries, family history, implants, language

The profile is injected as a `[Patient Health Profile]` block into every agent request so all nodes can personalize responses. Examples:

- Iodine allergy + CT scan → contrast agent warning
- Metformin + CT with contrast → hold medication 48h reminder
- Pacemaker + MRI → safety flag for radiology team
- Diabetes + dizziness → triage escalates from MONITOR to GO_ED

---

## Symptom Triage

When a patient reports symptoms, the triage engine assesses severity using their health profile:

| Level | Colour | Examples | Patient sees |
|---|---|---|---|
| 🚨 CALL_911 | Red | Stroke, heart attack, anaphylaxis | 911 button + ED links |
| 🏥 GO_ED | Orange | Seizure, severe pain, profile escalation | ED directions |
| ⏰ URGENT_CARE | Yellow | High fever, UTI with fever | Walk-in clinic links |
| ✅ MONITOR | Green | Mild symptoms | Self-care advice |

---

## Test Cases

**Check in as Minh Dam** — Conditions: Type 2 Diabetes, Hypertension · Meds: Metformin, Lisinopril · Allergies: Iodine contrast, Penicillin

| Input | Expected |
|---|---|
| "How do I prepare for my CT scan?" | Iodine contrast warning + hold Metformin 48h |
| "I feel dizzy and shaky" | 🏥 GO_ED — hypoglycemia risk |
| "I have chest pain" | 🚨 CALL_999 — diabetes + hypertension escalation |
| Book a CT scan | Allergy warning in confirmation |
| "Show my appointments" | Only Minh Dam's bookings |

**Check in as Jane Smith** — seed patient with Brain MRI, Neurology consult, Blood work

| Input | Expected |
|---|---|
| "Show my appointments" | Lists all 3 appointments |
| "What do I need to bring?" | Bring MRI results to neurology consult |

---

## Running Tests

```bash
uv run pytest tests/ -v
```

Covers: PII masking/restoration, call limit enforcement, HITL approve/edit/escalate, appointment CRUD, prep instruction lookup.

---

## Project Structure

```
appointment-agent/
├── server.py                   # FastAPI server
├── cli.py                      # CLI entry point
├── pyproject.toml              # Dependencies
├── .env.example                # Environment template
├── src/
│   ├── agents/graph.py         # LangGraph workflow — all nodes, edges, prompts
│   ├── middleware/
│   │   ├── pii.py
│   │   ├── moderation.py
│   │   ├── call_limits.py
│   │   ├── hitl.py
│   │   ├── retry.py
│   │   ├── fallback.py
│   │   ├── context_editing.py
│   │   ├── summarization.py
│   │   └── subagent.py
│   ├── tools/appointment_tools.py   # In-memory EHR mock
│   └── utils/logger.py              # PII-safe run logger
├── static/
│   ├── patient/index.html      # Patient portal
│   └── staff/index.html        # Staff HITL portal
├── tests/test_middleware.py
└── data/test_scenarios.json
```

---

## Design Decisions

**Middleware as nodes** — each concern is a dedicated LangGraph node or called inside `_llm_invoke()`, making the execution path fully traceable and each component independently testable.

**Two-tier routing** — action intents require HITL; informational intents auto-answer. Balances speed with safety oversight.

**Triage vs emergency** — `emergency` gives an instant 911 card. `triage_needed` runs a full LLM assessment with the health profile to prevent both under-reaction and over-triggering.

**Health profile in raw_input** — injected on every request so all nodes always have it, regardless of how much conversation history has been trimmed.

**PII scope** — masked before any LLM call, restored only after HITL in `finalize`. Staff see masked tokens by design.

**Duplicate booking prevention** — HITL intents run twice (draft + approval). A state guard and a data-layer guard both prevent duplicate records.

**Mock EHR** — `appointment_tools.py` is in-memory. In production, replace with REST calls to a real scheduling API.

**No clinical advice** — all prompts explicitly block diagnoses. Emergency and triage responses direct patients to 911, ED, or Health811.

---

## Dependencies

| Package | Purpose |
|---|---|
| `langgraph` | Stateful workflow |
| `langchain`, `langchain-openai` | LLM integration |
| `openai` | GPT-4o + Moderation API |
| `fastapi`, `uvicorn` | Web server |
| `pydantic` | Validation |
| `python-dotenv` | Environment variables |
| `rich`, `typer` | CLI formatting |

---

## Constraints Checklist

- [x] Secrets in environment variables — no keys in code
- [x] No clinical advice — all prompts explicitly blocked
- [x] Emergency directs to 911 / ED / Health811
- [x] PII masked before LLM, restored after HITL
- [x] Logs mask sensitive values
- [x] HITL pauses for review — final output reflects approve/edit/escalate
- [x] Each run produces run ID, timestamp, terminal status, and route path
- [x] All middleware documented with LangGraph integration
- [x] Health profile personalization across all intents
- [x] Patient appointment isolation — exact name match only

---

*Minh Dam - MBAN 5510 — Agentic AI · Saint Mary's University, Sobey School of Business*
