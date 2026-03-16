from pydantic import BaseModel
from datetime import datetime


class KnownPerson(BaseModel):
    name: str
    relation: str
    memo: str | None = None
    photo_gcs_path: str | None = None


class Notification(BaseModel):
    id: str
    timestamp: datetime
    visitor_type: str  # delivery, known_person, unknown, suspicious
    urgency: str  # low, medium, high
    summary: str
    screenshot_url: str | None = None
    conversation_transcript: list[dict] = []
    owner_action: str | None = None  # let_in, wait, decline


class DoorbellSession(BaseModel):
    id: str
    status: str = "idle"  # idle, active, ended
    started_at: datetime | None = None
    ended_at: datetime | None = None
    notifications: list[Notification] = []


class DoorbellConfig(BaseModel):
    owner_name: str
    language: str = "en"
    delivery_instructions: str = "Please leave it at the door"
    known_faces: list[dict] = []
