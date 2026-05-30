"""
Test syarat lampiran "Surat Pernyataan Komitmen Tambahan Pendanaan" — wajib
hanya bila proposal mencantumkan dana Instansi Lain (>Rp0) di Rekap Sumber Dana
Bab 4. Berlaku ke semua skema pendanaan PKM; tidak ke PKM-AI/PKM-GFT (tanpa
anggaran), karena orchestrator tidak meneruskan flag di sana.
"""
import unittest
from dataclasses import dataclass

from app.services.lampiran_checker import LampiranChecker, _funding_letter_present
from app.services.orchestrator import _funding_letter_required


@dataclass
class _Para:
    index: int
    text: str
    is_heading: bool = False


class _StubParser:
    def __init__(self, paras):
        self.paragraphs = paras


class _StubIndex:
    """Index OCR tiruan: tidak ada gambar → korpus OCR kosong."""

    def rids_in_range(self, *a, **k):
        return []

    def ocr_text_for_rids(self, rids):
        return ""


def _build(body_text: str) -> _StubParser:
    return _StubParser([
        _Para(0, "BAB 1 PENDAHULUAN", True),
        _Para(1, "isi"),
        _Para(2, "LAMPIRAN", True),
        _Para(3, "Lampiran 1 Biodata Ketua dan Anggota serta Dosen Pendamping"),
        _Para(4, "Lampiran 2 Justifikasi Anggaran"),
        _Para(5, "Lampiran 3 Susunan Tim Pengusul dan Pembagian Tugas"),
        _Para(6, "Lampiran 4 Surat Pernyataan Ketua"),
        _Para(7, "Lampiran 5 Gambaran Teknologi"),
        _Para(8, "Lampiran 6 Hasil Uji Periksa Similaritas Proposal"),
        _Para(9, body_text),
    ])


def _check(body_text: str, require_funding_letter: bool):
    c = LampiranChecker.for_pkm_kc(_build(body_text))
    c.require_daftar = False  # fokus uji syarat surat, lewati cross-check Daftar Lampiran
    return c.check(index=_StubIndex(), require_funding_letter=require_funding_letter)


class TestFundingLetterPhrase(unittest.TestCase):
    def test_official_term(self):
        self.assertTrue(_funding_letter_present(
            "… Surat Pernyataan Komitmen Tambahan Pendanaan dari PT XYZ …"
        ))

    def test_user_term(self):
        self.assertTrue(_funding_letter_present(
            "surat keterangan pendanaan institusi lain"
        ))

    def test_no_false_positive_on_bare_instansi_lain(self):
        # "Instansi Lain" tanpa kata "pendanaan" (mis. di RAB) tidak boleh memicu.
        self.assertFalse(_funding_letter_present("Instansi Lain Rp1.000.000"))


class TestFundingLetterRequirement(unittest.TestCase):
    def test_present_and_required_passes(self):
        r = _check("Surat Pernyataan Komitmen Tambahan Pendanaan dari PT", True)
        self.assertEqual(r.status, "pass")

    def test_absent_and_required_fails(self):
        r = _check("teks lampiran biasa tanpa surat", True)
        self.assertEqual(r.status, "fail")
        self.assertTrue(any(
            "Komitmen Tambahan Pendanaan" in m.text for m in r.messages
        ))

    def test_absent_but_not_required_passes(self):
        r = _check("teks lampiran biasa tanpa surat", False)
        self.assertEqual(r.status, "pass")


class TestFundingLetterTrigger(unittest.TestCase):
    def _budget(self, external):
        return {"budget": {"rekap_sumber_dana": {"external_rp": external}}}

    def test_external_positive_triggers(self):
        self.assertTrue(_funding_letter_required(self._budget(500_000)))

    def test_external_zero_does_not_trigger(self):
        self.assertFalse(_funding_letter_required(self._budget(0)))

    def test_external_none_does_not_trigger(self):
        self.assertFalse(_funding_letter_required(self._budget(None)))

    def test_budget_error_payload_does_not_trigger(self):
        self.assertFalse(_funding_letter_required({"budget": {"status": "error"}}))

    def test_missing_budget_does_not_trigger(self):
        self.assertFalse(_funding_letter_required({}))


if __name__ == "__main__":
    unittest.main()
