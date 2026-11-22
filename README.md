# Uji Paham Belajar: Core Service

Microservice backend untuk aplikasi **Uji Paham Belajar** (tema _Education & Learning Tools_, Tugas Besar TST × PWAM).
AI diposisikan sebagai **pendamping belajar, bukan penyedia jawaban instan**: penjelasan konsep tampil terbuka,
sedangkan hasil akhir (kode utuh / ringkasan final) **ditahan di backend (LOCKED)** sampai pengguna menulis ulang
intisari pemahamannya dan lolos _logic checkpoint_.

> Ganti `SakitKepala` dengan nama kelompok yang terdaftar di API Registry, dan `.stei.fun` dengan `.stei.site` untuk kelas K02.

- **Base URL**: `https://SakitKepala.stei.fun/api`
- **Dokumentasi interaktif (Swagger)**: `https://SakitKepala.stei.fun/api/docs`
- **Kontrak OpenAPI**: `https://SakitKepala.stei.fun/api/openapi.json` (salinan: [`docs/openapi.json`](docs/openapi.json))
- **Stack**: Python 3.12, FastAPI, SQLite (WAL), Nginx (gateway), Cloudflare Tunnel, Docker Compose
- **Aplikasi mobile (PWAM)**: folder [`app/`](app/README.md), React Native (Expo)

---

## 1. Arsitektur

```
Aplikasi mobile / kelompok mitra
        │ HTTPS
        ▼
Cloudflare  SakitKepala.stei.fun
        │ Cloudflare Tunnel (koneksi keluar dari STB, tanpa buka port)
        ▼
┌──────────────────── STB (Docker) ────────────────────┐
│ tunnel ─► gateway (Nginx, rate limit) ─► core-service │
│                                           (FastAPI)   │
│                                              │        │
│                                           SQLite      │
│                                         (volume)      │
└───────────────────────────────────────────────────────┘
        core-service ──► Layanan AI eksternal (conformist)
        core-service ──► API mitra (ACL, opsional)
```

Setiap container dibatasi memori dan CPU (`core-service` 256 MB / 0.5 CPU, `gateway` 64 MB, `tunnel` 128 MB).
Saat uji lokal, `core-service` memakai sekitar 60 MB RAM.

## 2. Pemetaan Makalah DDD ke Kode

| Bounded context (makalah)             | Jenis      | Modul                            | Isi                                                                                                     |
| ------------------------------------- | ---------- | -------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Validasi Pemahaman                    | **Core**   | `validation.py`                  | Gatekeeper LOCKED/UNLOCKED, logic checkpoint maks. 3 percobaan, proof-of-learning, kurasi Q&A per topic |
| Orkestrasi Penjelasan & Kurasi Q&A AI | **Core**   | `ai_client.py` + `validation.py` | Penjelasan via API AI, penyimpanan pasangan Q&A konseptual                                              |
| Kuota & Langganan                     | Supporting | `quota.py`                       | Free 5 sesi/hari (WIB), Pro tanpa batas + ekspor                                                        |
| Agregasi Konteks & Integrasi Topik    | Supporting | `acl.py`, `public_api.py`        | ACL ke mitra; endpoint publik Q&A                                                                       |
| Autentikasi & Akses API               | Generic    | `security.py`, `auth_routes.py`  | JWT pengguna, `X-API-Key` mitra                                                                         |

| Relasi (Tabel 1 makalah)                  | Pola                     | Di kode                                                                       |
| ----------------------------------------- | ------------------------ | ----------------------------------------------------------------------------- |
| Layanan AI Eksternal → Validasi Pemahaman | Conformist               | `ai_client.py` mengikuti format penyedia; semua kegagalan dibungkus `AiError` |
| Kuota & Langganan → Validasi Pemahaman    | Customer–Supplier        | `validation.py` hanya memanggil `quota.status / try_consume / can_export`     |
| Autentikasi → Kuota, Validasi             | OHS / Published Language | `security.current_user` (JWT) dipakai semua rute pengguna                     |
| Siaran Belajar, Materi Belajar → kita     | Anti-Corruption Layer    | `acl.py`: penerjemah JSON mitra ke struktur internal                          |
| Kita → Materi Belajar, Siaran Belajar     | OHS / Published Language | `public_api.py`: kontrak JSON berversi `/api/public/v1`                       |

Mitigasi risiko pada makalah: _timeout + cache_ (`acl.py`), _pembatasan laju_ (Nginx per IP, `public_api.RateLimiter` per API key),
_versi kontrak_ (`/v1`, field `contract_version`).

### Aturan domain yang ditegakkan

