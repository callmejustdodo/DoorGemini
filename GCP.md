# Google Cloud Services & API Usage

AI Doorbell uses 6 Google Cloud services and APIs, all invoked from real production code — not wrappers or stubs.

---

## 1. Gemini Live API (AI Core)

Real-time bidirectional video + audio streaming with tool calling via `google-genai` SDK.

**File:** [`backend/gemini_session.py`](backend/gemini_session.py)

```python
from google import genai
from google.genai import types

# Initialize client
client = genai.Client(api_key=settings.GEMINI_API_KEY)

# Open a persistent Live API session with tool declarations
config = types.LiveConnectConfig(
    response_modalities=[types.Modality.AUDIO],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
        )
    ),
    system_instruction=types.Content(parts=[types.Part(text=system_prompt)]),
    tools=TOOL_DECLARATIONS,
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
)

# Connect — bidirectional WebSocket session
session = await client.aio.live.connect(model="gemini-2.5-flash-native-audio-preview-12-2025", config=config)

# Stream video frames and audio in real time
await session.send_realtime_input(video=types.Blob(data=jpeg_frame, mime_type="image/jpeg"))
await session.send_realtime_input(audio=types.Blob(data=audio_data, mime_type="audio/pcm;rate=16000"))

# Receive audio responses, transcriptions, and tool calls
async for response in session.receive():
    # Audio playback, subtitles, tool call dispatch...
```

**What it demonstrates:**
- Persistent WebSocket session with Gemini Live API
- Multimodal input: video frames (JPEG) + audio (PCM 16kHz)
- Audio output with voice selection
- Real-time tool calling (function declarations + dispatch)
- Session resumption for fault tolerance
- Input/output transcription for subtitles

---

## 2. Gmail API

Searches the homeowner's Gmail for recent order confirmations to verify deliveries.

**File:** [`backend/tools/gmail.py`](backend/tools/gmail.py)

```python
from googleapiclient.discovery import build

# Build authorized Gmail service
creds = get_credentials(["https://www.googleapis.com/auth/gmail.readonly"])
service = build("gmail", "v1", credentials=creds, cache_discovery=False)

# Search for order-related emails from the last 7 days
query = "subject:(order OR shipping OR delivery OR confirmation) newer_than:7d"
results = service.users().messages().list(userId="me", q=query, maxResults=5).execute()

# Fetch email metadata (subject, sender, date)
for msg_ref in results.get("messages", []):
    msg = service.users().messages().get(
        userId="me", id=msg_ref["id"], format="metadata",
        metadataHeaders=["Subject", "From", "Date"],
    ).execute()
```

**What it demonstrates:**
- OAuth2-authenticated Gmail API calls
- Message search with query filters
- Metadata extraction without reading email bodies (privacy-conscious)

---

## 3. Google Calendar API

Queries today's calendar events to verify visitor appointments.

**File:** [`backend/tools/calendar.py`](backend/tools/calendar.py)

```python
from googleapiclient.discovery import build

# Build authorized Calendar service
creds = get_credentials(["https://www.googleapis.com/auth/calendar.readonly"])
service = build("calendar", "v3", credentials=creds, cache_discovery=False)

# Query today's events
events_result = service.events().list(
    calendarId="primary",
    timeMin=start_of_day.isoformat(),
    timeMax=end_of_day.isoformat(),
    timeZone="Asia/Seoul",
    maxResults=10,
    singleEvents=True,
    orderBy="startTime",
).execute()

# Match visitor name against event summaries and attendees
for event in events_result.get("items", []):
    summary = event.get("summary", "")
    attendees = [a.get("displayName", a.get("email", "")) for a in event.get("attendees", [])]
    # Fuzzy match visitor_name against summary + attendees
```

**What it demonstrates:**
- OAuth2-authenticated Calendar API calls
- Time-bounded event queries with timezone support
- Attendee and summary matching for visitor verification

---

## 4. Google OAuth2 with Secret Manager Fallback

