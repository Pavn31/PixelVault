import secrets
import string
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PASSCODE_LENGTH = 6
PASSCODE_ALPHABET = string.ascii_letters + string.digits + "!@#$%&*+-=?"
SALT_BYTES = 16
NONCE_BYTES = 12
KEY_BYTES = 32


@dataclass(frozen=True)
class EncryptedPayload:
    salt: bytes
    nonce: bytes
    ciphertext: bytes


def generate_passcode() -> str:
    groups = [string.ascii_uppercase, string.ascii_lowercase, string.digits, "!@#$%&*+-=?"]
    code = [secrets.choice(group) for group in groups]
    code.extend(secrets.choice(PASSCODE_ALPHABET) for _ in range(PASSCODE_LENGTH - len(code)))
    secrets.SystemRandom().shuffle(code)
    return "".join(code)


def derive_key(passcode: str, salt: bytes, recovery_secret: str = "") -> bytes:
    if len(passcode) != PASSCODE_LENGTH or any(character not in PASSCODE_ALPHABET for character in passcode):
        raise ValueError("passcode must contain exactly six supported characters")
    if len(recovery_secret) > 128:
        raise ValueError("recovery secret is too long")
    secret = passcode.encode("ascii") + b"\x00" + recovery_secret.encode("utf-8")
    return hash_secret_raw(
        secret=secret,
        salt=salt,
        time_cost=3,
        memory_cost=64 * 1024,
        parallelism=2,
        hash_len=KEY_BYTES,
        type=Type.ID,
    )


def encrypt_payload(payload: bytes, passcode: str, associated_data: bytes = b"", recovery_secret: str = "") -> EncryptedPayload:
    salt = secrets.token_bytes(SALT_BYTES)
    nonce = secrets.token_bytes(NONCE_BYTES)
    key = derive_key(passcode, salt, recovery_secret)
    ciphertext = AESGCM(key).encrypt(nonce, payload, associated_data)
    return EncryptedPayload(salt=salt, nonce=nonce, ciphertext=ciphertext)


def decrypt_payload(encrypted: EncryptedPayload, passcode: str, associated_data: bytes = b"", recovery_secret: str = "") -> bytes:
    key = derive_key(passcode, encrypted.salt, recovery_secret)
    return AESGCM(key).decrypt(encrypted.nonce, encrypted.ciphertext, associated_data)
