# AI Doorbell — Product Requirements Document

> Version 2.0 | March 2026
> Gemini Live Agent Challenge Hackathon

---

## 1. Executive Summary

AI Doorbell is a smart doorbell agent powered by the Gemini Live API. It simulates a doorbell using a phone camera, sees and talks with visitors in real time, cross-checks Gmail order history and Google Calendar appointments, and sends situation summaries with photos to the homeowner via Telegram.

The key differentiator is that **instead of just sending notifications, the AI assesses the situation and responds on behalf of the homeowner**. It welcomes legitimate deliveries, filters out fake ones, verifies acquaintances through the calendar, and captures photos to warn about suspicious visitors.

### One-Line Summary

> An AI doorbell agent that sees visitors through a phone camera, has real-time conversations via Gemini, cross-checks Gmail/Calendar/Known Faces DB, and reports its assessment to the homeowner via Telegram.

---

## 2. Problem & Why Now

### 2.1 Problem

When someone comes to the door while you're away, existing smart doorbells (Ring, Nest, etc.) only send notifications. The homeowner must personally watch the video and speak through the microphone. If you're busy or in a meeting, you can't respond.

The bigger problem is **judgment**:
- A delivery arrives, but you don't know if it's something you ordered
- Someone shows up, but you can't remember if you have an appointment with them
- A suspicious person is lingering, but you can't check on every visitor

### 2.2 Target User

- Solo households (handling visitors while away)
- Remote workers (minimizing interruptions during meetings)
- People who frequently receive deliveries

### 2.3 Why Now

- **Gemini Live API**: Supports real-time bidirectional video + audio streaming with tool calling in a single session. Previously, separate STT → LLM → TTS pipelines had to be built.
- **Native audio processing**: Gemini 3 Flash Native Audio processes raw audio directly, significantly reducing latency compared to traditional multi-step pipelines.
- **Tool use in Live session**: External APIs like Gmail and Calendar can be called in real time during conversation, enabling **judgment** beyond simple conversation.

---

## 3. Solution Overview

### 3.1 Core Concept

AI Doorbell is a **semi-autonomous doorbell concierge**. When a visitor arrives:

1. The AI sees the visitor through the camera and initiates a conversation via microphone
2. Based on the conversation, it cross-checks Gmail (order history), Calendar (appointments), and Known Faces DB (registered acquaintances)
3. It assesses the situation and responds appropriately (delivery guidance, acquaintance greeting, suspicious visitor handling)
4. It sends a situation summary + screenshot to the homeowner via Telegram
5. When the homeowner sends a command via Telegram (e.g., "Tell them to come in"), the AI relays it to the visitor

### 3.2 Key Differentiators

| Existing Smart Doorbells | AI Doorbell |
|---|---|
| Only sends notifications | AI converses on your behalf |
| Homeowner judges manually | AI cross-checks with Gmail/Calendar |
| One-way (video viewing) | Bidirectional (AI ↔ visitor real-time conversation) |
| All alerts identical | Different urgency levels per situation |

---

## 4. Demo Storyboard

Demo is **pre-recorded** (within 4 minutes). 3 scenes progressively build up to introduce features.

### Scene 1: Delivery Person (0:25 - 1:15) — "Gmail Cross-Check"

```
[Doorbell rings]
AI: "Hello, how can I help you?"
Delivery: "I have a delivery for you"
AI: (→ check_gmail_orders called → Amazon order matched)
    "Ah, this must be the [product name] you ordered from Amazon, right?
     Please leave it at the door. Thank you!"

→ Telegram alert: "📦 Delivery arrived — Amazon [product name], placed at door"
  + Screenshot attached
```

**Features demonstrated**: Gemini Live API real-time conversation, Gmail order matching, Telegram alert + screenshot

**Key moment**: The instant when AI finds the order in Gmail and says "This must be what you ordered from Amazon, right?"

### Scene 2: Acquaintance Visit (1:15 - 2:30) — "Calendar + DB Cross-Check + Bidirectional Commands"

