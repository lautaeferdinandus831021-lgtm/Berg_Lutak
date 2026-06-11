# Berg_Lutak

Bot trading Bitget USDT-Futures (demo/real) dengan sinyal BB + VD + CVD + DOM. Default mode demo, aman untuk belajar dulu.

## Fitur utama
- Auto polling REST + fallback (WS opsional)
- Configurable: SL/TP, leverage, size, order type (market/limit), spread limit
- Realtime state, stats, export trade via HTTP API
- Daily drawdown guard + analysis-only guard untuk real mode

## Penggunaan `start.sh` (minimal)

```bash
chmod +x start.sh
./start.sh
```

Yang dilakukan `start.sh`:
- membuat virtual env `.venv` jika belum ada
- install dependensi dari `requirements.txt`
- menjalankan bot lewat `python3.13 -u bot/server.py`

Catatan:
- Default mode adalah `demo`
- Port default `5000`
- Untuk stop, matikan proses yang berjalan atau gunakan endpoint `/api/stop`

## Konfigurasi awal
- Salin `.env.example` menjadi `.env`
- Isi `BITGET_API_KEY`, `BITGET_API_SECRET`, `BITGET_PASSPHRASE`
- Demo tidak perlu API key (`DEMO`)
