from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="ProcessingJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("operation", models.CharField(max_length=16)),
                ("status", models.CharField(choices=[("accepted", "Accepted"), ("rejected", "Rejected"), ("failed", "Failed"), ("complete", "Complete")], max_length=16)),
                ("input_bytes", models.PositiveBigIntegerField(default=0)),
                ("output_bytes", models.PositiveBigIntegerField(default=0)),
                ("file_count", models.PositiveIntegerField(default=0)),
                ("container_sha256", models.CharField(blank=True, max_length=64)),
                ("failure_code", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="FileRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("original_name", models.CharField(max_length=240)),
                ("content_type", models.CharField(blank=True, max_length=160)),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("sha256", models.CharField(max_length=64)),
                ("released", models.BooleanField(default=False)),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="files", to="security.processingjob")),
            ],
        ),
        migrations.CreateModel(
            name="ModerationEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(max_length=32)),
                ("check_name", models.CharField(max_length=64)),
                ("detail", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="moderation_events", to="security.processingjob")),
            ],
        ),
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(max_length=64)),
                ("remote_hash", models.CharField(blank=True, max_length=64)),
                ("detail", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("job", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="security.processingjob")),
            ],
        ),
    ]