```
[Doorbell rings]
AI: "Hello, who are you looking for?"
Visitor: "Is Kyuhee here? I'm Minsu."
AI: (→ check_known_faces: "Minsu" matched)
    (→ check_calendar: today 15:00 appointment confirmed)
    "Ah, Minsu! You have an appointment at 3 PM today, right?
     I'll let Kyuhee know right away. Please wait a moment."

→ Telegram alert: "👤 Minsu visiting — 15:00 appointment today confirmed"
  + Screenshot attached
  + Inline buttons: [Tell them to come in] [Tell them to wait]

→ Homeowner taps "Tell them to come in"

AI: "Minsu, Kyuhee said to come on in! Make yourself at home."
```

**Features demonstrated**: Known Faces DB matching, Google Calendar integration, Telegram bidirectional flow (alert → command → AI relay)

**Key moment**: AI finds the appointment in Calendar and says "You have a 3 PM appointment, right?" + homeowner's Telegram command is relayed to AI in real time

### Scene 3: Suspicious Visitor (2:30 - 3:35) — "Lie Detection Climax"

```
[Doorbell rings]
AI: "Hello, how can I help you?"
Visitor: "I have a delivery for you"
AI: (→ check_gmail_orders: no match)
    (→ check_calendar: no appointment)
    (→ check_known_faces: not registered)
    "I'm sorry, but it doesn't look like we're expecting any deliveries right now.
     Could you tell me where this is being sent from?"
Visitor: "Uh... it's just a delivery..."
AI: "Could you provide the shipping company name or sender's name?"
Visitor: (unable to answer)
AI: "If you're unable to verify, please check with the delivery company again. Thank you."

→ Telegram: "⚠️ Caution — Claims to be delivery but no matching order in Gmail.
   Unable to verify carrier/sender. Identity unknown."
   + 📸 Photo capture attached
```

**Features demonstrated**: Multi-source cross-check for lie detection, automatic photo capture, high-risk alert

**Key moment**: Contrast with Scene 1 where a real delivery was matched and welcomed via Gmail — the same system now filters out a fake delivery. This is the demo climax.

### Architecture + Closing (3:35 - 4:00)

Display architecture diagram + technical summary:
> "Real-time bidirectional video + audio streaming via Gemini Live API.
> Agent orchestration via ADK.
> Google Calendar, Gmail, and Telegram integrated through tool calling.
> Deployed on Cloud Run via Terraform."

---

## 5. Feature Requirements

### 5.1 Core Features (P0 — Must Have)

| ID | Feature | Description | Demo Scene |
|---|---|---|---|
| C1 | Real-time video + audio conversation | Bidirectional real-time conversation with visitors via phone camera/microphone | All |
| C2 | Visitor intent recognition | Classify visitor type based on conversation (delivery/acquaintance/suspicious) | All |
| C3 | Gmail order matching | Search Gmail for recent order confirmation emails, match with delivery contents | Scene 1, 3 |
| C4 | Known Faces DB matching | Search registered acquaintance DB for name mentioned by visitor | Scene 2, 3 |
| C5 | Google Calendar appointment check | Query today's scheduled events, match with visitor name | Scene 2, 3 |
| C6 | Telegram alert sending | Send situation summary + screenshot to homeowner via Telegram | All |
| C7 | Telegram command receive → AI relay | Reflect homeowner's Telegram response (inline buttons) in AI conversation | Scene 2 |
| C8 | Suspicious visitor photo capture | Automatically capture frame during suspicious situations, save to Cloud Storage | Scene 3 |
| C9 | Threat level assessment | Combine DB/Calendar/Gmail/conversation to classify urgency (low/medium/high) | Scene 3 |

### 5.2 UI Features (P1 — Demo Impact)

| ID | Feature | Description |
|---|---|---|
| U1 | Camera feed | Real-time display of phone camera |
| U2 | Real-time conversation subtitles | AI ↔ visitor conversation text overlay |
| U3 | Status indicator | 🟢 Idle / 🔴 In Conversation / ⚠️ Caution |
| U4 | Notification log | List of previous visit records |

