"""
Шифрование данных пользователя.
Ключ генерируется индивидуально для каждого пользователя (SECRET_KEY + user.pk),
поэтому данные одного пользователя недоступны другим.
"""
import base64
import hashlib
from django.conf import settings
from cryptography.fernet import Fernet


def _get_user_fernet(user) -> Fernet:
    """Создаёт Fernet-инстанс с ключом, уникальным для пользователя."""
    raw_key = hashlib.sha256(
        (settings.SECRET_KEY + str(user.pk)).encode()
    ).digest()
    key = base64.urlsafe_b64encode(raw_key)
    return Fernet(key)


def encrypt_for_user(user, plaintext: str) -> str:
    """
    Шифрует строку для конкретного пользователя.
    Возвращает base64-encoded ciphertext.
    """
    if not plaintext:
        return ""
    f = _get_user_fernet(user)
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_for_user(user, ciphertext: str) -> str:
    """
    Расшифровывает строку для конкретного пользователя.
    Возвращает plaintext или пустую строку при ошибке.
    """
    if not ciphertext:
        return ""
    try:
        f = _get_user_fernet(user)
        return f.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except Exception:
        return ""
