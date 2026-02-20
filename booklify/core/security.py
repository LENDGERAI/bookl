from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet

from booklify.core.config import get_settings


class SecurityService:
    def __init__(self, key: str | None = None) -> None:
        settings = get_settings()
        selected_key = key or settings.encryption_key
        if selected_key:
            token = selected_key.encode("utf-8")
        else:
            token = Fernet.generate_key()
        self._fernet = Fernet(token)

    def hash_bytes(self, payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def encrypt_text(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt_text(self, token: str) -> str:
        return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")

    @staticmethod
    def random_token(byte_length: int = 32) -> str:
        return base64.urlsafe_b64encode(os.urandom(byte_length)).decode("utf-8")

