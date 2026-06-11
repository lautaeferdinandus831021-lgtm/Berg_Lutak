#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_URL="git@github.com:lautaeferdinandus831021-lgtm/Berg_Lutak.git"
INSTALL_DIR="${HOME}/Berg_Lutak"
HERMES_HOME="${HOME}/.hermes"
HERMES_BIN="$(command -v hermes || true)"

echo "=============================================="
echo "  Berg_Lutak + Hermes Auto Setup"
echo "=============================================="

# 1) Clone repo jika belum ada
if [[ ! -d "${INSTALL_DIR}/.git" ]]; then
  echo "[CLONE] Mengclone repo..."
  mkdir -p "${INSTALL_DIR}"
  git clone "${REPO_URL}" "${INSTALL_DIR}"
else
  echo "[CLONE] Repo sudah ada di ${INSTALL_DIR}, skip clone."
fi

cd "${INSTALL_DIR}"

# 2) Install Hermes Agent jika belum ada
if [[ -z "${HERMES_BIN}" ]]; then
  echo "[HERMES] Hermes belum terinstall. Menginstall..."
  npm install -g @nousresearch/hermes-agent || npm install -g hermes-agent || true
  HERMES_BIN="$(command -v hermes || true)"
  if [[ -z "${HERMES_BIN}" ]]; then
    echo "[ERR] Gagal install Hermes. Cek manual: npm install -g hermes-agent"
    exit 1
  fi
else
  echo "[HERMES] Hermes sudah terinstall: ${HERMES_BIN}"
fi

# 3) Setup Hermes home (skills, plugins, profiles)
echo "[HERMES] Setup Hermes home..."
mkdir -p "${HERMES_HOME}/skills"
mkdir -p "${HERMES_HOME}/profiles/berglutak/skills"
mkdir -p "${HERMES_HOME}/profiles/berglutak/plugins"
mkdir -p "${HERMES_HOME}/profiles/berglutak/cron"
mkdir -p "${HERMES_HOME}/profiles/berglutak/memories"

# 4) Copy bot-specific skill untuk Berg_Lutak
BOT_SKILL_DIR="${HERMES_HOME}/profiles/berglutak/skills/berglutak-platform"
if [[ ! -d "${BOT_SKILL_DIR}" ]]; then
  echo "[SKILL] Install berglutak-platform skill..."
  mkdir -p "${BOT_SKILL_DIR}"
  cp -r "${INSTALL_DIR}/scripts"/* "${BOT_SKILL_DIR}/" 2>/dev/null || true
  cp "${INSTALL_DIR}/README.md" "${BOT_SKILL_DIR}/" 2>/dev/null || true
fi

# 5) Install dependencies bot
echo "[BOT] Setup environment..."
if [[ -f "${INSTALL_DIR}/setup_bot.sh" ]]; then
  chmod +x "${INSTALL_DIR}/setup_bot.sh"
  bash "${INSTALL_DIR}/setup_bot.sh"
elif [[ -f "${INSTALL_DIR}/setup.sh" ]]; then
  chmod +x "${INSTALL_DIR}/setup.sh"
  bash "${INSTALL_DIR}/setup.sh" "${INSTALL_DIR}"
else
  echo "[WARN] setup.sh tidak ditemukan, buat manual: python3.13 -m venv .venv && pip install -r requirements.txt"
fi

# 6) Verifikasi akhir
echo ""
echo "=============================================="
echo "  Setup Selesai!"
echo "=============================================="
echo "Repo: ${INSTALL_DIR}"
echo "Hermes: ${HERMES_BIN}"
echo "Profile: ${HERMES_HOME}/profiles/berglutak"
echo ""
echo "Cara pakai:"
echo "  cd ${INSTALL_DIR}"
echo "  hermes --profile berlutak"
echo "  (chat dengan Hermes untuk manage bot)"
echo ""
