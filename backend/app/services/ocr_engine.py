"""
OCR engine — Google Cloud Vision (single backend).

Semua OCR di proyek ini mengalir lewat `_run_ocr` di biodata_date_checker.py
yang delegasi ke `get_ocr_engine().run(images)` di file ini.

Kredensial:
    export GOOGLE_APPLICATION_CREDENTIALS=/path/ke/service-account.json
    (project punya billing aktif & Cloud Vision API enabled)

Catatan: easyocr & pytesseract sudah tidak dipakai lagi.
"""

from __future__ import annotations

import io
import logging
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)


class GoogleVisionEngine:
    """
    Google Cloud Vision document_text_detection.

    - Vision auto-deteksi orientasi → tak perlu coba 4 rotasi manual.
    - Paralel via ThreadPoolExecutor (Vision I/O-bound).
    - Fallback aman: kalau satu gambar gagal/error, return "" (jangan crash).
    """

    def __init__(self):
        from google.cloud import vision
        self._client = vision.ImageAnnotatorClient()
        self._vision = vision

    def run(self, images: list) -> list[str]:
        if not images:
            return []
        with ThreadPoolExecutor(max_workers=8) as ex:
            return list(ex.map(self._one, images))

    def _one(self, pil_img) -> str:
        try:
            buf = io.BytesIO()
            pil_img.convert("RGB").save(buf, format="PNG")
            image = self._vision.Image(content=buf.getvalue())
            ctx = self._vision.ImageContext(language_hints=["id", "en"])
            resp = self._client.document_text_detection(image=image, image_context=ctx)
            if resp.error.message:
                log.warning(f"[ocr/vision] api error: {resp.error.message}")
                return ""
            return resp.full_text_annotation.text or ""
        except Exception as e:
            log.warning(f"[ocr/vision] per-image exception: {e}")
            return ""


_engine: GoogleVisionEngine | None = None


def get_ocr_engine() -> GoogleVisionEngine:
    global _engine
    if _engine is None:
        _engine = GoogleVisionEngine()
        log.info("[ocr] engine=google_vision")
    return _engine


def preload_ocr_engine() -> None:
    """Inisialisasi client di startup biar request pertama tidak nunggu init."""
    try:
        get_ocr_engine()
    except Exception as e:
        log.warning(f"[ocr] preload failed: {e}")
