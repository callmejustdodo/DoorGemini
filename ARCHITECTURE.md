# AI Doorbell — Architecture Document

> Extracted from PRD v2.0 | March 2026
> Revised after RALPLAN consensus review

---

## 1. System Overview

AI Doorbell is a semi-autonomous doorbell concierge powered by the Gemini Live API. A phone camera simulates the doorbell hardware, while a FastAPI backend on Cloud Run orchestrates real-time AI conversation, multi-source verification, and homeowner notifications.

```
┌──────────────┐         ┌─────────────────────────────────────┐
│  Phone       │         │       Google Cloud (Cloud Run)       │
│  (Camera +   │ WebSocket│                                     │
│   Mic +      │────────▶│  FastAPI Backend                    │
│   Speaker)   │◀────────│    │                                │
│              │  Audio   │    ├── Gemini Live API session      │
│  = Doorbell  │  back    │    │   (video+audio in, audio out)  │
│    simulator │         │    │                                │
└──────────────┘         │    ├── Tool Handlers:               │
                          │    │   ├── Gmail API               │
┌──────────────┐         │    │   ├── Google Calendar API      │
│  Owner's     │ Telegram │    │   ├── Known Faces DB (JSON)   │
│  Phone       │◀────────│    │   ├── Telegram Bot API         │
│  (Telegram)  │────────▶│    │   └── Photo Capture            │
│              │ Commands │    │       + Cloud Storage          │
└──────────────┘         │    │                                │
                          │    └── google-genai SDK             │
                          └─────────────────────────────────────┘
```

---

## 2. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Vanilla HTML/JS (single page) | Camera feed + subtitle UI, served as static file from FastAPI |
| Camera/Audio | WebRTC MediaStream API | Browser webcam + microphone capture |
| Real-time Comm | WebSocket (binary frames) | Frontend ↔ backend bidirectional streaming |
| Backend | FastAPI (Python) | Deployed on Cloud Run |
| AI Core | Gemini Live API | Real-time bidirectional video + audio. Model: `gemini-2.5-flash-native-audio-preview-12-2025` |
| AI SDK | `google-genai` (Python) | Direct SDK for Live API sessions + tool dispatch |
| Storage | Google Cloud Storage | Screenshots, logs |
| Notifications | Telegram Bot API | Homeowner alerts + bidirectional commands |
| IaC / Deployment | Terraform + Cloud Build | Cloud Run, Cloud Storage, IAM, networking |

**Note**: ADK is not used. The `google-genai` SDK provides direct Live API session management via `client.aio.live.connect()` with built-in tool calling support. This avoids an unverified abstraction layer and keeps the stack minimal for a 3-day hackathon.

---

## 3. Data Flow

```
 1. Phone browser → getUserMedia() → video + audio stream
 2. WebSocket binary frames sent to Cloud Run backend
 3. Backend → Gemini Live API via google-genai SDK (bidirectional)
 4. Gemini analyzes video + audio, generates voice response
 5. Gemini triggers tool calling (Gmail/Calendar/FacesDB/Telegram)
 6. Backend executes tools and returns results to Gemini
 7. Gemini reflects tool results and continues conversation
 8. Voice response → WebSocket → phone speaker playback
 9. Telegram Bot API → sends alert to homeowner
10. Homeowner's Telegram response → webhook → injected as context into Gemini session
```

---

## 4. Streaming Flow

```
Frontend (phone browser)              Backend (Cloud Run)              Gemini Live API
     │                                      │                                │
     │── video frames (WebSocket) ─────────▶│── send_realtime_input(video) ─▶│
     │── audio PCM 16kHz (WebSocket) ──────▶│── send_realtime_input(audio) ─▶│
     │                                      │                                │
     │                                      │◀── audio PCM 24kHz ───────────│
     │◀── audio playback (WebSocket) ───────│                                │
     │                                      │                                │
     │                                      │◀── input_transcription ───────│
     │◀── subtitle: visitor (WebSocket) ────│                                │
     │                                      │◀── output_transcription ──────│
     │◀── subtitle: AI (WebSocket) ─────────│                                │
     │                                      │                                │
     │                                      │◀── tool_call: check_gmail ────│
     │                                      │── tool_response ─────────────▶│
     │                                      │                                │
     │                                      │◀── tool_call: send_telegram ──│
     │◀── notification update (WebSocket) ──│── Telegram Bot API ──▶ Owner  │
     │                                      │                                │
     │                                      │◀── owner command (webhook) ────│
     │                                      │── send_realtime_input(text) ──▶│
     │                                      │◀── audio response ────────────│
     │◀── audio playback (WebSocket) ───────│                                │
```

