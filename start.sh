#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python3 tidak ditemukan. Install python3 terlebih dahulu."
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

if [ -f "server.py" ]; then
  exec python -u server.py
elif [ -f "bot/server.py" ]; then
  exec python -u bot/server.py
else
  export FLASK_APP=server.py
  exec python -m flask run --host=0.0.0.0 --port=5000
fi
