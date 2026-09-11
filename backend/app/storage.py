"""Salinan dokumen upload ke Cloudflare R2 (S3-compatible).

Masa transisi: file tetap ditulis ke disk lokal (UPLOAD_DIR) karena engine
checker & LibreOffice butuh path lokal. Setelah submission tercatat di DB,
salinannya dikirim ke R2 di thread background — gagal upload hanya dicatat
di log, tidak menggagalkan pengecekan.

Aktif hanya bila R2_BUCKET, R2_ENDPOINT_URL, R2_ACCESS_KEY_ID dan
R2_SECRET_ACCESS_KEY di-set (lihat README). Tanpa itu modul ini no-op.
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
from urllib.parse import quote

R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL", "").strip()
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
R2_BUCKET = os.getenv("R2_BUCKET", "").strip()
R2_PREFIX = os.getenv("R2_PREFIX", "uploads/").strip()

DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

_client = None
_client_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="r2-upload")


def r2_enabled() -> bool:
    return all((R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET))


def get_client():
    """boto3 S3 client ke R2 (lazy, thread-safe, dipakai bersama)."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                import boto3
                from botocore.config import Config

                _client = boto3.client(
                    "s3",
                    endpoint_url=R2_ENDPOINT_URL,
                    aws_access_key_id=R2_ACCESS_KEY_ID,
                    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
                    region_name="auto",
                    config=Config(
                        # Checksum default boto3 >= 1.36 tidak perlu untuk R2.
                        request_checksum_calculation="when_required",
                        response_checksum_validation="when_required",
                        retries={"max_attempts": 5, "mode": "standard"},
                        connect_timeout=10,
                        read_timeout=60,
                    ),
                )
    return _client


def object_key(submission_id: str) -> str:
    return f"{R2_PREFIX}{submission_id}.docx"


def upload_docx(file_path: Path, submission_id: str, **metadata: Optional[str]) -> str:
    """Upload satu .docx ke R2 (blocking). Mengembalikan object key."""
    key = object_key(submission_id)
    # Metadata S3 harus ASCII — nama file asli bisa mengandung karakter non-ASCII.
    meta = {"submission-id": submission_id}
    for name, value in metadata.items():
        if value is not None:
            meta[name.replace("_", "-")] = quote(str(value), safe="")
    get_client().upload_file(
        str(file_path),
        R2_BUCKET,
        key,
        ExtraArgs={"ContentType": DOCX_CONTENT_TYPE, "Metadata": meta},
    )
    return key


def upload_docx_async(file_path: Path, submission_id: str, **metadata) -> None:
    """Jadwalkan upload ke R2 di background. No-op bila R2 belum dikonfigurasi."""
    if not r2_enabled():
        return

    def _job():
        try:
            key = upload_docx(file_path, submission_id, **metadata)
            print(f"[r2] uploaded {submission_id} -> r2://{R2_BUCKET}/{key}")
        except Exception as e:
            print(f"[r2] GAGAL upload {submission_id}: {e!r}")

    _executor.submit(_job)
