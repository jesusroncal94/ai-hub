#!/usr/bin/env bash
# The one check agents and CI run before calling a change done.
# There is no test suite: install the locked dependencies, compile every module and import the app.
set -euo pipefail
cd "$(dirname "$0")/.."

MSYS_NO_PATHCONV=1 docker run --rm \
  -v "$(pwd -W 2>/dev/null || pwd):/repo:ro" -w /repo \
  -e UV_PROJECT_ENVIRONMENT=/tmp/venv -e UV_CACHE_DIR=/tmp/uv-cache -e AI_HUB_DATA_DIR=/tmp/ai-hub-data -e PYTHONPYCACHEPREFIX=/tmp/pycache \
  ghcr.io/astral-sh/uv:0.9-python3.13-bookworm-slim \
  sh -c 'uv sync --frozen && uv run --no-sync python -m compileall -q src && uv run --no-sync python -c "import ai_hub.app"'
