"""Unit tests untuk ReferenceValidator (sitasi in-text, DP, typo)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.docx_parser import ParagraphInfo
from app.services.reference_validator import (
    ReferenceValidator,
    _dp_has_dkk,
    _dp_has_et_al,
)
from app.services.schema_rules import get_pkm_kc_proposal_rules


def _fake_parser(paragraphs: list[ParagraphInfo]) -> MagicMock:
    parser = MagicMock()
    parser.paragraphs = paragraphs
    parser.estimate_physical_page = None
    parser.estimate_paragraph_index_in_page = None

    def find_section_boundaries(
        section_names: list[str],
        case_sensitive: bool = False,
        headings_only: bool = False,
    ) -> dict[str, int | None]:
        result: dict[str, int | None] = {name: None for name in section_names}
        for para in paragraphs:
            if headings_only and not para.is_heading:
                continue
            text = para.text.strip()
            cmp_text = text if case_sensitive else text.upper()
            for name in section_names:
                if result[name] is not None:
                    continue
                cmp_name = name if case_sensitive else name.upper()
                if cmp_text.startswith(cmp_name):
                    result[name] = para.index
        return result

    parser.find_section_boundaries = find_section_boundaries
    return parser


def _heading(idx: int, text: str) -> ParagraphInfo:
    return ParagraphInfo(index=idx, text=text, is_heading=True)


def _body(idx: int, text: str) -> ParagraphInfo:
    return ParagraphInfo(index=idx, text=text, is_heading=False)


@pytest.fixture
def schema():
    return get_pkm_kc_proposal_rules()


def test_et_al_word_boundary_not_metal():
    assert _dp_has_et_al("metal oxide catalyst") is False
    assert _dp_has_et_al("Smith et al. (2020) Title.") is True
    assert _dp_has_et_al("Rahmadi et al (2022) paper") is True


def test_dkk_detected():
    assert _dp_has_dkk("Penulis dkk. 2021.") is True
    assert _dp_has_dkk("No abbreviation here 2021.") is False


def test_intext_et_al_allowed(schema):
    """Sitasi in-text dengan 'et al.' DIPERBOLEHKAN — tidak boleh ke-flag."""
    paras = [
        _heading(0, "BAB 1. PENDAHULUAN"),
        _body(1, "Menurut (Revis et al, 2020) hal ini penting."),
        _heading(2, "DAFTAR PUSTAKA"),
        _body(
            3,
            "Revis, A. 2020. Judul buku yang cukup panjang agar tidak warning "
            "pendek. Penerbit: Kota.",
        ),
    ]
    parser = _fake_parser(paras)
    r = ReferenceValidator(parser, schema, current_year=2026).check()
    intext_fail = [
        f for f in r.format_issues if f.entry_index == -1 and "et al" in f.issue.lower()
    ]
    assert intext_fail == []


def test_intext_dkk_allowed(schema):
    """Sitasi in-text dengan 'dkk.' DIPERBOLEHKAN — tidak boleh ke-flag."""
    paras = [
        _heading(0, "BAB 1. X"),
        _body(1, "Lihat (Astuti dkk., 2012)."),
        _heading(2, "DAFTAR PUSTAKA"),
        _body(
            3,
            "Astuti. 2012. Judul artikel yang memadai untuk panjang minimum "
            "validator di sini. Jurnal Contoh, 1(1), 1–10.",
        ),
    ]
    parser = _fake_parser(paras)
    r = ReferenceValidator(parser, schema, current_year=2026).check()
    intext_fail = [
        f for f in r.format_issues if f.entry_index == -1 and "dkk" in f.issue.lower()
    ]
    assert intext_fail == []


def test_balance_typo_hint_same_year(schema):
    paras = [
        _heading(0, "BAB 1. X"),
        _body(1, "Menurut (Smyth, 2020) benar."),
        _heading(2, "DAFTAR PUSTAKA"),
        _body(
            3,
            "Smith, J. 2020. Solar Energy Fundamentals yang cukup panjang. "
            "New York: Springer.",
        ),
    ]
    parser = _fake_parser(paras)
    r = ReferenceValidator(parser, schema, current_year=2026).check()
    missing = [f for f in r.balance_findings if f.direction == "in_text_not_in_references"]
    assert missing
    assert "typo" in missing[0].detail.lower() or "smyth" in missing[0].detail.lower()


def test_dp_heading_but_no_entries_explains_gap(schema):
    """Judul DP ada, LAMPIRAN langsung setelah baris kosong → pesan spesifik."""
    paras = [
        _heading(0, "BAB 1. PENDAHULUAN"),
        _body(1, "Teks (Smith, 2020) dengan cukup panjang untuk pemeriksaan."),
        _heading(2, "DAFTAR PUSTAKA"),
        _body(3, ""),
        _heading(4, "LAMPIRAN"),
    ]
    parser = _fake_parser(paras)
    r = ReferenceValidator(parser, schema, current_year=2026).check()
    assert r.total_entries == 0
    assert r.dp_heading_paragraph_index == 2
    assert r.lampiran_heading_paragraph_index == 4
    joined = " ".join(m.text for m in r.messages)
    assert "terdeteksi" in joined.lower()
    assert "lampiran" in joined.lower()
    d = r.to_dict()
    assert d["section_detection"]["daftar_pustaka_heading_paragraph_index"] == 2


NUKI_FIXTURE = Path(r"c:\Users\ac300\Downloads\PKM KC  NUKI OTISTA_evp_KP_030426.docx")


@pytest.mark.skipif(not NUKI_FIXTURE.exists(), reason="Lokal: file contoh Zotero tidak ada")
def test_zotero_sdt_bibliography_extracted(schema):
    """Dokumen dengan bibliografi di w:sdt (Zotero) punya entri DP terbaca."""
    from app.services.docx_parser import DocxParser

    r = ReferenceValidator(DocxParser(NUKI_FIXTURE), schema, current_year=2026).check()
    assert r.total_entries >= 10
    assert r.dp_heading_paragraph_index is not None
    assert r.entries[0].author_first is not None
