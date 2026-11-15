# PixelVault

Secure, portable data hiding with encrypted image-compatible containers.

PixelVault packages multiple permitted files—including documents, images, video, and audio—into a self-contained `.pvlt` file protected by authenticated encryption.

## Overview

| Area | Implementation |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Backend | Django + Django REST Framework |
| Database | PostgreSQL |
| Encryption | AES-256-GCM |
| Key derivation | Argon2id |
| Packaging | Python `zipfile` |
| Media inspection | Pillow, FFprobe, FFmpeg |
| Malware scanning | ClamAV |
| Background jobs | Celery + Redis |
| Deployment | Docker + Nginx |

## Features

- Multi-file encoding and recovery
- Original filenames, extensions, and contents preserved
- Portable `.pvlt` output with carrier image and encrypted payload together
- Six-character passcode using letters, numbers, and symbols
- Optional recovery secret for sensitive payloads
- AES-GCM integrity authentication
- Upload size, MIME, signature, and filename validation
- Archive traversal and decompression-bomb protection
- ClamAV malware scanning
- FFprobe validation and FFmpeg video-frame sampling
- Configurable media moderation provider
- CSRF protection, throttling, audit metadata, and cleanup jobs
- Dark matte brutalist interface with responsive layouts
- Custom `assets/Icon.jpeg` branding used as the site mark and favicon

## Architecture

```text
Browser → Nginx → Django REST API
                  ↓
       Validation → Moderation → ZIP packaging
                  ↓
       Argon2id + AES-256-GCM
                  ↓
              .pvlt download
```

The `.pvlt` file contains the carrier bytes, versioned container metadata, cryptographic parameters, and encrypted payload. Recovery does not depend on the original browser session.

## Quick start — Arch Linux

Requirements:

- Docker Engine
- Docker Compose plugin
- Git

```bash
git clone https://github.com/Pavn31/PixelVault.git
cd PixelVault
cp .env.example .env
docker compose up --build -d
docker compose exec web python manage.py migrate
```

Open `http://localhost:8080/`.

| Page | URL |
|---|---|
| Home | `http://localhost:8080/` |
| Encoder | `http://localhost:8080/encoder/` |
| Decoder | `http://localhost:8080/decoder/` |
| Health | `http://localhost:8080/api/health/` |

## Environment

Set these values in `.env`:

```env
DJANGO_SECRET_KEY=long-random-secret
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
POSTGRES_DB=pixelvault
POSTGRES_USER=pixelvault
POSTGRES_PASSWORD=strong-local-password
POSTGRES_HOST=db
POSTGRES_PORT=5432
REDIS_URL=redis://redis:6379/0
```

Generate a secret with:

```bash
openssl rand -hex 32
```

For local development without external moderation services:

```env
PIXELVAULT_CLAMAV_REQUIRED=false
PIXELVAULT_MEDIA_MODERATION_REQUIRED=false
```

Keep both values `true` in production after configuring the required scanners and provider.

## API

| Method | Endpoint | Input | Result |
|---|---|---|---|
| `GET` | `/api/health/` | — | Health JSON |
| `GET` | `/api/csrf/` | — | CSRF cookie/token |
| `POST` | `/api/encode/` | `carrier`, repeated `files`, optional `recovery_secret` | `.pvlt` download |
| `POST` | `/api/decode/` | `container`, `passcode`, optional `recovery_secret` | Recovered ZIP |

## Security notes

- Never store or log passcodes or recovery secrets.
- Transfer the encoded file and secret through separate channels.
- A short passcode is not protection against unlimited offline guessing; use the recovery secret for sensitive data.
- Do not upload `.pvlt` files to services that recompress or transform them.
- Production moderation fails closed when required dependencies are unavailable.

### Moderation policy boundary

Production requires a vetted media moderation provider for image, video-frame, and audio decisions. The provider must return JSON such as:

```json
{"decision":"allow","labels":[]}
```

Labels for CSAM, child sexual abuse, pornography, explicit sexual content, gore, or graphic violence are rejected. PixelVault does not claim that any classifier is perfect; confirmed or uncertain cases must follow the operator’s legal and incident-response policy.

## Project structure

```text
apps/api/               REST endpoints
apps/container_format/  Versioned .pvlt serializer
apps/crypto/            Argon2id and AES-256-GCM
apps/encoding/          ZIP packaging and recovery
apps/moderation/        ClamAV, FFmpeg, archive, provider checks
apps/security/          Jobs, hashes, moderation, audit records
apps/storage/           Temporary-file cleanup
apps/validation/        Upload validation
config/                 Django and Celery configuration
frontend/               Vanilla HTML, CSS, and JavaScript
deployment/             Nginx configuration
tests/                  Unit tests
```

## Validation

```bash
DJANGO_SECRET_KEY=test-secret DJANGO_DEBUG=true pytest -q
DJANGO_SECRET_KEY=test-secret DJANGO_DEBUG=true python manage.py check
node --check frontend/app.js
```

## License

Add the project license before public production distribution.