---

## 5. WebSocket Binary Protocol

The phone ↔ backend WebSocket uses binary frames with a 1-byte type prefix:

### Client → Server

| Prefix | Type | Payload |
|---|---|---|
| `0x01` | Audio | Raw PCM 16-bit, 16kHz, mono |
| `0x02` | Video | JPEG frame (quality ~0.5, 5 FPS) |
| `0x03` | Control | UTF-8 JSON: `{"action": "start"\|"stop"}` |

### Server → Client

| Prefix | Type | Payload |
|---|---|---|
| `0x01` | Audio | Raw PCM 16-bit, 24kHz (from Gemini) |
| `0x03` | Control | UTF-8 JSON (see below) |

Control message types:
```json
{"type": "subtitle", "text": "...", "speaker": "ai"|"visitor"}
{"type": "notification", "data": { ... Notification object ... }}
{"type": "status", "status": "idle"|"active"|"caution"}
```

---

## 6. Agent Design

```
DoorbellAgent (google-genai Live API session via gemini_session.py)
├── Model: gemini-2.5-flash-native-audio-preview-12-2025
├── Input: Real-time video + audio stream
├── Output: Audio responses
├── Transcription: input_transcription + output_transcription enabled
├── Session Config:
│   ├── response_modalities: [AUDIO]  (TEXT and AUDIO cannot coexist)
│   ├── context_window_compression: enabled (for sessions > 2 min)
│   └── session_resumption: enabled (handle connection resets)
└── Tools:
    ├── check_gmail_orders   — Match delivery with Gmail order history
    ├── check_calendar       — Verify visitor against today's appointments
    ├── check_known_faces    — Look up visitor in registered acquaintance DB
    ├── send_telegram_alert  — Send summary + photo to homeowner (inline formatting)
    └── capture_screenshot   — Capture current frame to Cloud Storage
```

### Session Limits (Critical)

| Limit | Value | Mitigation |
|---|---|---|
| Audio + video session | ~2 min without compression | Enable `context_window_compression` in `LiveConnectConfig` |
| Connection lifetime | ~10 min | Implement session resumption; reconnect before timeout |
| Response modality | AUDIO **or** TEXT, not both | Use AUDIO only; subtitles via `output_transcription` |
| `send_realtime_input` | Use `audio=` and `video=` keys separately | Never use `media=` key (deprecated) |
| Mic pause | Send `audioStreamEnd` signal | Required per best practices when mic is paused |

### Visitor Classification Flow

```
Visitor arrives
     │
     ▼
 AI initiates conversation
     │
     ▼
 Visitor states purpose
     │
     ├── "Delivery" ──────────▶ check_gmail_orders()
     │                              │
     │                         Match found? ──Yes──▶ ✅ Verified delivery (low urgency)
     │                              │
     │                             No ──────────────▶ ⚠️ Suspicious (high urgency)
     │
     ├── States a name ───────▶ check_known_faces() + check_calendar()
     │                              │
     │                         Match found? ──Yes──▶ ✅ Known person (low urgency)
     │                              │
     │                             No ──────────────▶ ❓ Unknown (medium urgency)
     │
     └── Evasive / unclear ───▶ capture_screenshot()
                                    │
                                    ▼
                               ⚠️ Suspicious (high urgency)
                                    │
                                    ▼
                          send_telegram_alert() [always called]
```

---

## 7. Gemini Live API Specs

| Parameter | Value |
|---|---|
| Audio input | Raw 16-bit PCM, 16kHz, mono |
| Audio output | Raw 16-bit PCM, 24kHz |
| Protocol | WebSocket (stateful) |
| Features | Voice Activity Detection, barge-in, tool calling, affective dialog |
| Session | Stateful — remembers all conversation within session |
| Model | `gemini-2.5-flash-native-audio-preview-12-2025` |
| SDK | `google-genai` via `client.aio.live.connect()` |
| Transcription | `input_transcription` + `output_transcription` for subtitles |
| Compression | `context_window_compression` for sessions > 2 min |

---

## 8. API Endpoints

```
# WebSocket (real-time streaming)
WS  /ws/doorbell           → Doorbell stream (binary protocol, see Section 5)

# REST
POST /api/doorbell/start    → Start doorbell session
POST /api/doorbell/stop     → Stop doorbell session
GET  /api/notifications     → Notification history
POST /api/owner/command     → Relay homeowner command (Telegram webhook)
GET  /api/config            → Get configuration
PUT  /api/config            → Update configuration

# Static
GET  /                      → Serve frontend (index.html)
GET  /static/*              → Static assets (JS, CSS)
```

