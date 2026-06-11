# Berg_Lutak

Bot trading Bitget USDT-Futures (demo/real) dengan sinyal BB + VD + CVD + DOM. Default mode demo, aman untuk belajar dulu.

## Fitur utama
- Auto polling REST + fallback (WS opsional)
- Configurable: SL/TP, leverage, size, order type (market/limit), spread limit
- Realtime state, stats, export trade via HTTP API
- Daily drawdown guard + analysis-only guard untuk real mode

## Headless setup (clone and run)

From a fresh environment:

```bash
git clone https://github.com/<user>/<repo>.git
cd <repo>
./start.sh
```

`start.sh` akan:
1. Cek `python3`
2. Buat venv `.venv` (sekali)
3. `pip install -r requirements.txt`
4. Jalankan bot

## API

Setelah start:
- `http://localhost:5000/api/state` -> JSON state
- `http://localhost:5000/api/stats` -> ringkasan performa
- `http://localhost:5000/api/export/trades` -> history trade

## Konfigurasi awal
- Salin `.env.example` menjadi `.env`
- Isi `BITGET_API_KEY`, `BITGET_API_SECRET`, `BITGET_PASSPHRASE`
- Demo tidak perlu API key (`DEMO`)
