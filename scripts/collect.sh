#!/bin/bash
set -e
cd "$(dirname "$0")/.."
dotenvx run -- uv run python -m fandom_dashboard.run