---

## 9. Data Models

```python
from pydantic import BaseModel
from datetime import datetime

class Notification(BaseModel):
    id: str
    timestamp: datetime
    visitor_type: str      # delivery, known_person, unknown, suspicious
    urgency: str           # low, medium, high
    summary: str           # "📦 Delivery arrived — Amazon [product name]"
    screenshot_url: str | None
    conversation_transcript: list[dict]
    owner_action: str | None  # let_in, wait, decline, None

class DoorbellSession(BaseModel):
    id: str
    status: str            # idle, active, ended
    started_at: datetime | None
    ended_at: datetime | None
    notifications: list[Notification]

class DoorbellConfig(BaseModel):
    owner_name: str
    language: str          # en, ko
    delivery_instructions: str
    known_faces: list[dict]
    # [{"name": "Minsu", "relation": "friend", "memo": "college classmate"}]

class KnownPerson(BaseModel):
    name: str
    relation: str
    memo: str | None
```

---

## 10. Cloud Infrastructure (Terraform)

### Directory Structure

```
infra/
├── main.tf              # Provider config, backend (GCS remote state)
├── variables.tf         # Input variables
├── outputs.tf           # Output values (service URL, bucket name)
├── cloud_run.tf         # Cloud Run service
├── cloud_storage.tf     # GCS bucket for screenshots
├── iam.tf               # Service accounts, permissions
├── secrets.tf           # Secret Manager for API keys
├── artifact_registry.tf # Container image registry
└── terraform.tfvars.example
```

### Resource Map

```
Google Cloud Project
│
├── Artifact Registry
│   └── ai-doorbell/backend          ← Docker image repository
│
├── Cloud Run
│   └── ai-doorbell-service          ← FastAPI backend + static frontend
│       ├── Service Account (least-privilege)
│       ├── Secret references (Telegram token, OAuth creds)
│       ├── session_affinity = true (WebSocket stickiness)
│       ├── timeout = 300s (long conversations)
│       ├── max_instance_request_concurrency = 1
│       └── Public invoker IAM (for Telegram webhook)
│
├── Cloud Storage
│   └── ai-doorbell-screenshots      ← Visitor photos, logs
│       └── Lifecycle: auto-delete after 7 days
│
├── Secret Manager
│   ├── telegram-bot-token
│   ├── gmail-oauth-credentials
│   ├── calendar-oauth-credentials
│   └── gemini-api-key
│
└── IAM
    └── ai-doorbell-sa               ← Service account
        ├── roles/run.invoker
        ├── roles/storage.objectAdmin
        └── roles/secretmanager.secretAccessor
```

### Deployment Scripts

```
scripts/
├── deploy.sh            # Full deploy: build → push → terraform apply
├── build-and-push.sh    # Build Docker image and push to Artifact Registry
└── destroy.sh           # Tear down all infrastructure
```

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY data/ ./data/
EXPOSE 8080
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## 11. Project Structure

```
AI-Doorbell/
├── backend/
│   ├── main.py              # FastAPI app, WebSocket /ws/doorbell, static file serving
│   ├── config.py            # pydantic-settings: env vars
│   ├── models.py            # Pydantic data models
│   ├── requirements.txt     # google-genai, fastapi, uvicorn, etc.
│   ├── gemini_session.py    # Gemini Live API session + tool dispatch
│   ├── static/
│   │   ├── index.html               # Single-page vanilla JS doorbell UI
│   │   └── audio-worklet-processor.js  # AudioWorkletNode for capture + playback
│   └── tools/
│       ├── __init__.py
│       ├── gmail.py         # check_gmail_orders
│       ├── calendar.py      # check_calendar
│       ├── known_faces.py   # check_known_faces
│       ├── telegram.py      # send_telegram_alert (with inline formatting)
│       └── screenshot.py    # capture_screenshot
│
├── infra/                   # Terraform IaC
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── cloud_run.tf
│   ├── cloud_storage.tf
│   ├── iam.tf
│   ├── secrets.tf
│   ├── artifact_registry.tf
│   └── terraform.tfvars.example
│
├── scripts/                 # Deployment automation
│   ├── deploy.sh
│   ├── build-and-push.sh
│   └── destroy.sh
│
├── data/
│   └── known_faces.json     # Registered acquaintance DB
│
├── Dockerfile
├── AI_Doorbell_PRD.md
├── ARCHITECTURE.md
└── README.md
```
