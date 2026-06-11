#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
BASE=/data/data/com.termux/files/home/bot
cd "$BASE"
PIDFILE="$BASE/bot.pid"
PORT="${PORT:-5000}"

stop_bot(){
  if [ -f "$PIDFILE" ]; then
    oldpid=$(cat "$PIDFILE" || true)
    if [ -n "${oldpid:-}" ] && kill -0 "$oldpid" 2>/dev/null; then
      kill "$oldpid" >/dev/null 2>&1 || true
      for i in {1..20}; do
        sleep 0.3
        kill -0 "$oldpid" 2>/dev/null || break
      done
      kill -9 "$oldpid" >/dev/null 2>&1 || true
      sleep 0.3
    fi
    rm -f "$PIDFILE" || true
  fi
}

# Remove stale listener on the same port if any
pkill -f "python3 -u bot/server.py" >/dev/null 2>&1 || true
sleep 0.5

MODE="${MODE:-demo}" PORT="$PORT" /data/data/com.termux/files/usr/bin/python3.13 -u bot/server.py > "$BASE/bot.log" 2>&1 &
echo $! > "$PIDFILE"
disown || true
echo "bot started pid=$(cat "$PIDFILE") port=$PORT"
