import hashlib
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.utils import timezone
from django.http import FileResponse, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view, parser_classes, throttle_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.throttling import AnonRateThrottle

from apps.container_format.format import deserialize, serialize
from apps.crypto.service import generate_passcode
from apps.encoding.packaging import InputFile, create_container, decrypt_container
from apps.moderation.errors import ModerationError, ModerationRejected, ModerationUnavailable
from apps.moderation.service import moderate_file
from apps.security.models import AuditEvent, FileRecord, JobStatus, ModerationEvent, ProcessingJob
from apps.validation.errors import ValidationError
from apps.validation.service import read_limited, validate_carrier, validate_payload


class DecodeThrottle(AnonRateThrottle):
    scope = "decode"


def _moderate_files(files):
    """Run independent moderation jobs concurrently, keeping input order."""
    worker_count = min(4, len(files))
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="moderation") as executor:
        return list(
            executor.map(
                lambda item: (item[0], moderate_file(item[1], item[0], item[2])),
                files,
            )
        )


def health(_request):
    return JsonResponse({"service": "pixelvault", "status": "ok", "version": "0.1.0"})


@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"csrfToken": get_token(request)})


@api_view(["POST"])
@parser_classes([MultiPartParser])
@throttle_classes([AnonRateThrottle])
def encode(request):
    carrier_upload = request.FILES.get("carrier")
    payload_uploads = request.FILES.getlist("files")
    if carrier_upload is None or not payload_uploads:
        return JsonResponse({"error": "carrier and at least one file are required"}, status=400)
    recovery_secret = request.data.get("recovery_secret", "")
    if not isinstance(recovery_secret, str) or (recovery_secret and len(recovery_secret) < 8) or len(recovery_secret) > 128:
        return JsonResponse({"error": "recovery secret must be empty or 8–128 characters"}, status=400)
    try:
        carrier = read_limited(carrier_upload)
        validate_carrier(carrier, carrier_upload.name, carrier_upload.content_type)
        moderation_inputs = [(carrier_upload.name, carrier, carrier_upload.content_type)]
        inputs = []
        for upload in payload_uploads:
            content = read_limited(upload)
            validate_payload(upload.name, content)
            moderation_inputs.append((upload.name, content, upload.content_type))
            inputs.append(InputFile(upload.name, content, upload.content_type))
        reports = _moderate_files(moderation_inputs)
        passcode = generate_passcode()
        blob = serialize(create_container(carrier, inputs, passcode, recovery_secret))
    except ValidationError as error:
        return JsonResponse({"error": str(error)}, status=400)
    except ModerationRejected as error:
        return JsonResponse({"error": str(error), "code": "moderation_rejected"}, status=422)
    except ModerationUnavailable as error:
        return JsonResponse({"error": str(error), "code": "moderation_unavailable"}, status=503)
    except ModerationError as error:
        return JsonResponse({"error": str(error), "code": "moderation_error"}, status=503)
    job = ProcessingJob.objects.create(
        operation="encode",
        status=JobStatus.COMPLETE,
        input_bytes=len(carrier) + sum(len(item.content) for item in inputs),
        output_bytes=len(blob),
        file_count=len(inputs),
        container_sha256=hashlib.sha256(blob).hexdigest(),
        completed_at=timezone.now(),
    )
    for name, report in reports:
        ModerationEvent.objects.create(job=job, status=report.status, check_name=",".join(report.checks)[:64])
    for item in inputs:
        FileRecord.objects.create(
            job=job,
            original_name=item.name,
            content_type=item.content_type or "",
            size_bytes=len(item.content),
            sha256=hashlib.sha256(item.content).hexdigest(),
        )
    AuditEvent.objects.create(job=job, event_type="encoding_complete", detail={"file_count": len(inputs)})
    response = FileResponse(
        iter([blob]),
        as_attachment=True,
        filename="pixelvault.pvlt",
        content_type="application/octet-stream",
    )
    response["X-PixelVault-Passcode"] = passcode
    response["X-PixelVault-Job-ID"] = str(job.id)
    response["X-PixelVault-Moderation"] = "complete"
    response["Access-Control-Expose-Headers"] = "X-PixelVault-Passcode, X-PixelVault-Job-ID, X-PixelVault-Moderation, Content-Disposition"
    return response


@api_view(["POST"])
@parser_classes([MultiPartParser])
@throttle_classes([DecodeThrottle])
def decode(request):
    container_upload = request.FILES.get("container")
    passcode = request.data.get("passcode", "")
    if container_upload is None or not isinstance(passcode, str) or len(passcode) != 6:
        return JsonResponse({"error": "container and a six-character passcode are required"}, status=400)
    recovery_secret = request.data.get("recovery_secret", "")
    if not isinstance(recovery_secret, str) or (recovery_secret and len(recovery_secret) < 8) or len(recovery_secret) > 128:
        return JsonResponse({"error": "recovery secret must be empty or 8–128 characters"}, status=400)
    try:
        blob = read_limited(container_upload, settings.PIXELVAULT_MAX_UPLOAD_BYTES * 2)
        parsed = deserialize(blob)
        recovered = decrypt_container(parsed, passcode, recovery_secret)
        for item in recovered:
            moderate_file(item.content, item.name, item.content_type)
    except ModerationRejected as error:
        return JsonResponse({"error": str(error), "code": "moderation_rejected"}, status=422)
    except ModerationUnavailable as error:
        return JsonResponse({"error": str(error), "code": "moderation_unavailable"}, status=503)
    except Exception:
        return JsonResponse({"error": "container or passcode is invalid"}, status=400)
    from apps.encoding.packaging import zip_recovered_files

    archive = zip_recovered_files(recovered)
    return FileResponse(iter([archive]), as_attachment=True, filename="pixelvault-recovered.zip", content_type="application/zip")