### 5.3 Deferred (P2 — Not in MVP)

- Notification history page
- Settings page (AI personality, language, delivery instructions customization)
- Conversation transcript storage and search
- Multi-language support

---

## 6. User Flow

```
┌─────────────────────────────────────────────────────────┐
│                    AI Doorbell Web App                    │
│                                                          │
│  ┌─────────────────────────────┐  ┌───────────────────┐ │
│  │     Live Camera Feed        │  │  Control Panel     │ │
│  │                             │  │                    │ │
│  │  [Webcam/Phone camera live] │  │  🟢 AI Active     │ │
│  │                             │  │                    │ │
│  │  ┌───────────────────────┐  │  │  Current status:   │ │
│  │  │ Real-time subtitles   │  │  │  "Talking with     │ │
│  │  │ AI: "Leave it at the  │  │  │   delivery         │ │
│  │  │      door please"     │  │  │   person..."       │ │
│  │  └───────────────────────┘  │  │                    │ │
│  └─────────────────────────────┘  │  Quick Actions:    │ │
│                                    │  [Tell them to     │ │
│  ┌─────────────────────────────┐  │   come in]         │ │
│  │     Notification Log        │  │  [Away mode]       │ │
│  │                             │  │  [Talk directly]   │ │
│  │  📦 14:23 Delivery arrived  │  │                    │ │
│  │     Amazon [product], door  │  │                    │ │
│  │     [View screenshot]       │  │                    │ │
│  │                             │  │                    │ │
│  │  👤 13:05 Minsu visited     │  │                    │ │
│  │     15:00 appt confirmed    │  │                    │ │
│  │     [View screenshot]       │  │                    │ │
│  └─────────────────────────────┘  └───────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Technical Architecture

### 7.1 System Architecture

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

### 7.2 Data Flow

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

### 7.3 Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js + Tailwind | Camera feed + subtitle UI |
| Camera/Audio | WebRTC MediaStream API | Browser webcam + microphone capture |
| Real-time Comm | WebSocket | Frontend ↔ backend bidirectional streaming |
| Backend | FastAPI (Python) | Deployed on Cloud Run |
| AI Core | Gemini Live API | Real-time bidirectional video + audio. Model: `gemini-live-2.5-flash-native-audio` |
| Agent Framework | Google ADK | Agent orchestration |
| Storage | Google Cloud Storage | Screenshots, logs |
| Notifications | Telegram Bot API | Homeowner alerts + bidirectional commands |
| IaC / Deployment | Terraform + Cloud Build | Cloud Run, Cloud Storage, IAM, networking |

### 7.4 Gemini Live API Specs

Key technical specifications for the Gemini Live API (implementation reference):

- **Audio input**: Raw 16-bit PCM, 16kHz, mono
- **Audio output**: Raw 16-bit PCM, 24kHz
- **Protocol**: WebSocket (stateful)
- **Features**: Voice Activity Detection, barge-in (interruptible), tool calling, affective dialog
- **Session**: Stateful — remembers all conversation within a session
- **Model**: `gemini-live-2.5-flash-native-audio` (or latest Live API compatible model)

### 7.5 Streaming Flow

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

## 8. Agent Design

### 8.1 ADK Agent Architecture

```
ADK Orchestrator
├── DoorbellAgent (Main)
│   ├── Model: Gemini Live API
│   ├── Input: Real-time video + audio stream
│   ├── Output: Audio responses
│   └── Tools: check_gmail_orders, check_calendar,
│              check_known_faces, send_telegram_alert,
│              capture_screenshot
│
└── NotifierAgent
    ├── Model: Gemini (text, for summary)
    ├── Input: Event from DoorbellAgent
    └── Output: Telegram notification
```

### 8.2 System Prompt

```
You are an AI doorbell assistant for {owner_name}'s home. You can see
visitors through the doorbell camera and have natural voice conversations
with them.

