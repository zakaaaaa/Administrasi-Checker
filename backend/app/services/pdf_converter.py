"""
PdfConverter — konversi DOCX → PDF via LibreOffice headless.

Dipakai oleh:
- PhysicalSheetCounter (modul 3) — untuk hitung lembar fisik
- (potensial) PageNumberingChecker — untuk verifikasi posisi nomor halaman per lembar

Kenapa pakai LibreOffice (bukan docx2pdf, mammoth, dst)?
- Akurasi pagination paling baik untuk dokumen PKM (banyak tabel, gambar)
- Cross-platform (Linux server production, macOS dev)
- Open source, tidak butuh MS Word

System requirement: LibreOffice harus terinstal di system PATH.
- Linux: apt install libreoffice / pacman -S libreoffice
- macOS: brew install --cask libreoffice (atau download .dmg)
- Windows: download installer dari libreoffice.org

Cara install LibreOffice di macOS (untuk dev local):
    brew install --cask libreoffice

Verifikasi:
    soffice --version    # harus return versi 7.x atau 24.x
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


class PdfConversionError(Exception):
    """Konversi gagal — biasanya karena LibreOffice tidak terinstal atau dokumen rusak."""
    pass


class PdfConverter:
    """
    Konverter DOCX → PDF.

    Usage:
        converter = PdfConverter()
        pdf_path = converter.convert('input.docx', output_dir='/tmp')
        # pdf_path = '/tmp/input.pdf'

    Cache:
        Default tidak ada cache di-instance level — caller yang manage.
        Untuk kebutuhan worker production, hasil PDF sebaiknya disimpan di
        Cloud Storage (lihat blueprint §9.3) bukan filesystem lokal.
    """

    # Binary candidate yang dicoba (pertama yang ketemu menang)
    SOFFICE_CANDIDATES = [
        "soffice",
        "libreoffice",
        # macOS default install path
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]

    def __init__(self, soffice_path: Optional[str] = None, timeout_seconds: int = 120):
        """
        Args:
            soffice_path: path ke binary LibreOffice. Kalau None, otomatis cari.
            timeout_seconds: batas waktu konversi (default 120s untuk dokumen besar).
        """
        self.soffice_path = soffice_path or self._find_soffice()
        self.timeout_seconds = timeout_seconds

    @classmethod
    def _find_soffice(cls) -> str:
        """Cari binary LibreOffice di PATH atau lokasi umum macOS."""
        for cand in cls.SOFFICE_CANDIDATES:
            # shutil.which return path lengkap kalau ditemukan
            path = shutil.which(cand) or (cand if Path(cand).exists() else None)
            if path:
                return path
        raise PdfConversionError(
            "LibreOffice tidak ditemukan. Install dulu:\n"
            "  - macOS: brew install --cask libreoffice\n"
            "  - Linux: sudo apt install libreoffice\n"
            "Lalu pastikan 'soffice' atau 'libreoffice' tersedia di PATH."
        )

    def convert(
        self, docx_path: str | Path, output_dir: Optional[str | Path] = None
    ) -> Path:
        """
        Konversi DOCX → PDF.

        Args:
            docx_path: path ke file .docx
            output_dir: folder output. Kalau None, pakai folder yang sama dengan input.

        Returns:
            Path ke PDF hasil konversi.

        Raises:
            FileNotFoundError: file input tidak ada
            PdfConversionError: konversi gagal (LibreOffice error / timeout)
        """
        docx_path = Path(docx_path)
        if not docx_path.exists():
            raise FileNotFoundError(f"File tidak ditemukan: {docx_path}")

        if output_dir is None:
            output_dir = docx_path.parent
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # LibreOffice headless command
        # --headless: tanpa GUI
        # --convert-to pdf: target format
        # --outdir: folder output (LibreOffice akan generate file dengan nama asli + .pdf)
        cmd = [
            self.soffice_path,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(output_dir),
            str(docx_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                # LibreOffice butuh user profile dir yang writable; pakai temp dir
                # untuk avoid konflik kalau ada instance LibreOffice lain
                env=self._build_env(),
            )
        except subprocess.TimeoutExpired as e:
            raise PdfConversionError(
                f"Konversi timeout setelah {self.timeout_seconds}s: {docx_path.name}"
            ) from e
        except FileNotFoundError as e:
            raise PdfConversionError(
                f"Binary LibreOffice tidak bisa dieksekusi: {self.soffice_path}"
            ) from e

        if result.returncode != 0:
            raise PdfConversionError(
                f"LibreOffice exit code {result.returncode}.\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

        # Output file: <output_dir>/<input_stem>.pdf
        pdf_path = output_dir / (docx_path.stem + ".pdf")
        if not pdf_path.exists():
            raise PdfConversionError(
                f"Konversi selesai tapi file PDF tidak ditemukan: {pdf_path}\n"
                f"stdout: {result.stdout}"
            )

        return pdf_path

    @staticmethod
    def _build_env() -> dict:
        """
        Build env vars untuk subprocess LibreOffice.

        Set HOME ke temp dir supaya LibreOffice bikin user profile sendiri,
        avoid conflict dengan instance LibreOffice yang sedang dipakai user
        di GUI (sering jadi masalah di macOS dev).
        """
        import os
        env = os.environ.copy()
        # Buat temp profile dir per call (auto cleanup oleh OS)
        env["HOME"] = tempfile.gettempdir()
        return env