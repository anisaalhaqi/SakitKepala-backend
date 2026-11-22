# Uji Paham Belajar: Aplikasi Mobile

Aplikasi mobile kelompok **SakitKepala** (tema *Education & Learning Tools*, Tugas Besar TST × PWAM).
Pengguna membaca penjelasan dari AI, lalu menulis ulang intisarinya di *logic checkpoint*. Hasil akhir baru
terbuka setelah checkpoint lolos, dan kelulusan dicatat sebagai bukti belajar. Di samping penjelasan, aplikasi
menampilkan sesi siaran dari **Sistem Siaran Belajar** dan materi dari **Sistem Materi Belajar** yang topiknya sama.

| Item | Keterangan |
| --- | --- |
| API (live) | `https://sakitkepala.stei.site/api` · Swagger `/api/docs` |
| Backend | folder repo ini ([README backend](../README.md)) |
| Stack | React Native 0.88, Expo SDK 58, React Navigation 7, Expo SecureStore, Expo Clipboard |
| Akun demo | `demo@sakitkepala.test` / `UjiPaham123!` (paket Free, khusus demo) |

## Menjalankan

Prasyarat: Node.js 20 atau lebih baru, npm, dan Expo Go di HP atau emulator Android.

```bash
cd app
npm ci
cp .env.example .env      # default sudah memakai URL live
npm start                 # pindai QR dengan Expo Go, atau tekan "a" untuk emulator Android
```

| Lingkungan | `EXPO_PUBLIC_API_URL` |
| --- | --- |
| Live (dipakai APK) | `https://sakitkepala.stei.site/api` |
| Lokal, emulator Android | `http://10.0.2.2:8080/api` |
| Lokal, HP fisik | `http://<IP LAN komputer>:8080/api` |

`EXPO_PUBLIC_INTEGRATION_URL` diisi bila layanan integrasi mitra dipisah dari microservice. Bila kosong, aplikasi
memakai URL microservice. Berkas `.env` tidak di-commit. Untuk menjalankan backend secara lokal, lihat README backend.

## Struktur

```
app/
├── App.js                 provider + navigator (Root Stack, Bottom Tabs)
├── src/
│   ├── ApiService.js      semua komunikasi HTTP, termasuk data kelompok mitra
│   ├── AuthContext.js     token (SecureStore), profil, login/logout, sesi berakhir
│   ├── validation.js      aturan form, sama dengan batas backend
│   ├── drafts.js          draft intisari selama aplikasi terbuka
│   ├── ui.js              komponen tampilan bersama
│   └── screens/           Login (Masuk + Daftar), Belajar, DetailSesi, Riwayat, Akun
└── __tests__/             Jest: ApiService dan validasi
```

## Navigasi

```
Root Stack
├── Pemulihan            token sedang diperiksa lewat /auth/me
├── Masuk ↔ Daftar       belum login
└── Setelah login
    ├── Bottom Tabs: Belajar | Riwayat | Akun
    └── Detail Sesi      dibuka dari Belajar atau Riwayat (param sessionId)
```

Logout atau respons 401 pada request bertoken menghapus token dan membuka Masuk. Bila token kedaluwarsa saat
pengguna menulis intisari, draftnya tetap tersimpan selama aplikasi terbuka dan muncul lagi setelah login ulang.

## ApiService.js

| Fungsi | Endpoint | Layar |
| --- | --- | --- |
| `register` | `POST /auth/register` | Daftar |
| `login` | `POST /auth/login` | Masuk |
| `getMe` | `GET /auth/me` | Pemulihan, Akun |
| `createSession` | `POST /sessions` | Belajar |
| `listSessions` | `GET /sessions` | Riwayat |
| `getSession` | `GET /sessions/{id}` | Detail Sesi |
| `submitCheckpoint` | `POST /sessions/{id}/checkpoint` | Detail Sesi |
| `getExport` | `GET /sessions/{id}/export` (paket Pro) | Detail Sesi |
| `getProofOfLearning` | `GET /proof-of-learning` | Riwayat |
| `getSubscription` | `GET /subscription` | Belajar, Akun |
| `getReferences` | `GET /sessions/{id}/references` (layanan integrasi) | Detail Sesi |

`getReferences` tidak pernah melempar error. Bila mitra mati, blok mitra berstatus `unavailable` dan disembunyikan,
sedangkan alur belajar tetap berjalan.

Timeout: 45 detik untuk `POST /sessions` dan checkpoint (backend menunggu API AI hingga 30 detik), 15 detik untuk
request lain.

| Respons | Perilaku aplikasi |
| --- | --- |
| 401 | Hapus token, buka Masuk dengan pesan “Sesi berakhir” |
| 404 | “Sesi tidak ditemukan” dan tombol kembali |
| 409 `ALREADY_UNLOCKED` / `ATTEMPTS_EXHAUSTED` | Muat ulang sesi |
| 422 | Pesan di bawah field terkait |
| 429 `QUOTA_EXCEEDED` | Pesan kuota di layar Belajar, tombol buat sesi nonaktif |
| 403 `PRO_REQUIRED` | Tombol ekspor tampil nonaktif “Khusus Pro” |
| 503 | Pesan layanan AI tidak tersedia dan tombol coba lagi |
| Timeout / jaringan putus | Pesan yang jelas dan tombol coba lagi; aplikasi tidak crash |

## Pengujian

```bash
npm test
```
