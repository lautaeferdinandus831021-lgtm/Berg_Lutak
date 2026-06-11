---
name: berglutak-platform
description: Kelola dan operasikan Berg_Lutak trading bot (Bitget USDT futures) via Hermes Agent. Gunakan skill ini untuk start/stop bot, ubah config, baca stats, export trades, dan maintenance repo.
---

# Berg_Lutak Platform

Gunakan skill ini untuk operasi sehari-hari bot trading Berg_Lutak.

## Jalankan Bot

```bash
cd <repo_root>
bash start.sh
```

## Stop Bot

```bash
curl -s -X POST http://127.0.0.1:5000/api/stop
```

## Ubah Konfigurasi

```bash
curl -s -X POST http://127.0.0.1:5000/api/config \
  -H 'Content-Type: application/json' \
  -d '{"sl":1.5,"tp":3.0,"lev":10,"sz":0.5}'
```

## Baca State & Stats

```bash
curl -s http://127.0.0.1:5000/api/state
curl -s http://127.0.0.1:5000/api/stats
```

## Export Trades

```bash
curl -s http://127.0.0.1:5000/api/export/trades -o trades.json
```

## Validasi Dokumen

- Update `.env.example` dan `setup.sh` saat ada parameter baru
- Setiap perubahan strategi harus tercatat di jurnal (daily learning log)
