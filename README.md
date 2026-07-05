# SynCoop

SynCoop adalah aplikasi koperasi nelayan berbasis web untuk mengelola anggota,
kapal, kuota BBM, transaksi, piutang, simpan-pinjam, inventori, layanan warga,
harga ikan, laporan, dan portal publik.

## Panduan Untuk Dewan Juri

Bagian ini menjelaskan cara menjalankan project dari awal setelah clone dari
GitHub.

### Prasyarat

- Git
- Python 3.10 atau lebih baru
- Node.js 18 atau lebih baru
- Yarn 1.x atau npm
- MongoDB Atlas cluster atau MongoDB lokal

### Clone Repository

```bash
git clone https://github.com/slamsmart/SynCoop.git
cd SynCoop
```

### Setup Backend

```bash
cd backend
python -m venv .venv
```

Aktifkan virtual environment.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependency:

```bash
pip install -r requirements.txt
```

Buat file `backend/.env` dari contoh:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Untuk MongoDB Atlas, isi `backend/.env` seperti ini:

```env
MONGO_URL=mongodb+srv://<username>:<password>@<cluster-host>/syncoop?retryWrites=true&w=majority&appName=<app-name>
DB_NAME=syncoop
APP_ENV=local
EMERGENT_LLM_KEY=
```

Untuk MongoDB lokal, isi:

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=syncoop
APP_ENV=local
EMERGENT_LLM_KEY=
```

Jalankan backend:

```bash
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

Backend akan tersedia di:

```text
http://localhost:8001/api
```

Saat startup, aplikasi akan otomatis membuat data demo jika collection target
masih kosong.

### Setup Frontend

Buka terminal baru dari root project:

```bash
cd frontend
yarn install
```

Jika tidak memakai Yarn:

```bash
npm install
```

Buat atau cek file `frontend/.env`:

```env
REACT_APP_BACKEND_URL=http://localhost:8001
```

Jalankan frontend:

```bash
yarn start
```

Atau dengan npm:

```bash
npm start
```

Frontend akan tersedia di:

```text
http://localhost:3000
```

### Akun Demo

Gunakan tombol login demo di halaman login. Role demo yang tersedia:

- Nelayan
- Petugas Lapang
- Admin
- Petugas Dinas

Backend juga menyediakan endpoint demo login:

```text
POST /api/auth/demo
```

Body:

```json
{ "role": "ADMIN" }
```

Role valid:

```text
NELAYAN
PETUGAS_LAPANG
ADMIN
PETUGAS_DINAS
```

## MongoDB Atlas Setup

The backend reads MongoDB configuration from `backend/.env`.

1. Create a MongoDB Atlas cluster.
2. In Atlas, create a database user and allow your current IP address in
   **Network Access**.
3. Copy the Atlas connection string and put it in `backend/.env`.

Keep `DB_NAME=syncoop` unless you want a separate database.

If local DNS has trouble resolving `mongodb+srv://` records, set your DNS to
Google DNS or Cloudflare DNS:

```text
8.8.8.8
1.1.1.1
```

For development only, Atlas Network Access can temporarily use:

```text
0.0.0.0/0
```

For production, restrict Network Access to the deployed server IP.

## Project Structure

```text
backend/   FastAPI API, MongoDB models, seed data, tests
frontend/  React app and UI pages
memory/    Product notes and requirements
tests/     Supporting test package
```

## Important Security Notes

- Do not commit `backend/.env` or `frontend/.env`.
- Store real MongoDB credentials only in local or deployment environment
  variables.
- `backend/.env.example` is safe to commit because it contains placeholders
  only.
