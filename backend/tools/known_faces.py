"""Known Faces DB: name matching with optional visual reference photos from GCS."""

import json
import logging
from pathlib import Path

from backend.tools.gcs import download_face_photo

logger = logging.getLogger(__name__)

KNOWN_FACES_PATH = Path(__file__).parent.parent.parent / "data" / "known_faces.json"


def _load_faces() -> list[dict]:
    try:
        return json.loads(KNOWN_FACES_PATH.read_text())
    except FileNotFoundError:
        return []


def _save_faces(faces: list[dict]):
    KNOWN_FACES_PATH.write_text(json.dumps(faces, indent=2, ensure_ascii=False) + "\n")


async def check_known_faces(name: str = "") -> dict | tuple[dict, list]:
    """Check if a visitor matches a registered known person.

    If the person has a reference photo in GCS, downloads it and returns
    it as a tuple (result_dict, image_parts) so Gemini can visually compare
    against the live video feed.
    """
    faces = _load_faces()

    if not name:
        # Return all registered names for Gemini to consider
        names = [f["name"] for f in faces]
        return {"found": False, "registered_names": names, "message": "No name provided. Registered names listed."}

    name_lower = name.strip().lower()
    for person in faces:
        if person["name"].lower() == name_lower:
            result = {
                "found": True,
                "name": person["name"],
                "relation": person["relation"],
                "memo": person.get("memo", ""),
            }

            # If there's a reference photo, download and return it for visual comparison
            gcs_path = person.get("photo_gcs_path")
            if gcs_path:
                try:
                    photo_bytes = await download_face_photo(gcs_path)
                    if photo_bytes:
                        result["has_reference_photo"] = True
                        result["visual_instruction"] = (
                            "A reference photo of this person is attached. "
                            "Compare it with the visitor you see in the live camera feed."
                        )
                        # Return tuple: (result_dict, list of image bytes)
                        return (result, [photo_bytes])
                except Exception as e:
                    logger.error("Failed to download reference photo: %s", e)
                    result["has_reference_photo"] = False

            return result

    return {"found": False, "message": f"'{name}' is not a registered known person"}