## Your Responsibilities
1. Greet every visitor politely
2. Identify who they are and what they want through natural conversation
3. Use your tools to verify information:
   - Delivery? → check_gmail_orders to match with expected packages
   - Says a name? → check_known_faces + check_calendar
   - Can't verify? → ask follow-up questions, capture photo
4. Send appropriate alerts to the homeowner via send_telegram_alert
5. Handle the situation based on verification result:
   - Verified delivery: Thank them, instruct door placement
   - Known person + appointment: Greet warmly, notify owner, await instruction
   - Unknown but cooperative: Ask details, notify owner
   - Cannot verify + evasive: Stay polite, don't reveal info, capture photo,
     high-urgency alert

## House Rules
- Owner: {owner_name}
- Language: English
- Delivery instructions: Please leave it at the door
- Personality: Friendly and warm, like a helpful building concierge

## Critical Behaviors
- You can be interrupted — handle it gracefully
- Keep responses concise (1-2 sentences)
- Never reveal you are AI unless directly asked
- Never reveal personal information about the homeowner
- Always call send_telegram_alert for every visitor
- For suspicious visitors: be polite but firm, capture photo,
  alert owner immediately
- When owner sends a command via Telegram, relay it naturally
```

### 8.3 Tool Definitions

#### check_gmail_orders
```json
{
  "name": "check_gmail_orders",
  "description": "Check Gmail for recent online orders and delivery
    notifications. Call when a delivery person arrives to match the
    package with an expected order.",
  "parameters": {
    "type": "object",
    "properties": {
      "keywords": {
        "type": "string",
        "description": "Search keywords like carrier name or description"
      }
    }
  }
}
```
Implementation: Gmail API → search recent order confirmation emails (Amazon, etc.) → return product name / carrier

#### check_calendar
```json
{
  "name": "check_calendar",
  "description": "Check Google Calendar for today's appointments.
    Call when a visitor claims to have an appointment or gives a name.",
  "parameters": {
    "type": "object",
    "properties": {
      "visitor_name": {
        "type": "string",
        "description": "Name of the visitor"
      }
    }
  }
}
```
Implementation: Google Calendar API → query today's events → match visitor_name

#### check_known_faces
```json
{
  "name": "check_known_faces",
  "description": "Check if the visitor is a registered known person.
    Call when a visitor gives their name.",
  "parameters": {
    "type": "object",
    "properties": {
      "name": {
        "type": "string",
        "description": "Name of the visitor"
      }
    }
  }
}
```
Implementation: Match name in local JSON file → return relationship, memo

#### send_telegram_alert
```json
{
  "name": "send_telegram_alert",
  "description": "Send alert to homeowner via Telegram. Call for every
    visitor interaction.",
  "parameters": {
    "type": "object",
    "properties": {
      "urgency": {
        "type": "string",
        "enum": ["low", "medium", "high"],
        "description": "low=delivery/known, medium=unknown cooperative,
          high=suspicious/unverified"
      },
      "visitor_type": {
        "type": "string",
        "enum": ["delivery", "known_person",
                 "unknown", "suspicious"]
      },
      "summary": {
        "type": "string",
        "description": "Brief summary for the homeowner"
      },
      "capture_photo": {
        "type": "boolean",
        "description": "Whether to capture and attach photo.
          Always true for suspicious visitors."
      }
    },
    "required": ["urgency", "visitor_type", "summary", "capture_photo"]
  }
}
```
Implementation:
1. capture_photo=true → capture current frame → upload to Cloud Storage
2. Telegram Bot API → send message + photo
3. For Scene 2 (acquaintance), include inline keyboard buttons

#### capture_screenshot
```json
{
  "name": "capture_screenshot",
  "description": "Capture current camera frame and save to storage.
    Call immediately when encountering suspicious visitors.",
  "parameters": {
    "type": "object",
    "properties": {}
  }
}
```
Implementation: Current video frame → JPEG → upload to Cloud Storage → return URL

---

## 9. Data Models

```python
from pydantic import BaseModel
from datetime import datetime

class Notification(BaseModel):
    id: str
    timestamp: datetime
    visitor_type: str      # delivery, known_person,
                           # unknown, suspicious
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

