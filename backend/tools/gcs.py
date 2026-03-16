"""Google Cloud Storage helpers for face photo upload/download."""

import logging

from google.cloud import storage

from backend.config import settings

logger = logging.getLogger(__name__)

_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _client
    if _client is None:
        _client = storage.Client()
    return _client


def _get_bucket():
    return _get_client().bucket(settings.GCS_BUCKET_NAME)


async def upload_face_photo(name: str, photo_bytes: bytes) -> str:
    """Upload a face photo to GCS. Returns the GCS path."""
    import asyncio

    gcs_path = f"{settings.GCS_FACES_PREFIX}{name.lower().replace(' ', '_')}.jpg"

    def _upload():
        blob = _get_bucket().blob(gcs_path)
        blob.upload_from_string(photo_bytes, content_type="image/jpeg")

    await asyncio.get_event_loop().run_in_executor(None, _upload)
    logger.info("Uploaded face photo: %s", gcs_path)
    return gcs_path


async def download_face_photo(gcs_path: str) -> bytes | None:
    """Download a face photo from GCS. Returns bytes or None."""
    import asyncio

    def _download():
        blob = _get_bucket().blob(gcs_path)
        if not blob.exists():
            return None
        return blob.download_as_bytes()

    result = await asyncio.get_event_loop().run_in_executor(None, _download)
    return result
