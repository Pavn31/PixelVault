import io
import json
import mimetypes
import posixpath
import zipfile
from dataclasses import dataclass

from apps.container_format.errors import ContainerFormatError, ContainerLimitError
from apps.container_format.format import ContainerHeader, PixelVaultContainer
from apps.container_format.spec import (
    CURRENT_VERSION,
    MAX_FILES_PER_PAYLOAD,
    MAX_MANIFEST_BYTES,
    MAX_DECOMPRESSED_PAYLOAD_BYTES,
)
from apps.crypto.service import EncryptedPayload, decrypt_payload, encrypt_payload


@dataclass(frozen=True)
class InputFile:
    name: str
    content: bytes
    content_type: str | None = None


@dataclass(frozen=True)
class RecoveredFile:
    name: str
    content: bytes
    content_type: str


def _safe_name(name: str) -> str:
    normalized = posixpath.normpath(name.replace("\\", "/"))
    if normalized in {"", ".", ".."} or normalized.startswith("../") or normalized.startswith("/"):
        raise ContainerFormatError("unsafe file name")
    if any(part in {"", ".", ".."} for part in normalized.split("/")):
        raise ContainerFormatError("unsafe file name")
    return normalized


def _guess_content_type(name: str, provided: str | None) -> str:
    return provided or mimetypes.guess_type(name)[0] or "application/octet-stream"


def _build_archive(files: list[InputFile]) -> bytes:
    if not files:
        raise ContainerFormatError("at least one file is required")
    if len(files) > MAX_FILES_PER_PAYLOAD:
        raise ContainerLimitError("too many files")
    manifest = []
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for index, item in enumerate(files):
            safe_name = _safe_name(item.name)
            archive_name = f"files/{index:04d}"
            content_type = _guess_content_type(safe_name, item.content_type)
            manifest.append({"name": safe_name, "archive_name": archive_name, "content_type": content_type})
            output.writestr(archive_name, item.content)
        manifest_bytes = json.dumps(
            {"version": CURRENT_VERSION, "files": manifest}, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        if len(manifest_bytes) > MAX_MANIFEST_BYTES:
            raise ContainerLimitError("manifest exceeds the configured size limit")
        output.writestr("manifest.json", manifest_bytes)
    return archive.getvalue()


def _read_archive(payload: bytes) -> list[RecoveredFile]:
    if len(payload) > MAX_DECOMPRESSED_PAYLOAD_BYTES:
        raise ContainerLimitError("payload exceeds the configured size limit")
    with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
        names = archive.namelist()
        if "manifest.json" not in names:
            raise ContainerFormatError("manifest is missing")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("version") != CURRENT_VERSION:
            raise ContainerFormatError("unsupported payload version")
        entries = manifest.get("files")
        if not isinstance(entries, list) or not entries or len(entries) > MAX_FILES_PER_PAYLOAD:
            raise ContainerFormatError("invalid file manifest")
        total_size = 0
        recovered = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ContainerFormatError("invalid manifest entry")
            name = _safe_name(str(entry.get("name", "")))
            archive_name = str(entry.get("archive_name", ""))
            if archive_name not in names or not archive_name.startswith("files/"):
                raise ContainerFormatError("invalid archive member")
            info = archive.getinfo(archive_name)
            total_size += info.file_size
            if total_size > MAX_DECOMPRESSED_PAYLOAD_BYTES:
                raise ContainerLimitError("expanded payload exceeds the configured size limit")
            recovered.append(RecoveredFile(name, archive.read(archive_name), str(entry.get("content_type", "application/octet-stream"))))
        return recovered


def create_container(carrier: bytes, files: list[InputFile], passcode: str, recovery_secret: str = "") -> PixelVaultContainer:
    archive = _build_archive(files)
    associated_data = b"PVLT\x01"
    encrypted = encrypt_payload(archive, passcode, associated_data, recovery_secret)
    header = ContainerHeader(
        version=CURRENT_VERSION,
        flags=0,
        carrier_length=len(carrier),
        ciphertext_length=len(encrypted.ciphertext),
        salt=encrypted.salt,
        nonce=encrypted.nonce,
    )
    return PixelVaultContainer(carrier=carrier, header=header, ciphertext=encrypted.ciphertext)


def decrypt_container(container: PixelVaultContainer, passcode: str, recovery_secret: str = "") -> list[RecoveredFile]:
    encrypted = EncryptedPayload(
        salt=container.header.salt,
        nonce=container.header.nonce,
        ciphertext=container.ciphertext,
    )
    archive = decrypt_payload(encrypted, passcode, b"PVLT\x01", recovery_secret)
    return _read_archive(archive)


def zip_recovered_files(files: list[RecoveredFile]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            archive.writestr(_safe_name(item.name), item.content)
    return output.getvalue()
