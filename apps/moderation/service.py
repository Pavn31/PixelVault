import io
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from apps.container_format.spec import MAX_DECOMPRESSED_PAYLOAD_BYTES, MAX_FILES_PER_PAYLOAD

from .errors import ModerationRejected, ModerationUnavailable


@dataclass(frozen=True)
class ModerationReport:
    status: str
    checks: tuple[str, ...]


def _clamav_binary() -> str | None:
    configured = os.getenv("PIXELVAULT_CLAMAV_BINARY", "clamscan")
    return shutil.which(configured)


def scan_with_clamav(content: bytes, filename: str) -> str:
    binary = _clamav_binary()
    required = getattr(settings, "PIXELVAULT_CLAMAV_REQUIRED", True)
    if binary is None:
        if required:
            raise ModerationUnavailable("ClamAV scanner is not available")
        return "clamav-unavailable-development-mode"
    temporary_root = Path(settings.BASE_DIR) / "temporary"
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="scan-", suffix=".bin", dir=temporary_root, delete=False) as temporary:
        temporary.write(content)
        temporary_path = temporary.name
    try:
        result = subprocess.run(
            [binary, "--no-summary", temporary_path],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ModerationUnavailable("ClamAV scan could not be completed") from error
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
    if result.returncode == 1:
        raise ModerationRejected(f"malware detected in {filename}")
    if result.returncode != 0:
        if not required:
            return "clamav-indeterminate-development-mode"
        raise ModerationUnavailable("ClamAV returned an indeterminate result")
    return "clamav-clean"


def inspect_archive(content: bytes, filename: str) -> str | None:
    if not content.startswith(b"PK\x03\x04") and not content.startswith(b"PK\x05\x06"):
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            members = archive.infolist()
            if len(members) > MAX_FILES_PER_PAYLOAD:
                raise ModerationRejected(f"archive contains too many files: {filename}")
            expanded = sum(member.file_size for member in members)
            if expanded > MAX_DECOMPRESSED_PAYLOAD_BYTES:
                raise ModerationRejected(f"archive expands beyond the configured limit: {filename}")
            for member in members:
                normalized = member.filename.replace("\\", "/")
                if normalized.startswith("/") or any(part in {"", ".", ".."} for part in normalized.split("/")):
                    raise ModerationRejected(f"archive contains an unsafe path: {filename}")
                if member.compress_size and member.file_size / member.compress_size > 1000:
                    raise ModerationRejected(f"archive has an unsafe compression ratio: {filename}")
    except zipfile.BadZipFile as error:
        raise ModerationRejected(f"malformed archive: {filename}") from error
    return "archive-safe"


def inspect_media_provider(content: bytes, filename: str, content_type: str | None) -> str:
    """Invoke the configured external media classifier when one is configured.

    PixelVault deliberately does not ship an invented classifier. Production must
    configure a vetted provider for image/video/audio policy enforcement.
    """
    if not content_type or not (
        content_type.startswith("image/")
        or content_type.startswith("video/")
        or content_type.startswith("audio/")
    ):
        return "media-check-not-required"
    required = getattr(settings, "PIXELVAULT_MEDIA_MODERATION_REQUIRED", True)
    command = os.getenv("PIXELVAULT_MEDIA_MODERATION_COMMAND")
    if not command:
        if required:
            raise ModerationUnavailable("media moderation provider is not configured")
        return "media-provider-unavailable-development-mode"
    ffprobe = shutil.which(os.getenv("PIXELVAULT_FFPROBE_BINARY", "ffprobe"))
    ffmpeg = shutil.which(os.getenv("PIXELVAULT_FFMPEG_BINARY", "ffmpeg"))
    temporary_root = Path(settings.BASE_DIR) / "temporary"
    temporary_root.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix or ".bin"
    with tempfile.NamedTemporaryFile(prefix="media-", suffix=suffix, dir=temporary_root, delete=False) as temporary:
        temporary.write(content)
        temporary_path = temporary.name
    try:
        if not ffprobe or not ffmpeg:
            if required:
                raise ModerationUnavailable("FFmpeg media inspection tools are not available")
            return "media-runtime-unavailable-development-mode"
        probe = subprocess.run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", temporary_path], capture_output=True, text=True, timeout=120, check=False)
        if probe.returncode != 0:
            raise ModerationRejected(f"malformed media container: {filename}")
        probe_data = json.loads(probe.stdout or "{}")
        streams = probe_data.get("streams", [])
        if not streams:
            raise ModerationRejected(f"media has no readable streams: {filename}")
        media_paths = [(temporary_path, content_type or "application/octet-stream")]
        if content_type.startswith("video/"):
            with tempfile.TemporaryDirectory(prefix="frames-", dir=temporary_root) as frame_directory:
                frame_pattern = str(Path(frame_directory) / "frame-%03d.png")
                frame_result = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", temporary_path, "-vf", "fps=1/5,scale=640:-2", "-frames:v", "12", frame_pattern], capture_output=True, text=True, timeout=300, check=False)
                if frame_result.returncode != 0:
                    raise ModerationUnavailable("video frame extraction failed")
                frame_paths = sorted(Path(frame_directory).glob("frame-*.png"))
                if not frame_paths:
                    raise ModerationRejected(f"video contains no inspectable frames: {filename}")
                for frame_path in frame_paths:
                    media_paths.append((str(frame_path), "image/png"))
                for media_path, media_type in media_paths[1:]:
                    _run_media_classifier(command, media_path, media_type, filename)
        else:
            _run_media_classifier(command, temporary_path, content_type, filename)
        return "media-provider-allow"
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ModerationUnavailable("media moderation could not be completed") from error
    except json.JSONDecodeError as error:
        raise ModerationUnavailable("FFprobe returned invalid media metadata") from error
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass


def _run_media_classifier(command: str, media_path: str, content_type: str, filename: str) -> None:
    result = subprocess.run([*shlex.split(command), media_path, content_type], capture_output=True, text=True, timeout=300, check=False)
    if result.returncode == 1:
        raise ModerationRejected(f"content moderation rejected {filename}")
    if result.returncode != 0:
        raise ModerationUnavailable("media moderation returned an indeterminate result")
    try:
        result_payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as error:
        raise ModerationUnavailable("media moderation returned invalid output") from error
    prohibited = {"csam", "child_sexual_abuse", "pornography", "sexual_explicit", "gore", "graphic_violence"}
    labels = {str(label).lower() for label in result_payload.get("labels", [])}
    if result_payload.get("decision") != "allow" or labels.intersection(prohibited):
        raise ModerationRejected(f"content moderation rejected {filename}")


def moderate_file(content: bytes, filename: str, content_type: str | None) -> ModerationReport:
    checks = [scan_with_clamav(content, filename)]
    archive_check = inspect_archive(content, filename)
    if archive_check:
        checks.append(archive_check)
    checks.append(inspect_media_provider(content, filename, content_type))
    return ModerationReport(status="allowed", checks=tuple(checks))
