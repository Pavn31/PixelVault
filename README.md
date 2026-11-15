# PixelVault

Secure, image-based data hiding and recovery for multi-file payloads.

PixelVault packages permitted files—including documents, images, video, and audio—into a portable `.pvlt` container. The carrier image is preserved inside the container, while the payload is packaged, authenticated, and encrypted with AES-256-GCM.

> PixelVault is a privacy tool, not a promise of anonymity. A six-character passcode should be paired with a recovery secret for sensitive data.

## Features

- Vanilla HTML, CSS, and JavaScript interface
- Django REST Framework API
- Multiple files per encoding operation
- PNG, JPEG, WEBP, GIF, BMP, and SVG carrier validation
- Encrypted ZIP payload with original filenames and contents preserved
- Portable, independently recoverable `.pvlt` output
- Argon2id key derivation with unique salts
- AES-256-GCM authenticated encryption with unique nonces
- Six-character passcodes using letters, numbers, and safe symbols
- Optional 8–128 character recovery secret
- CSRF protection and rate-limited decoder attempts
- ClamAV malware scanning
- ZIP traversal and decompression-bomb protections
- FFprobe media validation and FFmpeg video-frame sampling
- Celery/Redis processing and temporary-file cleanup
- PostgreSQL job, file-hash, moderation, and audit metadata
- Docker, Nginx, and production security settings

## Architecture

```text
Browser
  → Nginx
  → Django REST API
  → validation and moderation
  → ZIP packaging
  → Argon2id + AES-256-GCM
  → versioned PixelVault container
  → downloadable .pvlt file
```

The container stores the carrier bytes, versioned metadata, cryptographic parameters, and encrypted payload together. Recovery does not depend on the original browser session or temporary server files.

## Important security model

The six-character passcode is stronger than a six-digit PIN but is still short enough to require care. For sensitive payloads, set a recovery secret of at least eight characters. The secret is combined with the passcode during Argon2id derivation and is never stored in the database.

Never transfer the `.pvlt` file and its passcode/recovery secret through the same channel. Services that recompress or transform uploads may damage recoverability.

## Moderation and safety

PixelVault performs layered checks before encryption and again before recovered files are released:

1. Filename, MIME, signature, and size validation.
2. ClamAV malware scanning.
3. Safe archive inspection with traversal, expansion-size, file-count, and compression-ratio limits.
4. FFprobe validation for video and audio.
5. FFmpeg sampling of video frames.
6. A configured, vetted media moderation provider for image, video-frame, and audio decisions.

The provider must return JSON in this shape:

```json
{"decision":"allow","labels":[]}
```

Labels such as `csam`, `child_sexual_abuse`, `pornography`, `sexual_explicit`, `gore`, and `graphic_violence` are rejected. PixelVault does not ship or invent a classifier; production must configure a provider capable of making those decisions. If required moderation infrastructure is unavailable, production requests fail closed.

Do not preview, expose, or manually distribute suspected CSAM. Follow applicable law and authorized incident-response procedures.

## Local setup on Arch Linux

Requirements:

- Docker Engine
- Docker Compose plugin
- Git

Start the development stack:

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec web python manage.py migrate
```

Open:

- `http://localhost:8080/`
- `http://localhost:8080/encoder/`
- `http://localhost:8080/decoder/`

For local development without a configured moderation provider, use:

```env
PIXELVAULT_CLAMAV_REQUIRED=false
PIXELVAULT_MEDIA_MODERATION_REQUIRED=false
```

These settings must be `true` in production after ClamAV, FFmpeg, and the vetted media provider are configured.

## Environment variables

Copy `.env.example` to `.env` and set at minimum:

```env
DJANGO_SECRET_KEY=use-a-long-random-secret
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=your-domain.example
POSTGRES_PASSWORD=use-a-strong-database-password
POSTGRES_HOST=db
REDIS_URL=redis://redis:6379/0
```

Generate a Django secret with:

```bash
openssl rand -hex 32
```

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health/` | Service health check |
| GET | `/api/csrf/` | Obtain a CSRF cookie/token |
| POST | `/api/encode/` | Multipart `carrier`, repeated `files`, optional `recovery_secret` |
| POST | `/api/decode/` | Multipart `container`, `passcode`, optional `recovery_secret` |

The encode response is a `.pvlt` download and exposes the generated passcode in a response header for the current UI. Do not log or persist that header in production infrastructure.

## Tests and checks

```bash
DJANGO_SECRET_KEY=test-secret DJANGO_DEBUG=true pytest -q
DJANGO_SECRET_KEY=test-secret DJANGO_DEBUG=true python manage.py check
node --check frontend/app.js
```

## Production checklist

- Use HTTPS with a real domain and certificates.
- Set `DJANGO_DEBUG=false`.
- Set a precise `DJANGO_ALLOWED_HOSTS` value.
- Set moderation requirements to `true`.
- Configure ClamAV signatures and a vetted media moderation provider.
- Run migrations before accepting traffic.
- Back up PostgreSQL metadata securely.
- Keep temporary storage on encrypted disks and verify cleanup tasks.
- Expose only ports 80 and 443 publicly.
- Monitor Nginx, Gunicorn, Celery, PostgreSQL, and Redis.
- Review retention, incident-response, and reporting policies with qualified legal and security teams.

## Project structure

```text
config/                 Django settings, URLs, ASGI/WSGI, Celery
apps/api/               REST endpoints
apps/container_format/  Versioned `.pvlt` serializer
apps/crypto/            Argon2id and AES-256-GCM
apps/encoding/          ZIP packaging and recovery
apps/moderation/        ClamAV, FFmpeg, archive, provider checks
apps/security/          Jobs, hashes, moderation events, audit records
apps/storage/           Temporary-file cleanup task
apps/validation/        Upload validation
frontend/               Vanilla HTML, CSS, and JavaScript
deployment/             Nginx configuration
tests/                  Unit tests
```
