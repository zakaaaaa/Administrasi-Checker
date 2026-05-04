"""
Inspect DocxParser output pada file .docx apa pun.

Usage:
    python3 tests/inspect_docx.py <path_to_file.docx>

Contoh:
    python3 tests/inspect_docx.py tests/sample_docs/dummy_pkm_kc.docx
    python3 tests/inspect_docx.py /path/ke/laporan_real.docx

Output yang ditampilkan:
1. Summary umum (jumlah paragraf, tabel, section, dll)
2. Daftar heading yang terdeteksi (penting untuk verifikasi heuristik)
3. Daftar tabel (penting untuk RAB detection nanti)
4. Section info (margin, paper size, page numbering)
5. Section boundaries (default vs headings_only)
6. Header/footer XML keys
7. Sample run dengan info font (cek konsistensi TNR 12pt)
8. Warning yang terkumpul saat parsing
"""

import sys
from pathlib import Path

# Pastikan path import benar saat dijalankan dari folder backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.docx_parser import DocxParser, dxa_to_cm


def inspect(file_path: str) -> None:
    print(f"\n{'='*70}")
    print(f"INSPECTING: {file_path}")
    print(f"{'='*70}\n")

    try:
        parser = DocxParser(file_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ ERROR: {e}")
        return

    # 1. Summary
    print("─── 1. SUMMARY ─────────────────────────────────────────────")
    s = parser.summary()
    for k, v in s.items():
        if k == "warnings":
            continue
        print(f"  {k:25s} : {v}")
    print()

    # 2. Heading detection
    print("─── 2. HEADING YANG TERDETEKSI ────────────────────────────")
    headings = [p for p in parser.paragraphs if p.is_heading]
    if not headings:
        print("  ⚠️  Tidak ada heading terdeteksi (mungkin dokumen pakai bold-center,")
        print("      bukan style 'Heading N'). Heuristik perlu diperkuat.")
    else:
        for p in headings[:30]:
            level = p.heading_level if p.heading_level is not None else "?"
            preview = p.text.strip()[:60]
            print(f"  [#{p.index:4d}] level={level} | {preview}")
        if len(headings) > 30:
            print(f"  ... dan {len(headings) - 30} heading lagi")
    print(f"  Total heading: {len(headings)}")
    print()

    # 3. Tabel
    print("─── 3. TABEL ──────────────────────────────────────────────")
    if not parser.tables:
        print("  ⚠️  Tidak ada tabel terdeteksi.")
    else:
        for t in parser.tables:
            preview = " | ".join(h[:25] for h in t.header_texts[:6])
            print(f"  Tabel #{t.index}: {t.rows} baris x {t.cols} kolom")
            print(f"    Header: {preview}")
    print()

    # 4. Section info
    print("─── 4. SECTION INFO ───────────────────────────────────────")
    for sec in parser.sections:
        print(f"  Section #{sec.index}:")
        print(f"    margin (cm): L={dxa_to_cm(sec.margin_left_dxa)} "
              f"R={dxa_to_cm(sec.margin_right_dxa)} "
              f"T={dxa_to_cm(sec.margin_top_dxa)} "
              f"B={dxa_to_cm(sec.margin_bottom_dxa)}")
        print(f"    paper size (cm): W={dxa_to_cm(sec.page_width_dxa)} "
              f"H={dxa_to_cm(sec.page_height_dxa)}")
        print(f"    page_num: format={sec.page_num_format} "
              f"start={sec.page_num_start}")
        print(f"    header_refs: {sec.header_refs or '(none)'}")
        print(f"    footer_refs: {sec.footer_refs or '(none)'}")
    print()

    # 5. Section boundaries
    print("─── 5. SECTION BOUNDARIES (PKM-KC) ────────────────────────")
    target_sections = [
        "DAFTAR ISI", "DAFTAR LAMPIRAN", "BAB 1", "BAB 2",
        "BAB 3", "BAB 4", "DAFTAR PUSTAKA", "LAMPIRAN",
    ]
    print("  Default (match kemunculan pertama, termasuk ToC):")
    b1 = parser.find_section_boundaries(target_sections)
    for k, v in b1.items():
        if v is not None:
            preview = parser.paragraphs[v].text.strip()[:50]
            is_h = parser.paragraphs[v].is_heading
            mark = "✓" if is_h else "✗ToC?"
            print(f"    {k:18s} -> #{v:4d} [{mark}] | {preview}")
        else:
            print(f"    {k:18s} -> NOT FOUND")
    print()
    print("  headings_only=True (skip baris ToC, hanya heading asli):")
    b2 = parser.find_section_boundaries(target_sections, headings_only=True)
    for k, v in b2.items():
        if v is not None:
            preview = parser.paragraphs[v].text.strip()[:50]
            print(f"    {k:18s} -> #{v:4d} | {preview}")
        else:
            print(f"    {k:18s} -> NOT FOUND")
    print()

    # 6. Header/footer XML
    print("─── 6. HEADER/FOOTER XML PARTS ────────────────────────────")
    if parser.header_xmls:
        print(f"  Header parts ({len(parser.header_xmls)}):")
        for name in parser.header_xmls:
            print(f"    - {name}")
    else:
        print("  ⚠️  Tidak ada header part (PageNumberingChecker akan kesulitan)")
    if parser.footer_xmls:
        print(f"  Footer parts ({len(parser.footer_xmls)}):")
        for name in parser.footer_xmls:
            print(f"    - {name}")
    else:
        print("  ⚠️  Tidak ada footer part")
    print()

    # 7. Sample run dengan font info — ringkasan distribusi font
    print("─── 7. DISTRIBUSI FONT DI BODY ────────────────────────────")
    font_counts: dict[str, int] = {}
    size_counts: dict[float, int] = {}
    no_font_run_count = 0
    for _, run in parser.iter_runs():
        if run.text and run.text.strip():
            if run.font_name:
                font_counts[run.font_name] = font_counts.get(run.font_name, 0) + 1
            else:
                no_font_run_count += 1
            if run.font_size_pt is not None:
                size_counts[run.font_size_pt] = size_counts.get(run.font_size_pt, 0) + 1
    print("  Font:")
    if font_counts:
        for name, count in sorted(font_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"    {count:6d}x  {name}")
    if no_font_run_count > 0:
        print(f"    {no_font_run_count:6d}x  (font tidak terbaca / inherited dari style)")
    print("  Ukuran (pt):")
    if size_counts:
        for size, count in sorted(size_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"    {count:6d}x  {size} pt")
    else:
        print("    (tidak ada size yang terbaca eksplisit dari run)")
    print()

    # 8. Images
    print("─── 8. IMAGES (word/media/) ───────────────────────────────")
    if parser.images:
        for img in parser.images:
            kb = img.size_bytes / 1024
            print(f"  {img.filename:30s} {img.content_type:15s} {kb:.1f} KB")
    else:
        print("  (tidak ada gambar)")
    print()

    # 9. Warnings
    print("─── 9. PARSER WARNINGS ────────────────────────────────────")
    if parser.warnings:
        for w in parser.warnings:
            print(f"  ⚠️  {w}")
    else:
        print("  ✓ Tidak ada warning")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    inspect(sys.argv[1])