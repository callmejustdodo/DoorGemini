"""Face registration: add/remove known faces with GCS photo storage."""

import json
import logging
from pathlib import Path

from backend.tools.gcs import upload_face_photo

logger = logging.getLogger(__name__)

KNOWN_FACES_PATH = Path(__file__).parent.parent.parent / "data" / "known_faces.json"


def _load_faces() -> list[dict]:
    try:
        return json.loads(KNOWN_FACES_PATH.read_text())
    except FileNotFoundError:
        return []


def _save_faces(faces: list[dict]):
    KNOWN_FACES_PATH.write_text(json.dumps(faces, indent=2, ensure_ascii=False) + "\n")


async def register_face(
    photo_bytes: bytes, name: str, relation: str = "unknown", memo: str = ""
) -> dict:
    """Register a new known face: upload photo to GCS and update JSON."""
    gcs_path = await upload_face_photo(name, photo_bytes)

    faces = _load_faces()

    # Update existing entry or add new
    for face in faces:
        if face["name"].lower() == name.lower():
            face["photo_gcs_path"] = gcs_path
            face["relation"] = relation
            if memo:
                face["memo"] = memo
            _save_faces(faces)
            logger.info("Updated face registration: %s", name)
            return {"status": "updated", "name": name, "gcs_path": gcs_path}

    faces.append({
        "name": name,
        "relation": relation,
        "memo": memo or None,
        "photo_gcs_path": gcs_path,
    })
    _save_faces(faces)
    logger.info("Registered new face: %s", name)
    return {"status": "registered", "name": name, "gcs_path": gcs_path}


async def remove_face(name: str) -> dict:
    """Remove a known face from the JSON DB. GCS photo is left for manual cleanup."""
    faces = _load_faces()
    original_len = len(faces)
    faces = [f for f in faces if f["name"].lower() != name.lower()]

    if len(faces) == original_len:
        return {"status": "not_found", "name": name}

    _save_faces(faces)
    logger.info("Removed face: %s", name)
    return {"status": "removed", "name": name}
