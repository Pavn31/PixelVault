<p align="center">
  <img src="assets/Icon.jpeg" alt="PixelVault logo" width="120">
</p>

<h1 align="center">PixelVault</h1>

<p align="center">
  Secure, portable data hiding with encrypted image-compatible containers.
</p>

<p align="center">
  <a href="https://pixelvault.pavn31.dpdns.org">Live app</a>
  ·
  <a href="https://github.com/Pavn31/PixelVault">Repository</a>
</p>

## What it does

PixelVault packages multiple permitted files into a self-contained .pvlt file protected by authenticated encryption.

| Capability | Details |
|---|---|
| Encoding | Carrier image + multiple files |
| Recovery | Original files and filenames preserved |
| Encryption | AES-256-GCM |
| Key derivation | Argon2id |
| Passcode | Six-character mixed passcode |
| Large files | Video and audio supported as encrypted payloads |
| Interface | Vanilla HTML, CSS, and JavaScript |
| Backend | Django REST Framework |
| Deployment | Docker, Nginx, PostgreSQL, Redis, Celery |

## Security

- Unique salts and nonces for every container
- Optional recovery secret for sensitive files
- MIME, signature, size, and filename validation
- ClamAV malware scanning
- Archive traversal and decompression-bomb protection
- FFprobe and FFmpeg media inspection
- Configurable media moderation provider
- CSRF protection and decoder rate limiting

A short passcode is not enough against unlimited offline guessing. Use the optional recovery secret for sensitive data.

## Quick start

Requirements:

- Docker
- Docker Compose
- Git

~~~bash
git clone https://github.com/Pavn31/PixelVault.git
cd PixelVault
cp .env.example .env
docker compose up --build -d
docker compose exec web python manage.py migrate
~~~

Open:

~~~text
http://localhost:8080/
~~~

## Environment

Generate a Django secret:

~~~bash
openssl rand -hex 32
~~~

For local development, configure .env with your database, Redis, and moderation settings. Keep required moderation checks enabled in production.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/health/ | Health check |
| GET | /api/csrf/ | CSRF token |
| POST | /api/encode/ | Create a .pvlt file |
| POST | /api/decode/ | Recover files as a ZIP |

## Development checks

~~~bash
DJANGO_SECRET_KEY=test-secret DJANGO_DEBUG=true pytest -q
DJANGO_SECRET_KEY=test-secret DJANGO_DEBUG=true python manage.py check
node --check frontend/app.js
~~~

## Project structure

~~~text
apps/          Django API, crypto, packaging, moderation, security
config/        Django and Celery configuration
frontend/      HTML, CSS, and Vanilla JavaScript
deployment/    Nginx configuration
tests/         Unit tests
~~~

## License

Add a license before public production distribution.

