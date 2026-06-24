import base64
import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken

from app.settings import get_settings


def _derive_fernet_key(raw: str) -> bytes:
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    settings = get_settings()
    key_source = settings.token_encrypt_key or settings.jwt_secret
    return Fernet(_derive_fernet_key(key_source))


def encrypt_secret(value: str) -> str:
    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    try:
        return _get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("无法解密 Bot Token，请检查 TOKEN_ENCRYPT_KEY") from exc


def token_hint(token: str) -> str:
    token = token.strip()
    if len(token) <= 8:
        return "****"
    return f"****{token[-4:]}"


def secret_fingerprint(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def apply_user_password(user, password: str) -> None:
    user.password_hash = password
    user.password_plain = password


def _is_legacy_hashed_password(stored: str) -> bool:
    if "$" not in stored:
        return False
    salt, _digest = stored.split("$", 1)
    return len(salt) == 32 and len(_digest) == 64


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    )
    return f"{salt}${digest.hex()}"


def user_password_for_display(user) -> str | None:
    if user.password_plain:
        return user.password_plain
    stored = user.password_hash or ""
    if stored and not _is_legacy_hashed_password(stored):
        return stored
    return None


def verify_password(password: str, stored: str) -> bool:
    if _is_legacy_hashed_password(stored):
        try:
            salt, hex_digest = stored.split("$", 1)
        except ValueError:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
        )
        return secrets.compare_digest(digest.hex(), hex_digest)
    return secrets.compare_digest(password, stored)
