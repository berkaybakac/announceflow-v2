# AnnounceFlow V2 — Developer Survival Guide

## Setup & Run
- `python3.11 -m venv .venv`
- `source .venv/bin/activate`
- `python -m pip install -r backend/requirements.txt`
- `cp .env.example .env` and fill required values
- `docker compose -f docker-compose.dev.yml up -d db`
- `./.venv/bin/alembic -c backend/alembic.ini upgrade head`
- `./.venv/bin/uvicorn backend.main:app --reload`

## Critical Gotcha
- `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` is mandatory because PyTorch 2.6+ defaults `torch.load` to `weights_only=True`, which breaks Coqui XTTS checkpoint loading.

## Voice Registry Rule
- Do not change code when adding a new voice alias; only update `backend/config/voice_profiles.json` (`profiles` and optionally `default_profile`).

## Test Strategy
- Fast tests: `pytest -q`
- Real XTTS smoke tests (manual): `pytest -m tts_smoke -o addopts='' -q -s`

## Environment Constraints
- `ffmpeg`
- `ffprobe`
- Python `3.11`
- Internet access for first XTTS model download
