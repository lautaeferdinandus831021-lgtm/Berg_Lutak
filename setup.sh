#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
REPO_DIR="${1:-.}"
cd "$REPO_DIR"

# 1) Pastikan Python 3.13 tersedia
PYTHON_BIN="$(command -v python3.13 || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "[ERR] python3.13 tidak ditemukan. Install dengan: pkg install python3.13"
  exit 1
fi

# 2) Siapkan venv
if [[ ! -d ".venv" ]]; then
  echo "[SETUP] Membuat virtualenv..."
  "${PYTHON_BIN}" -m venv .venv
fi
source .venv/bin/activate

# 3) Install dependencies
echo "[SETUP] Install requirements..."
python -m pip install --upgrade pip >/dev/null 2>&1 || true
pip install -r requirements.txt

# 4) Siapkan .env dari template
if [[ ! -f ".env" && -f ".env.example" ]]; then
  echo "[SETUP] Membuat .env dari template..."
  cp .env.example .env
  echo "[WARN] Edit .env dan isi API_KEY / SECRET / PASSPHRASE sebelum live."
fi

# 5) Pastikan kredensial Bitget ada (enforced path)
if [[ ! -f "${HOME}/.hermes/secrets/bitget_keys.json" ]]; then
  echo "[WARN] Kredensial Bitget belum ada di ~/.hermes/secrets/bitget_keys.json"
fi

# 6) Jalankan bot
echo "[SETUP] Menjalankan bot..."
exec bash start.sh
