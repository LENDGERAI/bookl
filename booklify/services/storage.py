from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from booklify.core.config import get_settings
from booklify.core.security import SecurityService

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".csv", ".xlsx", ".xls", ".txt"}


@dataclass(slots=True)
class StoredFile:
    original_filename: str
    normalized_filename: str
    content_type: str
    file_hash: str
    path: Path
    size_bytes: int


class StorageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.security = SecurityService()

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", filename.strip()) or "document"
        return cleaned[-200:]

    @staticmethod
    def validate_filename(filename: str) -> None:
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}")

    def persist(self, business_id: str, filename: str, payload: bytes, content_type: str) -> StoredFile:
        if not payload:
            raise ValueError("Empty file payload.")
        self.validate_filename(filename)

        safe_name = self._sanitize_filename(filename)
        hashed = self.security.hash_bytes(payload)
        day_partition = datetime.now(timezone.utc).strftime("%Y%m%d")
        target_dir = self.settings.upload_path / business_id / day_partition
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{hashed}_{safe_name}"
        target_path.write_bytes(payload)

        return StoredFile(
            original_filename=filename,
            normalized_filename=safe_name,
            content_type=content_type or "application/octet-stream",
            file_hash=hashed,
            path=target_path,
            size_bytes=len(payload),
        )

