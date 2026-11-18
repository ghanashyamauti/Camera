import base64
import hashlib
from cryptography.fernet import Fernet
from app.config import settings

def _get_fernet() -> Fernet:
    raw_key = settings.APP_SECRET_KEY.strip()
    if raw_key:
        try:
            return Fernet(raw_key.encode())
        except Exception:
            # Derive a valid 32-byte Fernet key from arbitrary string
            digest = hashlib.sha256(raw_key.encode()).digest()
            return Fernet(base64.urlsafe_b64encode(digest))
    # Fallback deterministic local key if not configured
    digest = hashlib.sha256(b"camera-monitor-default-local-key").digest()
    return Fernet(base64.urlsafe_b64encode(digest))

_fernet = _get_fernet()

def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    return _fernet.encrypt(plain.encode("utf-8")).decode("utf-8")

def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        # Backward safety if a plaintext value somehow existed
        return token
