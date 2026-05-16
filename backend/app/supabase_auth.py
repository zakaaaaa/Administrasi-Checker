"""
Supabase Auth helper — verifikasi JWT user dengan endpoint REST Supabase.

Cara kerja:
- Frontend login via supabase-js → dapat `access_token` (JWT).
- Frontend kirim ke backend di header `Authorization: Bearer <jwt>`.
- Backend forward ke `{SUPABASE_URL}/auth/v1/user` dengan header itu +
  `apikey: <SUPABASE_ANON_KEY>`. Supabase return 200 + user data kalau JWT
  valid, atau 401 kalau invalid/expired.

Alternatif yang lebih cepat (tanpa network call) adalah verifikasi JWT
lokal pakai SUPABASE_JWT_SECRET + PyJWT, tapi itu butuh menyimpan JWT
secret yang sangat sensitif. Untuk iter 1 kita pakai pendekatan REST.
"""
from __future__ import annotations

import os
from typing import Optional

import requests
from fastapi import HTTPException, Header

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(401, "Authorization header tidak ada")
    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Authorization header tidak valid (format: Bearer <token>)")
    token = parts[1].strip()
    if not token:
        raise HTTPException(401, "Token kosong")
    return token


def verify_supabase_token(access_token: str) -> dict:
    """
    Verifikasi JWT ke Supabase. Return user dict (id, email, ...).
    Raise HTTPException kalau invalid.
    """
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(
            500,
            "Konfigurasi Supabase belum lengkap (SUPABASE_URL / SUPABASE_ANON_KEY).",
        )
    url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "apikey": SUPABASE_ANON_KEY,
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as e:
        raise HTTPException(503, f"Tidak bisa verifikasi token ke Supabase: {e}")

    if resp.status_code == 401:
        raise HTTPException(401, "Token tidak valid atau sudah kadaluarsa")
    if resp.status_code != 200:
        raise HTTPException(
            resp.status_code,
            f"Verifikasi token gagal (status {resp.status_code})",
        )

    user = resp.json()
    if not isinstance(user, dict) or "id" not in user:
        raise HTTPException(401, "Response Supabase tidak valid")
    return user


def require_supabase_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """FastAPI dependency: extract Bearer token + verifikasi → return user."""
    token = _extract_bearer_token(authorization)
    return verify_supabase_token(token)
