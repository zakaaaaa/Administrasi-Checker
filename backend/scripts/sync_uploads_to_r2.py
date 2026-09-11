"""Salin semua .docx di storage/uploads ke R2 (idempotent — yang sudah ada di-skip).

File lokal TIDAK dihapus. Metadata (nama file asli, skema, dst.) diambil
dari tabel submissions bila ada.

Jalankan dari folder backend dengan env produksi:
    set -a; . /etc/administrasi-checker/backend.env; set +a
    .venv/bin/python scripts/sync_uploads_to_r2.py [--dry-run]
"""
import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from botocore.exceptions import ClientError  # noqa: E402

from app import storage  # noqa: E402

UPLOAD_DIR = BACKEND_DIR / "storage" / "uploads"


def _load_metadata() -> dict:
    try:
        from app.db import get_cursor

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT CAST(id AS TEXT) AS id, original_filename, competition,
                       report_type, schema_code,
                       CASE WHEN token_id IS NULL THEN 'reviewer' ELSE 'token' END AS source
                FROM submissions
                """
            )
            return {r["id"]: r for r in cur.fetchall()}
    except Exception as e:
        print(f"[warn] metadata DB tidak terbaca ({e}); upload tanpa metadata")
        return {}


def _exists(key: str) -> bool:
    try:
        storage.get_client().head_object(Bucket=storage.R2_BUCKET, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not storage.r2_enabled():
        print("R2 belum dikonfigurasi (R2_BUCKET/R2_ENDPOINT_URL/R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY).")
        return 1

    files = sorted(UPLOAD_DIR.glob("*.docx"))
    meta_by_id = _load_metadata()
    uploaded = skipped = failed = 0
    for path in files:
        sid = path.stem
        key = storage.object_key(sid)
        try:
            if _exists(key):
                skipped += 1
                continue
            if args.dry_run:
                print(f"[dry-run] {path.name} -> {key}")
                uploaded += 1
                continue
            row = meta_by_id.get(sid, {})
            storage.upload_docx(
                path, sid,
                original_filename=row.get("original_filename"),
                competition=row.get("competition"),
                report_type=row.get("report_type"),
                schema_code=row.get("schema_code"),
                source=row.get("source"),
            )
            uploaded += 1
            print(f"[ok] {path.name} ({path.stat().st_size // 1024} KB) -> {key}")
        except Exception as e:
            failed += 1
            print(f"[GAGAL] {path.name}: {e!r}")

    print(f"\nTotal {len(files)} file: {uploaded} diupload, {skipped} sudah ada, {failed} gagal")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
