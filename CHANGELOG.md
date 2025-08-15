Changelog

All notable changes to this project will be documented in this file.
This project adheres to Semantic Versioning (semver.org) and follows a simplified Keep a Changelog style.

## v1.0.0 — 2025-08-15

### Added
- Multi-file and folder upload support in the UI and API
- Health check endpoint at `/health`
- CORS configuration via `ALLOWED_ORIGINS` and `RENDER_EXTERNAL_URL`
- Env-configurable limits: `MAX_UPLOAD_MB` (default 20MB). `MAX_FILES` and `MAX_IMAGES` are unlimited by default and can be enabled via env vars
- Favicon route to avoid 404s

### Improved
- Robust Excel image extraction: resolves drawing relationships, supports anchors, ensures deterministic ordering
- Error handling and input validation with clear messages
- Static UI/UX polish (Bootstrap), progress indicator, and download flow

### Deployment
- Render-ready configuration (`render.yaml`, Procfile) and FastAPI/uvicorn startup

### Notes
- Current default behavior: unlimited number of files and images per file; per-file upload size remains capped at 20MB by default for safety