1. Aplikasi mobile **tidak pernah** menerima `final_result` sebelum status `UNLOCKED` (diuji di `tests/test_gatekeeper.py`).
2. Checkpoint maksimal `MAX_ATTEMPTS` (3). Habis → tetap `LOCKED` permanen (`locked_final: true`).
3. Tulisan yang hampir identik dengan penjelasan (≥ 60% potongan 5-kata sama) ditolak sebagai salinan mentah.
4. Lolos → status `UNLOCKED`, `copy_enabled: true`, dan tercatat di riwayat **proof-of-learning**.
5. Paket Free dibatasi `FREE_DAILY_QUOTA` (5) sesi per hari (zona WIB). Pro tanpa batas dan dapat **ekspor** (hasil akhir + catatan pemahaman).
6. Bila AI gagal, **kuota/percobaan pengguna tidak terpotong**.
7. Pengguna hanya bisa mengakses sesi miliknya sendiri.

## 3. Autentikasi

| Pemanggil                         | Mekanisme                                                                  |
| --------------------------------- | -------------------------------------------------------------------------- |
| Pengguna aplikasi                 | `Authorization: Bearer <JWT>` dari `POST /api/auth/login` (berlaku 1 jam)  |
| Kelompok mitra (server ke server) | Header `X-API-Key: <key>`, satu key per kelompok, batas 60 panggilan/menit |
| Publik                            | Hanya `GET /api/health`                                                    |

## 4. Daftar Endpoint

| Method | Path                              | Auth    | Keterangan                                                        |
| ------ | --------------------------------- | ------- | ----------------------------------------------------------------- |
| GET    | `/api/health`                     | –       | Cek hidup                                                         |
| POST   | `/api/auth/register`              | –       | Daftar (email + password ≥ 8 karakter)                            |
| POST   | `/api/auth/login`                 | –       | Mengembalikan JWT                                                 |
| GET    | `/api/auth/me`                    | JWT     | Profil dan paket                                                  |
| GET    | `/api/subscription`               | JWT     | Paket, kuota terpakai, sisa                                       |
| POST   | `/api/subscription/upgrade`       | JWT     | **Simulasi** upgrade ke Pro (`SUBSCRIPTION_SIMULATION=true`)      |
| POST   | `/api/subscription/downgrade`     | JWT     | Simulasi kembali ke Free                                          |
| POST   | `/api/sessions`                   | JWT     | Mulai sesi `{topic, question}` → penjelasan terbuka, hasil LOCKED |
| GET    | `/api/sessions`                   | JWT     | Daftar sesi milik sendiri                                         |
| GET    | `/api/sessions/{id}`              | JWT     | Detail sesi; `final_result` hanya bila UNLOCKED                   |
| POST   | `/api/sessions/{id}/checkpoint`   | JWT     | Kirim intisari `{summary}` (30-2000 karakter)                     |
| GET    | `/api/sessions/{id}/export`       | JWT     | Ekspor (UNLOCKED + Pro)                                           |
| GET    | `/api/sessions/{id}/references`   | JWT     | Sesi siaran + materi mitra untuk topic sesi (ACL)                 |
| GET    | `/api/proof-of-learning`          | JWT     | Riwayat bukti belajar                                             |
| GET    | `/api/public/v1/qa?topic=`        | API key | Pasangan Q&A per topic (untuk FAQ Materi Belajar)                 |
| GET    | `/api/public/v1/questions?topic=` | API key | Daftar pertanyaan (pemantik diskusi Siaran Belajar)               |
| GET    | `/api/public/v1/topics`           | API key | Topic yang tersedia + jumlah Q&A                                  |

Kode status penting: `401` kredensial salah, `403 LOCKED / PRO_REQUIRED` untuk ekspor, `404` sesi bukan milikmu,
`409 ATTEMPTS_EXHAUSTED / ALREADY_UNLOCKED`, `422` input tidak valid, `429 QUOTA_EXCEEDED` atau terkena rate limit, `503` AI tidak tersedia.

### Contoh request

```bash
BASE=https://SakitKepala.stei.fun/api

# Daftar + login
curl -X POST $BASE/auth/register -H "Content-Type: application/json" \
  -d '{"email":"uji@example.com","password":"Rahasia123"}'
TOKEN=$(curl -s -X POST $BASE/auth/login -H "Content-Type: application/json" \
  -d '{"email":"uji@example.com","password":"Rahasia123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Mulai sesi: penjelasan terbuka, final_result = null
curl -X POST $BASE/sessions -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"topic":"rekursi","question":"Buatkan fungsi faktorial rekursif"}'

# Logic checkpoint (ganti {id})
curl -X POST $BASE/sessions/{id}/checkpoint -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"summary":"Rekursi memecah masalah menjadi versi lebih kecil sampai kasus dasar, lalu hasilnya digabung kembali."}'

# Untuk kelompok mitra
curl "$BASE/public/v1/qa?topic=rekursi" -H "X-API-Key: <API_KEY_KELOMPOKMU>"
```

Respons `GET /api/public/v1/qa?topic=rekursi`:

```json
{
  "contract_version": "1.0",
  "topic": "rekursi",
  "count": 2,
  "items": [
    { "question": "Apa itu rekursi?", "answer": "..." },
    { "question": "Mengapa rekursi penting dipahami?", "answer": "..." }
  ]
}
```

## 5. Cara Mendapat Akses (untuk kelompok mitra)

