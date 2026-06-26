# PRD — SynCoop / warp (Koperasi Digital Nelayan)

## Problem Statement
Digital cooperative management ecosystem for Indonesian grassroots fishermen. Solves: (1) targeted subsidized BBM distribution + fish pricing/auction, (2) financial transparency, fair debt tracking, anti-speculation membership.

## Stack
React 19 + FastAPI + MongoDB. Auth: Emergent Google OAuth + 6-digit PIN fallback + demo role quick-access. Design: Swiss-minimalist (white/black/Inter, lavender accent), big tap targets.

## Roles
- NELAYAN (Calon/Anggota), PETUGAS_LAPANG (field officer), ADMIN (koperasi), PETUGAS_DINAS (govt fisheries).

## Implemented (2026-06-26)
- Auth: Emergent Google OAuth (/auth/session), PIN set/login, demo quick-access for 4 roles, session cookie + Bearer.
- Anti-speculation membership: 365-day maturation countdown, KYC gate locked until matured, admin KYC approval.
- BBM distribution: vessels (Pas Besar/Kecil, unique rekom no), Dinas creates Surat Rekomendasi, 400L/month HARD-BLOCK quota guardrail w/ alert chart.
- Split ledger: petugas lapang records BBM trx (Lunas/DP), DP -> kurang bayar, admin validates + uploads receipt photo, master piutang sheet, reminder notifications, nelayan fills debt reason.
- Fish calculator: gross = weight*price/kg, coop cut = gross*sharing%, net; admin manages fish prices & sharing %.
- Lelang Ikan (fish auction/sale): petugas/admin record fish purchase from nelayan; payment CASH or POTONG_UTANG (tebasan/ijon, deducts oldest debt first, remainder cash). Nelayan sees own sales.
- Fish-sale VALIDATION: admin validates lelang entries by uploading receipt/nota photo (Validasi Transaksi page has BBM + Lelang tabs). Petugas focuses on recording only.
- Role-based dashboards & notifications.

## Testing
- iteration_1: 31/31 backend pass. iteration_2: 43/43 backend pass + frontend flows. Fish-sale validation verified via curl + screenshot.

## Demo accounts (test_credentials.md)
nelayan@/lapang@/admin@/dinas@demo.syncoop.id via demo quick-access.

## Backlog / Next
- P1: ~~Real image upload for receipt photos~~ ✅ DONE (Emergent object storage: POST /api/upload, GET /api/files/{path} auth-gated; receipt validation now uses camera/file upload).
- P1: Disable submit buttons while POST in-flight (prevent dup sales).
- P2: Aggregate owner_outstanding query (avoid N+1 in /vessels).
- P2: Lelang validation gating into main ledger; reports/export.
- P2: Real PIN onboarding UI after Google login + WebAuthn biometric.