## 10. API Endpoints

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

## 11. Cloud Deployment (Infrastructure as Code)

### 11.1 Terraform Configuration

All cloud infrastructure is defined as Terraform code in the `infra/` directory.

```
infra/
├── main.tf              # Provider config, backend
├── variables.tf         # Input variables
├── outputs.tf           # Output values (URLs, etc.)
├── cloud_run.tf         # Cloud Run service
├── cloud_storage.tf     # GCS bucket for screenshots
├── iam.tf               # Service accounts, permissions
├── secrets.tf           # Secret Manager for API keys
├── artifact_registry.tf # Container image registry
└── terraform.tfvars.example
```

#### Key Resources

| Resource | Purpose |
|---|---|
| `google_cloud_run_v2_service` | FastAPI backend (doorbell agent) |
| `google_storage_bucket` | Screenshot / photo storage |
| `google_secret_manager_secret` | API keys (Telegram, Gmail OAuth, etc.) |
| `google_artifact_registry_repository` | Docker image registry |
| `google_service_account` | Least-privilege service account for Cloud Run |
| `google_cloud_run_v2_service_iam_member` | Public invoker for webhook endpoints |

### 11.2 Deployment Scripts

```
scripts/
├── deploy.sh            # Full deploy: build → push → terraform apply
├── build-and-push.sh    # Build Docker image and push to Artifact Registry
└── destroy.sh           # Tear down all infrastructure
```

#### deploy.sh workflow
```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Build and push Docker image
docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/ai-doorbell/backend:latest .
docker push $REGION-docker.pkg.dev/$PROJECT_ID/ai-doorbell/backend:latest

# 2. Apply Terraform
cd infra
terraform init
terraform apply -auto-approve

# 3. Output service URL
terraform output service_url
```

### 11.3 Dockerfile

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

## 12. Implementation Plan

### 12.1 Priority (Working Backwards from Demo)

**P0 — Demo is impossible without these:**
1. Gemini Live API integration (bidirectional video + audio)
2. Phone camera → WebSocket → backend streaming
3. AI voice response → phone speaker playback
4. send_telegram_alert tool calling (summary + photo)
5. check_gmail_orders tool calling
6. check_calendar tool calling
7. check_known_faces tool calling (local JSON)
8. Terraform IaC for Cloud Run + Cloud Storage

**P1 — Increases demo impact:**
9. Telegram inline keyboard → homeowner command receive → AI relay
10. Real-time conversation subtitle UI
11. Status indicator (idle/in conversation/caution)

**P2 — Nice to have:**
12. Notification history UI
13. Settings page
14. Conversation transcript storage

### 12.2 3-Day Timeline

#### Day 1 — Core Flow (P0)

| Task | Detail |
|---|---|
| Gemini Live API integration | WebSocket video + audio streaming ↔ Gemini, voice response receive |
| Phone camera integration | Mobile browser MediaStream → WebSocket → backend |
| Tool calling setup | 5 tool definitions + handler implementation |
| Telegram Bot setup | Bot creation + message/photo sending + inline keyboard |
| Gmail API integration | Order confirmation email search (OAuth) |
| Calendar API integration | Today's event query (OAuth) |
| Terraform IaC setup | Cloud Run + Cloud Storage + IAM + Secrets via Terraform |
| Cloud Run deploy | Initial deployment via `deploy.sh` |

**Milestone**: Say "I have a delivery" in front of the phone → AI conversation → Telegram alert arrives

#### Day 2 — Full Scenarios + P1

| Task | Detail |
|---|---|
| 3 scenario tests | Delivery, acquaintance, suspicious visitor — all working |
| Telegram bidirectional | Webhook → homeowner command → Gemini session injection |
| Frontend UI | Camera feed + subtitles + status indicator |
| Prompt tuning | Optimize natural conversation quality per scenario |
| Known Faces DB | Set up test data |

**Milestone**: All 3 scenarios E2E working, Telegram bidirectional complete

#### Day 3 — Record + Submit