1. Buka issue di repositori ini atau hubungi kontak di API Registry.
2. Kami memberi **satu API key** atas nama kelompokmu dan **satu akun uji** (email + password).
3. Panggil endpoint `/api/public/v1/*` dengan header `X-API-Key`. Batas **60 panggilan/menit** per key; kena batas → `429` + `Retry-After`.
4. Topic dicocokkan secara **persis** (tidak peka huruf besar/kecil). Pakai `/topics` untuk melihat topic yang tersedia.
5. Topic tanpa data mengembalikan `200` dengan `count: 0`. Tangani sebagai kondisi biasa, bukan error.

## 6. Konfigurasi (`.env`)

Salin `.env.example` ke `.env`, isi, lalu `chmod 600 .env`. **Jangan di-commit.**

| Variabel                               | Keterangan                                                             |
| -------------------------------------- | ---------------------------------------------------------------------- |
| `JWT_SECRET`                           | Wajib, ≥ 32 karakter (`openssl rand -hex 32`)                          |
| `TUNNEL_TOKEN`                         | Wajib, dari dashboard Cloudflare                                       |
| `API_KEYS`                             | `nama:key,nama2:key2`, satu per kelompok mitra                         |
| `FREE_DAILY_QUOTA` / `MAX_ATTEMPTS`    | 5 / 3                                                                  |
| `SUBSCRIPTION_SIMULATION`              | `true` = tombol upgrade Pro berupa simulasi                            |
| `AI_PROVIDER`                          | `mock` (dev/test) atau `http` (API kompatibel OpenAI chat completions) |
| `AI_API_URL`, `AI_API_KEY`, `AI_MODEL` | Wajib bila `AI_PROVIDER=http`                                          |
| `PARTNERS_ENABLED` + `PARTNER_*`       | Integrasi ACL ke Siaran Belajar / Materi Belajar                       |

## 7. Menjalankan

### Uji lokal tanpa Docker

```bash
cd core-service
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q                                   # 32 test
JWT_SECRET=$(openssl rand -hex 32) DB_PATH=./dev.db uvicorn app.main:app --port 8000
# buka http://localhost:8000/api/docs
```

### Deploy di STB

```bash
git clone https://github.com/<user>/SakitKepala-backend.git && cd SakitKepala-backend
cp .env.example .env && nano .env && chmod 600 .env
docker compose up -d --build
docker compose ps                           # core-service harus (healthy)
docker compose logs tunnel | tail -5        # cari "Registered tunnel connection"
docker stats --no-stream; free -h
```

Tes lokal tanpa tunnel: `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build core-service gateway`,
lalu buka `http://localhost:8080/api/docs`.

### Cloudflare Tunnel

1. Pesan nama kelompok di **API Registry**.
2. Dashboard Cloudflare akun kelas → **Networks → Tunnels → Create a tunnel → Cloudflared**, nama `k01-SakitKepala` (kelas-namakelompok).
3. Salin hanya string setelah `--token` ke `TUNNEL_TOKEN` di `.env`. Jangan jalankan perintah `docker run` yang ditampilkan.
4. **Public Hostname**: subdomain `SakitKepala`, domain `stei.fun` (K01) / `stei.site` (K02), Type **HTTP**, URL **`gateway:80`**.
5. `docker compose up -d`, tunnel harus berstatus _Healthy_. Lalu logout dari Cloudflare.

### Smoke test dari luar STB

```bash
python scripts/smoke_test.py https://SakitKepala.stei.fun --api-key <KEY_MITRA>
```

### Backup

```bash
docker compose cp core-service:/data/app.db ./backup-$(date +%F).db
```

## 8. Pengujian

`pytest -q` di `core-service/` menjalankan 32 test: auth, gatekeeper (LOCKED/UNLOCKED, 3 percobaan, anti-salinan),
kuota Free/Pro dan reset harian, ekspor, endpoint publik (API key, rate limit, tidak membocorkan data internal),
serta ACL (variasi skema mitra, mitra mati, cache basi).

## 9. Asumsi dan Keterbatasan

- **Penilaian checkpoint**: dengan `AI_PROVIDER=http`, penilai AI menilai pemahaman setelah lolos pemeriksaan anti-salinan. Bila penilai AI mati, percobaan tidak dihitung (`503`).
  Mode `mock` hanya mencocokkan kata kunci dan tidak boleh dipakai saat penilaian.
- **Ekspor**: salin hasil tersedia bagi semua pengguna setelah UNLOCKED; **ekspor** (hasil akhir + catatan pemahaman) khusus Pro, mengikuti bagian model bisnis makalah.
- **Pembayaran** tidak diimplementasikan; upgrade Pro adalah simulasi.
- **ACL mitra** dimatikan secara default. Path endpoint mitra (`PARTNER_*_PATH`) harus disesuaikan dengan kontrak mereka di API Registry.
  Aturan STB melarang layanan integrasi (Tugas 3) berjalan di STB, sehingga `acl.py` dapat dipindahkan ke layanan integrasi di server lain.
- Data uji saja; jangan simpan data pribadi asli pengguna di STB.
