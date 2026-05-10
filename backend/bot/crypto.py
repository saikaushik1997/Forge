from cryptography.fernet import Fernet
from config import settings


def _fernet() -> Fernet:
    return Fernet(settings.forge_encryption_key.encode())


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    return _fernet().decrypt(encrypted.encode()).decode()
