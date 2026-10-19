# mr cont — Reward App (Demo)

Website reward berbasis Flask + SQLite dengan desain premium modern. Fitur:
- Registrasi dan login dengan hash password.
- Dashboard saldo poin demo.
- Bonus harian 20 poin, sekali per tanggal.
- Daftar tugas demo dan klaim poin, sekali per tugas per hari.
- Kode referral: pengundang mendapat 50 poin demo, pengguna baru 25 poin demo.
- Riwayat poin.
- Admin untuk melihat pengguna dan menambah tugas.
- Perlindungan CSRF pada semua formulir POST.

**Penting:** poin pada proyek ini hanya poin demo, bukan uang nyata, tidak memiliki nilai tunai, dan tidak dapat ditarik. Jangan menampilkan klaim penghasilan nyata tanpa model bisnis dan kepatuhan yang sesuai.

## Jalankan di Android (Termux) atau komputer

1. Instal Python dan pip. Di Termux:
   ```bash
   pkg update && pkg upgrade
   pkg install python
   ```
2. Ekstrak ZIP, masuk ke folder `mr_cont_reward_app`.
3. Instal dependensi:
   ```bash
   pip install -r requirements.txt
   ```
4. Atur rahasia sebelum menjalankan (disarankan):
   ```bash
   export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
   export ADMIN_USERNAME="admin"
   export ADMIN_PASSWORD="GANTI_DENGAN_PASSWORD_ADMIN_KUAT"
   ```
5. Jalankan:
   ```bash
   python app.py
   ```
6. Buka `http://127.0.0.1:5000` di browser perangkat yang sama.

## Login admin
Buka `/admin`, lalu masukkan nilai `ADMIN_USERNAME` dan `ADMIN_PASSWORD` yang telah diatur. Nilai default hanya untuk pengembangan lokal; ubah sebelum dipublikasikan.

## Deploy ke Render
1. Unggah folder proyek ke repository GitHub.
2. Di Render pilih **New + > Blueprint**, lalu pilih repository tersebut (Render membaca `render.yaml`).
3. Isi `ADMIN_PASSWORD` sebagai environment variable rahasia ketika diminta. `SECRET_KEY` dibuat otomatis oleh konfigurasi.
4. Pastikan persistent disk tersedia untuk layanan yang dipilih. SQLite disimpan di `/var/data/mr_cont.db`.
5. Deploy dan buka URL yang diberikan Render.

Catatan: ketersediaan persistent disk dapat bergantung pada jenis paket Render. Jika paket tidak mendukung disk persisten, gunakan PostgreSQL atau layanan database persisten sebelum dipakai sungguhan.

## Struktur
```text
mr_cont_reward_app/
├── app.py
├── requirements.txt
├── Procfile
├── render.yaml
├── README.md
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── tasks.html
│   ├── history.html
│   ├── admin_login.html
│   ├── admin.html
│   └── error.html
└── static/
    └── style.css
```

## Catatan keamanan
- Set `SECRET_KEY` dan password admin yang kuat di environment, bukan di repository.
- Gunakan HTTPS saat online.
- Ini starter project yang layak untuk demo; sebelum produksi, tambahkan rate limiting, verifikasi email, kebijakan privasi, pencadangan database, pemantauan, dan pengujian keamanan.
- Hadiah referral diproses setelah akun baru dibuat; sistem ini belum mencegah pendaftaran multi-akun secara canggih.
