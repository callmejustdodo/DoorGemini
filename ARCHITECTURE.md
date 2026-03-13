# AI Doorbell — Architecture Document

> Extracted from PRD v2.0 | March 2026

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
                          │    └── ADK Orchestration            │
                          └─────────────────────────────────────┘
```

---

## 2. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js + Tailwind | Camera feed + subtitle UI (web app) |
| Camera/Audio | WebRTC MediaStream API | Browser webcam + microphone capture |
| Real-time Comm | WebSocket | Frontend ↔ backend bidirectional streaming |
| Backend | FastAPI (Python) | Deployed on Cloud Run |
| AI Core | Gemini Live API | Real-time bidirectional video + audio. Model: `gemini-live-2.5-flash-native-audio` |
| Agent Framework | Google ADK | Agent orchestration |
| Storage | Google Cloud Storage | Screenshots, logs |
| Notifications | Telegram Bot API | Homeowner alerts + bidirectional commands |
| IaC / Deployment | Terraform + Cloud Build | Cloud Run, Cloud Storage, IAM, networking |

---

## 3. Data Flow

```
 1. Phone browser → getUserMedia() → video + audio stream
 2. WebSocket sends to Cloud Run backend
 3. Backend → Gemini Live API WebSocket session (bidirectional)
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
     │── video frames (WebSocket) ─────────▶│── video stream ───────────────▶│
     │── audio PCM 16kHz (WebSocket) ──────▶│── audio stream ───────────────▶│
     │                                      │                                │
     │                                      │◀── audio PCM 24kHz ───────────│
     │◀── audio playback (WebSocket) ───────│                                │
     │                                      │                                │
     │                                      │◀── tool_call: check_gmail ────│
     │                                      │── tool_result ───────────────▶│
     │                                      │                                │
     │                                      │◀── tool_call: send_telegram ──│
     │◀── notification update (WebSocket) ──│── Telegram Bot API ──▶ Owner  │
     │                                      │                                │
     │                                      │◀── owner command (webhook) ────│
     │                                      │── inject context ────────────▶│
     │                                      │◀── audio response ────────────│
     │◀── audio playback (WebSocket) ───────│                                │
```

---

## 5. Agent Design (ADK)

```
ADK Orchestrator
├── DoorbellAgent (Main)
│   ├── Model: Gemini Live API (gemini-live-2.5-flash-native-audio)
│   ├── Input: Real-time video + audio stream
│   ├── Output: Audio responses
│   └── Tools:
│       ├── check_gmail_orders   — Match delivery with Gmail order history
│       ├── check_calendar       — Verify visitor against today's appointments
│       ├── check_known_faces    — Look up visitor in registered acquaintance DB
│       ├── send_telegram_alert  — Send summary + photo to homeowner
│       └── capture_screenshot   — Capture current frame to Cloud Storage
│
└── NotifierAgent
    ├── Model: Gemini (text, for summary generation)
    ├── Input: Event from DoorbellAgent
    └── Output: Formatted Telegram notification
```

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

## 6. Gemini Live API Specs

| Parameter | Value |
|---|---|
| Audio input | Raw 16-bit PCM, 16kHz, mono |
| Audio output | Raw 16-bit PCM, 24kHz |
| Protocol | WebSocket (stateful) |
| Features | Voice Activity Detection, barge-in, tool calling, affective dialog |
| Session | Stateful — remembers all conversation within session |
| Model | `gemini-live-2.5-flash-native-audio` |

---

## 7. API Endpoints

```
# WebSocket (real-time streaming)
WS  /ws/doorbell           → Doorbell stream (video+audio in, audio+notifications out)

# REST
POST /api/doorbell/start    → Start doorbell session
POST /api/doorbell/stop     → Stop doorbell session
GET  /api/notifications     → Notification history
POST /api/owner/command     → Relay homeowner command (called from Telegram webhook)
GET  /api/config            → Get configuration
PUT  /api/config            → Update configuration
```

---

## 8. Data Models

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

## 9. Cloud Infrastructure (Terraform)

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
│   └── ai-doorbell-service          ← FastAPI backend
│       ├── Service Account (least-privilege)
│       ├── Secret references (Telegram token, OAuth creds)
│       └── Public invoker IAM (for Telegram webhook)
│
├── Cloud Storage
│   └── ai-doorbell-screenshots      ← Visitor photos, logs
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
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## 10. Project Structure

```
AI-Doorbell/
├── frontend/                # Next.js web app
│   ├── src/
│   │   ├── app/             # Next.js app router
│   │   ├── components/      # Camera feed, subtitles, status, notification log
│   │   └── lib/             # WebSocket client, audio playback
│   ├── package.json
│   └── tailwind.config.ts
│
├── backend/                 # FastAPI server
│   ├── main.py              # App entry, WebSocket endpoint
│   ├── agents/
│   │   ├── doorbell_agent.py    # DoorbellAgent (Gemini Live API)
│   │   └── notifier_agent.py    # NotifierAgent (Telegram)
│   ├── tools/
│   │   ├── gmail.py             # check_gmail_orders
│   │   ├── calendar.py          # check_calendar
│   │   ├── known_faces.py       # check_known_faces
│   │   ├── telegram.py          # send_telegram_alert
│   │   └── screenshot.py        # capture_screenshot
│   ├── models.py            # Pydantic data models
│   ├── config.py            # Environment / settings
│   └── requirements.txt
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
