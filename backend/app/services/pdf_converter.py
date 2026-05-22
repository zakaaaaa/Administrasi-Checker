"""
PdfConverter — konversi DOCX → PDF via LibreOffice headless.

Dipakai oleh:
- PhysicalSheetCounter (modul 3) — untuk hitung lembar fisik
- (potensial) PageNumberingChecker — untuk verifikasi posisi nomor halaman per lembar

Kenapa pakai LibreOffice (bukan docx2pdf, mammoth, dst)?
- Akurasi pagination paling baik untuk dokumen PKM (banyak tabel, gambar)
- Cross-platform (Linux server production, macOS dev)
- Open source, tidak butuh MS Word

System requirement: LibreOffice harus terinstal.
- Linux: apt install libreoffice — pastikan `soffice` di PATH
- macOS: brew install --cask libreoffice
- Windows: installer dari libreoffice.org — binary biasanya di
  `C:\\Program Files\\LibreOffice\\program\\soffice.exe` (otomatis dicoba).
  Atau set env `SOFFICE_PATH` / `LIBREOFFICE_PROGRAM` ke path lengkap .exe.

Cara install LibreOffice di macOS (untuk dev local):
    brew install --cask libreoffice

Verifikasi:
    soffice --version    # harus return versi 7.x atau 24.x
"""

from __future__ import annotations

import os
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

    # Binary candidate yang dicoba setelah env SOFFICE_PATH / LIBREOFFICE_PROGRAM
    SOFFICE_CANDIDATES = [
        "soffice",
        "libreoffice",
        # macOS default install path
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]

    # Windows: installer tidak selalu menambahkan ke PATH
    _WINDOW_SOFFICE_PATHS = [
        r"D:\libre\program\soffice.com",
        r"D:\libre\program\soffice.exe",
        r"C:\Program Files\LibreOffice\program\soffice.com",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.com",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
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
        """Cari binary LibreOffice: env → PATH → lokasi umum macOS/Windows."""
        for key in ("SOFFICE_PATH", "LIBREOFFICE_PROGRAM"):
            raw = (os.environ.get(key) or "").strip().strip('"')
            if not raw:
                continue
            p = Path(raw)
            if p.is_file():
                return str(p)
            resolved = shutil.which(raw)
            if resolved:
                return resolved

        for cand in cls.SOFFICE_CANDIDATES:
            path = shutil.which(cand) or (cand if Path(cand).exists() else None)
            if path:
                return path

        for winpath in cls._WINDOW_SOFFICE_PATHS:
            wp = Path(winpath)
            if wp.is_file():
                return str(wp)

        raise PdfConversionError(
            "LibreOffice tidak ditemukan. Install lalu:\n"
            "  - Windows: set env SOFFICE_PATH ke soffice.exe, atau tambahkan "
            r"'C:\Program Files\LibreOffice\program' ke PATH, atau\n"
            "  - macOS: brew install --cask libreoffice\n"
            "  - Linux: sudo apt install libreoffice\n"
            "Verifikasi: jalankan `soffice --version` di terminal."
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

        try:
            with tempfile.TemporaryDirectory(prefix="lo-profile-") as profile_dir:
                # LibreOffice headless command
                # --headless: tanpa GUI
                # --convert-to pdf: target format
                # --outdir: folder output (LibreOffice akan generate file dengan nama asli + .pdf)
                # -env:UserInstallation: profile sementara agar tidak bentrok dengan instance GUI.
                cmd = [
                    self.soffice_path,
                    f"-env:UserInstallation={Path(profile_dir).as_uri()}",
                    "--headless",
                    "--nologo",
                    "--nodefault",
                    "--nofirststartwizard",
                    "--norestore",
                    "--convert-to", "pdf",
                    "--outdir", str(output_dir),
                    str(docx_path),
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
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