| Task | Detail |
|---|---|
| Demo rehearsal | 3 scene timing check, line practice |
| Demo video recording | Pre-recorded (multiple takes) |
| Video editing | Edit to within 4 minutes + add subtitles |
| Submission materials | Architecture diagram, README, text description |
| Cloud deployment evidence | Console screen recording + Terraform state |
| Code cleanup | GitHub repo cleanup + spin-up instructions |

**Milestone**: Submission complete

---

## 13. Hackathon Requirements Compliance

### Required

| Requirement | How We Meet It |
|---|---|
| Gemini model usage | Gemini Live API (gemini-live-2.5-flash-native-audio) — entire AI core |
| Google GenAI SDK / ADK | ADK for agent orchestration |
| Google Cloud services (1+) | Cloud Run (deployment) + Cloud Storage (screenshots) |
| Multimodal input/output | Video + Audio in → Audio out + Text (Telegram) |
| Live Agent track required tech | Gemini Live API usage, Google Cloud hosting |

### Submission Items

| Item | Plan |
|---|---|
| Text Description | Features, technology, Gmail/Calendar data sources, lessons learned |
| Public GitHub Repo | README with spin-up instructions, environment variable guide |
| Cloud Deployment Evidence | Cloud Run console screen recording + Terraform config in repo |
| Architecture Diagram | Excalidraw or draw.io — system architecture |
| Demo Video | Within 4 minutes, pre-recorded, 3 scenarios demonstrated |

### Bonus

| Item | Plan |
|---|---|
| Content | Blog post "Building AI Doorbell with Gemini Live API" + #GeminiLiveAgentChallenge |
| IaC | Terraform configs + deployment scripts + Dockerfile in repo |
| GDG | Google Developer Group membership + profile link |

---

## 14. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Gemini Live API latency affects natural conversation | Medium | High | Test on Day 1 morning. If latency is severe, lower video resolution/fps |
| Tool calling doesn't work mid-conversation in Live API | Medium | High | Verify on Day 0. If not possible, separate tool calls into a separate Gemini invocation |
| WebSocket video streaming bandwidth issues | Low | Medium | Frame compression, limit fps to 5-10 |
| Audio echo/feedback loop | Medium | Medium | Echo cancellation, use headphones (during demo) |
| Cloud Run WebSocket timeout | Low | Medium | Keep-alive ping, increase timeout settings |
| English voice quality issues | Low | Medium | Test on Day 0. Adjust voice settings if needed |
| Gmail OAuth approval time | Low | High | Create OAuth app on Day 0 and approve test account |
| Terraform state conflicts | Low | Medium | Use remote backend (GCS) for state, lock with `-lock=true` |

---

## 15. Day 0 Checklist (Before Hackathon)

- [ ] Verify Gemini Live API access + multimodal (video + audio) test
- [ ] Verify tool calling works in Live API (function calls possible mid-conversation)
- [ ] Test Live API English voice quality
- [ ] Create Gmail API OAuth app + approve test account + test order email search
- [ ] Set up Google Calendar API OAuth + test event query
- [ ] Create Telegram Bot + obtain API token + test message/photo sending
- [ ] Create Google Cloud project + set up billing
- [ ] Set up Terraform backend (GCS bucket for state)
- [ ] Write initial Terraform configs + `terraform plan` test
- [ ] Deploy test service to Cloud Run via `deploy.sh`
- [ ] Install ADK + verify basic agent operation
- [ ] Test phone browser camera + mic → WebSocket transmission
- [ ] Create GitHub repo

---

## 16. Future Vision (Beyond Hackathon)

- **Real hardware integration**: Raspberry Pi + camera module = physical doorbell
- **Face recognition**: Actual face embeddings instead of name-based DB
- **Smart home integration**: "Tell them to come in" → actual door lock release
- **Multi-camera**: Front door + hallway + parking lot integrated monitoring
- **Recording + analysis**: Daily/weekly visit pattern reports
- **Multi-language**: Auto-detect foreign visitors → respond in their language
