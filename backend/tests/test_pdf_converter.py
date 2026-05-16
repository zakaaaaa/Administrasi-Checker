"""Tes penemuan binary LibreOffice untuk PdfConverter."""

from __future__ import annotations

import pytest

from app.services.core.pdf_converter import PdfConverter, PdfConversionError


def test_soffice_resolved_from_soffice_path_env(monkeypatch, tmp_path):
    exe = tmp_path / "soffice"
    exe.write_bytes(b"")
    monkeypatch.setenv("SOFFICE_PATH", str(exe))
    monkeypatch.delenv("LIBREOFFICE_PROGRAM", raising=False)
    c = PdfConverter()
    assert c.soffice_path == str(exe)


def test_soffice_resolved_from_libreoffice_program_env(monkeypatch, tmp_path):
    exe = tmp_path / "mysoffice"
    exe.write_bytes(b"")
    monkeypatch.delenv("SOFFICE_PATH", raising=False)
    monkeypatch.setenv("LIBREOFFICE_PROGRAM", str(exe))
    c = PdfConverter()
    assert c.soffice_path == str(exe)


def test_raises_when_no_libreoffice(monkeypatch):
    monkeypatch.delenv("SOFFICE_PATH", raising=False)
    monkeypatch.delenv("LIBREOFFICE_PROGRAM", raising=False)
    monkeypatch.setattr("shutil.which", lambda _x: None)
    monkeypatch.setattr(PdfConverter, "SOFFICE_CANDIDATES", [])
    monkeypatch.setattr(PdfConverter, "_WINDOW_SOFFICE_PATHS", [])
    with pytest.raises(PdfConversionError, match="LibreOffice tidak ditemukan"):
        PdfConverter()