Shared credential loader that works locally (env vars / `token.json`) and on Cloud Run (Secret Manager-injected env vars).

**File:** [`backend/tools/google_auth.py`](backend/tools/google_auth.py)

```python
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

def get_credentials(scopes):
    # Priority 1: Env vars (works on Cloud Run with Secret Manager injection)
    if settings.GOOGLE_REFRESH_TOKEN and settings.GOOGLE_CLIENT_ID:
        creds = Credentials(
            token=None,
            refresh_token=settings.GOOGLE_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=scopes,
        )
        creds.refresh(Request())  # Exchange refresh token for access token
        return creds

    # Priority 2: Local token.json (development)
    creds = Credentials.from_authorized_user_file("token.json", scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds
```

**What it demonstrates:**
- Google OAuth2 token refresh flow
- Environment-aware credential loading (local dev vs Cloud Run)
- Seamless integration with Secret Manager-injected environment variables

---

## 5. Cloud Run (Deployment)

FastAPI backend deployed as a containerized Cloud Run service with WebSocket support, session affinity, and Secret Manager integration.

**File:** [`infra/cloud_run.tf`](infra/cloud_run.tf)

```hcl
resource "google_cloud_run_v2_service" "doorbell" {
  name     = "ai-doorbell"
  location = var.region

  template {
    service_account = google_service_account.doorbell.email
    session_affinity = true          # Sticky sessions for WebSocket
    timeout          = "300s"        # 5-minute timeout for long conversations
    max_instance_request_concurrency = 1  # One conversation per instance

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/ai-doorbell/backend:latest"

      # Secrets injected from Secret Manager
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }
      # ... GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN, TELEGRAM_BOT_TOKEN
    }
  }
}

# Public access for doorbell frontend + Telegram webhook
resource "google_cloud_run_v2_service_iam_member" "public" {
  role   = "roles/run.invoker"
  member = "allUsers"
}
```

**What it demonstrates:**
- Cloud Run v2 service with WebSocket support (session affinity + extended timeout)
- Secret Manager integration via `secret_key_ref` (zero secrets in code or env files)
- Least-privilege service account
- Terraform IaC for reproducible deployment

---

## 6. Secret Manager

Stores and injects 5 secrets into Cloud Run without exposing them in code, environment files, or Terraform state.

**File:** [`infra/secrets.tf`](infra/secrets.tf)

```hcl
resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "gemini-api-key"
  project   = var.project_id
  replication { auto {} }
}

resource "google_secret_manager_secret_version" "gemini_api_key" {
  secret      = google_secret_manager_secret.gemini_api_key.id
  secret_data = var.gemini_api_key
}

# Same pattern for: telegram-bot-token, google-client-id, google-client-secret, google-refresh-token
```

**Secrets managed:**

| Secret | Used By |
|---|---|
| `gemini-api-key` | Gemini Live API authentication |
| `telegram-bot-token` | Telegram Bot API |
| `google-client-id` | Gmail + Calendar OAuth |
| `google-client-secret` | Gmail + Calendar OAuth |
| `google-refresh-token` | Gmail + Calendar OAuth token refresh |

---

## Summary

| Google Cloud Service | Purpose | Code Location |
|---|---|---|
| **Gemini Live API** | Real-time video+audio AI conversations with tool calling | `backend/gemini_session.py` |
| **Gmail API** | Match deliveries against order confirmation emails | `backend/tools/gmail.py` |
| **Calendar API** | Verify visitor appointments against today's schedule | `backend/tools/calendar.py` |
| **Cloud Run** | Containerized deployment with WebSocket + session affinity | `infra/cloud_run.tf` |
| **Secret Manager** | Secure injection of API keys and OAuth credentials | `infra/secrets.tf` |
| **OAuth2** | Shared credential loader with automatic token refresh | `backend/tools/google_auth.py` |

All API calls are production code invoked during real-time doorbell conversations — not mocked or simulated.
