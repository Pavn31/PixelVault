import uuid

from django.conf import settings
from django.db import models


class JobStatus(models.TextChoices):
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"
    FAILED = "failed", "Failed"
    COMPLETE = "complete", "Complete"


class ProcessingJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    operation = models.CharField(max_length=16)
    status = models.CharField(max_length=16, choices=JobStatus.choices)
    input_bytes = models.PositiveBigIntegerField(default=0)
    output_bytes = models.PositiveBigIntegerField(default=0)
    file_count = models.PositiveIntegerField(default=0)
    container_sha256 = models.CharField(max_length=64, blank=True)
    failure_code = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class FileRecord(models.Model):
    job = models.ForeignKey(ProcessingJob, related_name="files", on_delete=models.CASCADE)
    original_name = models.CharField(max_length=240)
    content_type = models.CharField(max_length=160, blank=True)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    released = models.BooleanField(default=False)


class ModerationEvent(models.Model):
    job = models.ForeignKey(ProcessingJob, related_name="moderation_events", on_delete=models.CASCADE)
    status = models.CharField(max_length=32)
    check_name = models.CharField(max_length=64)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(models.Model):
    job = models.ForeignKey(ProcessingJob, null=True, blank=True, on_delete=models.SET_NULL)
    event_type = models.CharField(max_length=64)
    remote_hash = models.CharField(max_length=64, blank=True)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
