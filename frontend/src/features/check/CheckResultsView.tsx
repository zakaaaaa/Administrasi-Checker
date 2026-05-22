'use client';

import { useMemo } from 'react';
import type { CheckResults } from '@/features/check/types';

type Message = { level: string; text: string };
type ModuleData = {
  status?: string;
  messages?: Message[];
  message?: string;
  schema?: { code?: string };
};

const MODULES = [
  { key: 'structure', label: 'Struktur Dokumen' },
  { key: 'ai_front_matter', label: 'Front Matter' },
  { key: 'physical_sheet', label: 'Lembar Fisik' },
  { key: 'format', label: 'Format Penulisan' },
  { key: 'page_numbering', label: 'Penomoran Halaman' },
  { key: 'budget', label: 'Anggaran' },
  { key: 'reference', label: 'Daftar Pustaka' },
  { key: 'luaran', label: 'Luaran' },
  { key: 'lampiran', label: 'Lampiran' },
  { key: 'biodata_date', label: 'Tanggal Biodata' },
  { key: 'schedule', label: 'Jadwal Kegiatan' },
];

function getMessages(mod: ModuleData): Message[] {
  if (Array.isArray(mod.messages)) return mod.messages;
  if (typeof mod.message === 'string' && mod.message.trim())
    return [{ level: 'error', text: mod.message }];
  return [];
}

function parseMessage(text: string): { lokasi: string; masalah: string } {
  const cleaned = text.replace(/^\s*•\s*/, '').trim();
  const match = cleaned.match(/^\[([^\]]+)\]\s*([\s\S]+)$/);
  if (match) return { lokasi: match[1], masalah: match[2] };
  return { lokasi: '', masalah: cleaned };
}

function extractPageNumber(lokasi: string): number | null {
  const m = lokasi.match(/Halaman\s*~?\s*(\d+)/i);
  return m ? parseInt(m[1], 10) : null;
}

function isSummaryLine(text: string): boolean {
  return (
    /pelanggaran terdeteksi/.test(text) ||
    /Urutan alfabetis Daftar Pustaka tidak sesuai/i.test(text) ||
    // summary lines dari PkmAiFormatChecker: "check_name: N pelanggaran" atau "check_name: OK"
    /^[a-z_]+: \d+ pelanggaran$/.test(text.trim()) ||
    /^[a-z_]+: OK$/.test(text.trim())
  );
}

function isBalanceSummary(text: string): boolean {
  return (
    /\d+ sitasi di teks tidak ditemukan/i.test(text) ||
    /tidak pernah disitasi di body teks/i.test(text)
  );
}

// Peta kalimat predefined per modul
function mapToSentence(module: string, masalah: string, schemaCode = 'PKM'): string {
  const m = masalah.toLowerCase();

  switch (module) {
    case 'structure': {
      if (/halaman[_\s]judul|sampul|pengesahan|ringkasan|abstrak|abstract/.test(m))
        return 'Kesalahan terdapat lembar judul / halaman sampul / lembar pengesahan / ringkasan / abstrak di proposal';
      if (/daftar[_\s]isi/.test(m))
        return 'Kesalahan tidak terdapat daftar isi';
      if (/luaran/.test(m))
        return 'Kesalahan menuliskan 4 luaran wajib PKM di proposal pada Bab 1 Pendahuluan';
      const sectionMatch = masalah.match(/'([^']+)'/);
      const section = sectionMatch ? sectionMatch[1] : '';
      if (/tidak ditemukan di dokumen/i.test(masalah))
        return `Kesalahan tidak ditemukan (${section})`;
      return `Kesalahan Judul Bab (${section}) tidak sesuai panduan ${schemaCode} 2026`;
    }

    case 'ai_front_matter': {
      // Judul
      if (/melebihi batas 20 kata|word.count/i.test(m)) {
        const countMatch = masalah.match(/\((\d+) kata\)/);
        return `Kesalahan judul melebihi batas 20 kata${countMatch ? ` (${countMatch[1]} kata)` : ''}`;
      }
      if (/huruf kapital semua|all caps/i.test(m))
        return 'Kesalahan judul tidak seluruhnya huruf kapital (ALL CAPS)';
      if (/judul.*tidak ditemukan|tidak ditemukan.*judul/i.test(m))
        return 'Kesalahan judul artikel tidak ditemukan di front matter';
      if (/font judul bukan|judul.*times new roman/i.test(m))
        return 'Kesalahan font judul bukan Times New Roman';
      if (/ukuran font judul|judul.*12pt|judul.*bukan 12/i.test(m))
        return 'Kesalahan ukuran font judul bukan 12pt';
      if (/judul.*bold|judul.*tebal/i.test(m))
        return 'Kesalahan judul tidak dicetak tebal (bold)';
      // Penulis / institusi
      if (/font nama penulis.*times|penulis.*times new roman/i.test(m))
        return 'Kesalahan font nama penulis/institusi bukan Times New Roman';
      if (/ukuran font.*penulis|penulis.*10pt|penulis.*bukan 10/i.test(m))
        return 'Kesalahan ukuran font nama penulis/institusi bukan 10pt';
      if (/penulis.*bold|penulis.*tebal/i.test(m))
        return 'Kesalahan nama penulis/institusi dicetak tebal, harusnya normal';
      if (/penulis.*italic|penulis.*miring/i.test(m))
        return 'Kesalahan nama penulis/institusi dicetak miring, harusnya normal';
      // Abstrak Indonesia
      if (/abstrak.*indonesia.*tidak ditemukan|abstrak \(indonesia\) tidak/i.test(m))
        return 'Kesalahan Abstrak Indonesia tidak ditemukan';
      if (/abstrak.*indonesia.*250|abstrak.*indonesia.*kata/i.test(m)) {
        const countMatch = masalah.match(/\((\d+) kata\)/);
        return `Kesalahan Abstrak Indonesia melebihi 250 kata${countMatch ? ` (${countMatch[1]} kata)` : ''}`;
      }
      if (/font abstrak.*indonesia.*times|abstrak.*indonesia.*times/i.test(m))
        return 'Kesalahan font Abstrak Indonesia bukan Times New Roman';
      if (/ukuran font abstrak.*indonesia|abstrak.*indonesia.*11pt/i.test(m))
        return 'Kesalahan ukuran font Abstrak Indonesia bukan 11pt';
      // Abstract English
      if (/abstract.*english.*tidak ditemukan|abstract \(english\) tidak/i.test(m))
        return 'Kesalahan Abstract English tidak ditemukan';
      if (/abstract.*english.*250|abstract.*english.*kata/i.test(m)) {
        const countMatch = masalah.match(/\((\d+) kata\)/);
        return `Kesalahan Abstract English melebihi 250 kata${countMatch ? ` (${countMatch[1]} kata)` : ''}`;
      }
      if (/font abstract.*english.*times|abstract.*english.*times/i.test(m))
        return 'Kesalahan font Abstract English bukan Times New Roman';
      if (/ukuran font abstract.*english|abstract.*english.*11pt/i.test(m))
        return 'Kesalahan ukuran font Abstract English bukan 11pt';
      if (/abstract.*english.*italic|abstract.*english.*miring/i.test(m))
        return 'Kesalahan Abstract English tidak dicetak miring (italic)';
      // Spasi front matter
      if (/spasi baris front matter|front matter.*1\.0/i.test(m))
        return 'Kesalahan Judul Artikel, Nama Penulis, Alamat Institusi, Abstrak Tidak Menggunakan Spasi Baris 1.0';
      return masalah;
    }

    case 'format': {
      if (/ukuran kertas|bukan a4/.test(m))
        return 'Kesalahan ukuran kertas bukan A4';
      if (/ukuran font(?! keterangan)|bukan 12/.test(m)) {
        const snippetMatch = masalah.match(/"([^"]+)"/);
        const snippet = snippetMatch ? ` — "${snippetMatch[1]}"` : '';
        return `Kesalahan ukuran huruf tidak 12${snippet}`;
      }
      if (/ukuran font keterangan/.test(m)) {
        const snippetMatch = masalah.match(/"([^"]+)"/);
        const snippet = snippetMatch ? ` — "${snippetMatch[1]}"` : '';
        return `Kesalahan ukuran huruf keterangan gambar/tabel bukan 11${snippet}`;
      }
      if (/^font bukan|font body bukan|bukan times new roman/.test(m)) {
        const snippetMatch = masalah.match(/"([^"]+)"/);
        const snippet = snippetMatch ? ` - "${snippetMatch[1]}"` : '';
        return `Kesalahan tipe huruf tidak Times New Roman${snippet}`;
      }
      if (/margin/.test(m)) {
        if (/margin left|margin kiri/.test(m)) return 'Kesalahan margin kiri bukan 4cm';
        if (/margin right|margin kanan/.test(m)) return 'Kesalahan margin kanan bukan 3cm';
        if (/margin top|margin atas/.test(m)) return 'Kesalahan margin atas bukan 3cm';
        if (/margin bottom|margin bawah/.test(m)) return 'Kesalahan margin bawah bukan 3cm';
        return 'Kesalahan margin tidak sesuai aturan PKM';
      }
      if (/keterangan gambar|keterangan tabel/.test(m)) {
        const snippetMatch = masalah.match(/"([^"]+)"/);
        const snippet = snippetMatch ? ` — "${snippetMatch[1]}"` : '';
        return `Kesalahan spasi keterangan gambar/tabel bukan 1${snippet}`;
      }
      if (/line spacing|spacing bukan/.test(m))
        return 'Kesalahan spasi teks/paragraf tidak 1,15';
      if (/justify|bukan justify/.test(m))
        return 'Kesalahan perataan teks/paragraf tidak rata kiri-kanan';
      if (/kolom/.test(m))
        return 'Kesalahan format paragraf tidak satu kolom';
      if (/indent|indentasi/.test(m))
        return 'Kesalahan indentasi paragraf berlebihan (paragraf menggeser teks ke kanan)';
      if (/italic|asing/.test(m)) {
        // Ekstrak daftar kata asing dari backend: "...asing (word1, word2) tapi..."
        const wordsMatch = masalah.match(/\(([^)]+)\)/);
        const words = wordsMatch ? ` (${wordsMatch[1]})` : '';
        return `Paragraf memuat kata asing${words} namun belum italic`;
      }
      return masalah;
    }

    case 'page_numbering': {
      if (schemaCode === 'PKM-AI') {
        if (/tidak terdeteksi|missing/.test(m))
          return 'Nomor halaman arab (1, 2, 3...) tidak ditemukan di dokumen';
        if (/posisi|position|bawah|bottom/.test(m))
          return 'Kesalahan letak nomor halaman (harusnya pojok kanan atas untuk semua halaman PKM-AI)';
        if (/numeral|roman_lower|roman/.test(m))
          return 'Kesalahan jenis nomor halaman (harusnya angka arab untuk semua halaman PKM-AI, bukan romawi)';
        if (/font|ukuran|times/.test(m))
          return 'Kesalahan format font nomor halaman (harusnya Times New Roman 12pt)';
        return 'Kesalahan nomor halaman';
      }
      if (/front.matter.*tidak terdeteksi|tidak terdeteksi.*front.matter|roman_lower/.test(m))
        return 'Nomor halaman romawi kecil (i, ii, iii) tidak ditemukan di bagian awal dokumen';
      if (/core.matter.*tidak terdeteksi|tidak terdeteksi.*core.matter|arabic.*top.right/.test(m))
        return 'Nomor halaman arab tidak ditemukan di bagian isi dokumen (Bab 1 s.d. Daftar Pustaka)';
      if (/letak|posisi|atas|bawah|header|footer/.test(m))
        return 'Kesalahan letak nomor halaman (harusnya pojok kanan atas untuk isi, pojok kanan bawah untuk awal)';
      if (/jenis|roman|arabic|arab|romawi/.test(m))
        return 'Kesalahan jenis nomor halaman (romawi kecil untuk awal, angka arab untuk isi)';
      if (/font|ukuran|times/.test(m))
        return 'Kesalahan format font nomor halaman (harusnya Times New Roman 12pt)';
      return 'Kesalahan nomor halaman';
    }

    case 'physical_sheet': {
      if (/melebihi batas|melebihi.*lembar|lembar.*melebihi/i.test(m)) {
        const maxMatch = masalah.match(/melebihi batas (\d+)/i);
        const max = maxMatch ? maxMatch[1] : '10';
        return `Kesalahan jumlah halaman inti yang melebihi ${max} halaman`;
      }
      const duplikat = masalah.match(/Nomor halaman '(\d+)' duplikat — muncul di lembar fisik:\s*([\d,\s]+)/i);
      if (duplikat) {
        const [, num, sheets] = duplikat;
        return `Kesalahan duplikasi nomor halaman "${num}" muncul di lembar ${sheets.trim()}`;
      }
      const meloncat = masalah.match(/Nomor halaman meloncat: dari '(\d+)'/i);
      if (meloncat) {
        const [, num] = meloncat;
        return `Kesalahan urutan nomor halaman "${num}"`;
      }
      return masalah;
    }

    case 'budget': {
      if (/belmawa/.test(m))
        return 'Kesalahan nominal pengajuan anggaran ke Belmawa (6–8 juta)';
      if (/perguruan tinggi|dana pt/.test(m))
        return 'Kesalahan nominal dana pendampingan perguruan tinggi (tidak ada atau lebih dari 2 juta)';
      if (/institusi lain|eksternal/.test(m))
        return 'Kesalahan dana pendampingan institusi lain (lebih dari 1 juta atau tidak menyertakan surat keterangan)';
      if (/justifikasi|cross.check|tidak sama/.test(m))
        return 'Kesalahan total anggaran pada tabel rekapitulasi tidak sama dengan justifikasi anggaran di lampiran';
      return 'Kesalahan format rekapitulasi rencana anggaran biaya';
    }

    case 'reference':
      return 'Kesalahan daftar pustaka (tidak Harvard style, urutan abjad, dan menguraikan nama penulis)';

    case 'luaran': {
      const schemaMatch = masalah.match(/Luaran (PKM-\w+)/i);
      const luaranSchema = schemaMatch ? schemaMatch[1].toUpperCase() : 'PKM';
      if (/yang tidak ditemukan:/i.test(m)) {
        const missingMatch = masalah.match(/yang tidak ditemukan:\s*([^.]+)/i);
        const missing = missingMatch ? missingMatch[1].trim() : '';
        return `Kesalahan luaran ${luaranSchema} tidak lengkap${missing ? ` ${missing}` : ''}`;
      }
      if (/section.*tidak ditemukan|tidak ditemukan.*dokumen/i.test(m))
        return `Kesalahan section Luaran tidak ditemukan di dokumen ${luaranSchema}`;
      if (/melebihi batas/i.test(m)) {
        const countMatch = masalah.match(/memuat (\d+) luaran/i);
        const count = countMatch ? countMatch[1] : '';
        return `Kesalahan jumlah luaran ${luaranSchema} melebihi 4${count ? ` (terdeteksi ${count})` : ''}`;
      }
      if (/hanya memuat (\d+)/i.test(m)) {
        const countMatch = masalah.match(/hanya memuat (\d+)/i);
        const count = countMatch ? countMatch[1] : '';
        return `Kesalahan jumlah luaran ${luaranSchema} kurang dari 4${count ? ` (terdeteksi ${count})` : ''}`;
      }
      return masalah;
    }

    case 'lampiran': {
      const numMatch = masalah.match(/Lampiran (\d+) \(([^)]+)\)/i);
      if (numMatch) {
        const [, num, label] = numMatch;
        return `Kesalahan Lampiran ${num} (${label}) tidak ditemukan di dokumen`;
      }
      return masalah;
    }

    case 'biodata_date': {
      if (/tidak dapat terdeteksi/i.test(m))
        return 'Tanggal tanda tangan biodata tidak terdeteksi — periksa manual (harus 9 Maret s.d. 9 April 2026)';
      if (/tidak valid/i.test(m)) {
        const dateMatch = masalah.match(/'([^']+)'/);
        const tgl = dateMatch ? dateMatch[1] : '';
        return `Kesalahan tanggal/bulan/tahun${tgl ? ` '${tgl}'` : ''} di lampiran biodata tidak antara 9 Maret s.d. 9 April 2026`;
      }
      return masalah;
    }

    case 'schedule': {
      if (/tidak terdeteksi/i.test(m))
        return 'Tabel jadwal kegiatan tidak terdeteksi — periksa manual (kolom: No, Jadwal Kegiatan, Bulan, Penanggung Jawab)';
      if (/header kolom|tidak ditemukan di tabel jadwal/i.test(m)) {
        const colMatch = masalah.match(/"([^"]+)"/);
        const col = colMatch ? ` "${colMatch[1]}"` : '';
        return `Kesalahan penulisan header kolom tabel jadwal${col} (wajib persis: No, Jadwal Kegiatan, Bulan, Penanggung Jawab)`;
      }
      if (/jumlah bulan|rentang bulan|melebihi batas/i.test(m)) {
        const cntMatch = masalah.match(/jumlah bulan pada tabel jadwal (\d+)/i);
        const cnt = cntMatch ? ` (terdeteksi ${cntMatch[1]} bulan)` : '';
        return `Kesalahan jumlah bulan tabel jadwal harus tepat 4 bulan${cnt}`;
      }
      if (/penanggung jawab kosong/i.test(m)) {
        const noMatch = masalah.match(/nomor (\d+)/i);
        const no = noMatch ? ` (kegiatan nomor ${noMatch[1]})` : '';
        return `Kolom Penanggung Jawab pada tabel jadwal belum terisi${no}`;
      }
      return masalah;
    }
  }

  return masalah;
}

// Reformat pesan Daftar Pustaka ke kalimat yang lebih deskriptif
function formatReferenceMessage(masalah: string): string {
  // Urutan alfabetis: "'Author1' muncul setelah 'Author2' (seharusnya sebelum)."
  const orderMatch = masalah.match(/'([^']+)'\s+muncul setelah\s+'([^']+)'/i);
  if (orderMatch) {
    const [, cur, prev] = orderMatch;
    return `Kesalahan urutan alfabetis "${cur}" harusnya sebelum "${prev}"`;
  }
  return masalah;
}

// Reformat pesan cross-check anggaran ke kalimat yang lebih deskriptif
function formatBudgetMessage(masalah: string): string {
  // Cross-check: "Cross-check Bab 4 ↔ Lampiran 2 untuk 'Category': Bab 4 = RpX, Lampiran 2 = RpY, selisih RpZ"
  const crossCheck = masalah.match(
    /untuk\s+'([^']+)'[^:]*:\s*Bab\s+4\s+=\s+(Rp[\d.,]+).*?Lampiran\s+2\s+=\s+(Rp[\d.,]+)/i
  );
  if (crossCheck) {
    const [, category, bab4, lampiran2] = crossCheck;
    return `Kesalahan total anggaran pada BAB 4 tabel rekapitulasi anggaran (${category} = ${bab4}) tidak sama dengan justifikasi anggaran di lampiran (${lampiran2})`;
  }

  // Item terlarang: "Item TERLARANG: 'Nama Item' (RpX) — mengandung kata kunci '...' yang dilarang di ..."
  const prohibited = masalah.match(/Item TERLARANG:\s*'([^']+)'/i);
  if (prohibited) {
    const [, itemName] = prohibited;
    return `Terdapat item terlarang "${itemName}" yang dilarang`;
  }

  // Volume melebihi batas: "Volume berjangka waktu melebihi batas: 'Nama Item' (...) — volume '...' (...) melebihi maksimum N bulan ..."
  const duration = masalah.match(/Volume berjangka waktu melebihi batas:\s*'([^']+)'/i);
  if (duration) {
    const [, itemName] = duration;
    return `Jangka waktu pembelian "${itemName}" tidak boleh lebih dari 4 bulan`;
  }

  // Saran relokasi: "Saran relokasi / pecah justifikasi: 'Nama Item' — harga satuan RpX melebihi patokan ..."
  const relokasi = masalah.match(/Saran relokasi[^:]*:\s*'([^']+)'/i);
  if (relokasi) {
    const [, itemName] = relokasi;
    return `Harga satuan "${itemName}" tidak boleh melebihi 1 juta`;
  }

  return masalah;
}

type ErrorItem = {
  module: string;
  moduleLabel: string;
  level: string;
  masalah: string;
  page: number | null;
};

type BalanceGroup = { header: string; items: string[] };

function parseBalanceGroups(notes: string[]): BalanceGroup[] {
  const groups: BalanceGroup[] = [];
  let current: BalanceGroup | null = null;
  for (const note of notes) {
    if (note.startsWith('•')) {
      if (current) current.items.push(note.replace(/^•\s*/, '').trim());
    } else {
      if (current) groups.push(current);
      current = { header: note, items: [] };
    }
  }
  if (current) groups.push(current);
  return groups;
}

export function CheckResultsView({ result }: { result: CheckResults }) {
  const resultMap = result.results as Record<string, ModuleData | undefined>;

  const { flatItems, budgetItems, referenceItems, balanceNotes } = useMemo(() => {
    const flat: ErrorItem[] = [];
    const budget: ErrorItem[] = [];
    const reference: ErrorItem[] = [];
    const balance: string[] = [];

    // Ambil kode skema dari structure result (mis. "KC" → "PKM-KC")
    const structureSchema = resultMap.structure?.schema?.code;
    const schemaCode = structureSchema ? `PKM-${structureSchema}` : 'PKM';

    for (const { key, label } of MODULES) {
      const mod = resultMap[key];
      if (!mod) continue;

      if (key === 'reference') {
        let inBalance = false;
        for (const msg of getMessages(mod)) {
          if (msg.level !== 'fail' && msg.level !== 'error' && msg.level !== 'warning') continue;
          if (isSummaryLine(msg.text)) continue;
          if (isBalanceSummary(msg.text)) {
            inBalance = true;
            balance.push(msg.text.trim());
          } else if (inBalance && /^\s*•/.test(msg.text)) {
            balance.push(msg.text.trim());
          } else {
            inBalance = false;
            const { lokasi, masalah } = parseMessage(msg.text);
            reference.push({
              module: key,
              moduleLabel: label,
              level: msg.level,
              masalah: formatReferenceMessage(masalah),
              page: extractPageNumber(lokasi),
            });
          }
        }
        continue;
      }

      for (const msg of getMessages(mod)) {
        if (msg.level !== 'fail' && msg.level !== 'error' && msg.level !== 'warning') continue;
        if (isSummaryLine(msg.text)) continue;
        const { lokasi, masalah } = parseMessage(msg.text);
        const isBudgetRelokasiWarning =
          key === 'budget' && /Saran relokasi/i.test(masalah);
        const isBudgetNoPage =
          key === 'budget' && (
            /Saran relokasi/i.test(masalah) ||
            /Item TERLARANG/i.test(masalah) ||
            /Volume berjangka waktu melebihi batas/i.test(masalah)
          );
        const item: ErrorItem = {
          module: key,
          moduleLabel: label,
          level: isBudgetRelokasiWarning ? 'fail' : msg.level,
          masalah: key === 'budget' ? formatBudgetMessage(masalah) : mapToSentence(key, masalah, schemaCode),
          page: isBudgetNoPage ? null : extractPageNumber(lokasi),
        };
        if (key === 'budget') {
          budget.push(item);
        } else {
          flat.push(item);
        }
      }
    }

    // Deduplikasi: pesan identik dengan halaman yang sama (atau keduanya null) hanya tampil sekali
    const seenKeys = new Set<string>();
    const dedupedFlat = flat.filter(item => {
      const key = `${item.module}|${item.masalah}|${item.page}`;
      if (seenKeys.has(key)) return false;
      seenKeys.add(key);
      return true;
    });

    dedupedFlat.sort((a, b) => {
      if (a.page === null && b.page === null) return 0;
      if (a.page === null) return -1;
      if (b.page === null) return 1;
      return a.page - b.page;
    });

    return {
      flatItems: dedupedFlat,
      budgetItems: budget,
      referenceItems: reference,
      balanceNotes: balance,
    };
  }, [resultMap]);

  const allErrors = [...flatItems, ...budgetItems, ...referenceItems];
  const failCount = allErrors.filter(e => e.level === 'fail' || e.level === 'error').length;
  const warnCount = allErrors.filter(e => e.level === 'warning').length;
  const balanceGroups = parseBalanceGroups(balanceNotes);

  if (allErrors.length === 0 && balanceGroups.length === 0) {
    return (
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-8 text-center">
        <p className="text-xl font-semibold text-emerald-700">Semua pengecekan lulus!</p>
        <p className="mt-1 text-sm text-emerald-600">Tidak ada kesalahan yang ditemukan.</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Summary badges */}
      <div className="flex flex-wrap gap-3">
        {failCount > 0 && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-2.5">
            <p className="text-sm font-semibold text-red-700">{failCount} harus diperbaiki</p>
          </div>
        )}
        {warnCount > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5">
            <p className="text-sm font-semibold text-amber-700">{warnCount} perlu diperhatikan</p>
          </div>
        )}
        {balanceGroups.length > 0 && (
          <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-2.5">
            <p className="text-sm font-semibold text-sky-700">{balanceGroups.length} saran sitasi</p>
          </div>
        )}
      </div>

      {/* Flat list — kesalahan umum, per halaman */}
      {flatItems.length > 0 && (
        <div className="space-y-2">
          {flatItems.map((item, i) => (
            <ErrorRow key={i} item={item} showPage />
          ))}
        </div>
      )}

      {/* Audit Anggaran */}
      {budgetItems.length > 0 && (
        <GroupedSection label="Audit Anggaran" items={budgetItems} showPage />
      )}

      {/* Daftar Pustaka */}
      {referenceItems.length > 0 && (
        <GroupedSection label="Daftar Pustaka" items={referenceItems} showPage />
      )}

      {/* Saran Perbaikan — balance notes sitasi */}
      {balanceGroups.length > 0 && (
        <SaranPerbaikanSection groups={balanceGroups} />
      )}
    </div>
  );
}

function ErrorRow({ item, showPage = false }: { item: ErrorItem; showPage?: boolean }) {
  const isFail = item.level === 'fail' || item.level === 'error';
  const rowCls = isFail ? 'border-red-100 bg-red-50/60' : 'border-amber-100 bg-amber-50/60';
  const dotCls = isFail ? 'bg-red-400' : 'bg-amber-400';
  const textCls = isFail ? 'text-red-900' : 'text-amber-900';
  const tagCls = isFail ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700';
  const pageCls = isFail ? 'text-red-400' : 'text-amber-400';

  return (
    <div className={`flex items-start gap-3 rounded-xl border px-4 py-3 ${rowCls}`}>
      <span className={`mt-2.5 h-2.5 w-2.5 shrink-0 rounded-full ${dotCls}`} />
      {showPage && (
        <span className={`mt-0.5 w-20 shrink-0 font-mono text-sm font-medium ${pageCls}`}>
          {item.page !== null ? `Hal. ${item.page}` : ''}
        </span>
      )}
      <p className={`flex-1 text-base font-medium leading-relaxed ${textCls}`}>{item.masalah}</p>
      <span className={`shrink-0 rounded px-2 py-0.5 font-mono text-xs font-semibold ${tagCls}`}>
        {item.moduleLabel}
      </span>
    </div>
  );
}

function GroupedSection({ label, items, showPage = false }: { label: string; items: ErrorItem[]; showPage?: boolean }) {
  return (
    <div>
      <p className="mb-2.5 text-sm font-semibold uppercase tracking-wider text-foreground-subtle">
        {label}
      </p>
      <div className="space-y-2">
        {items.map((item, i) => (
          <ErrorRow key={i} item={item} showPage={showPage} />
        ))}
      </div>
    </div>
  );
}

function SaranPerbaikanSection({ groups }: { groups: BalanceGroup[] }) {
  return (
    <div>
      <p className="mb-3 text-sm font-semibold uppercase tracking-wider text-foreground-subtle">
        Saran Perbaikan
      </p>
      <div className="space-y-3">
        {groups.map((group, gi) => (
          <div key={gi} className="rounded-2xl border border-sky-200 bg-sky-50/60 p-5">
            <p className="mb-3 text-base font-semibold text-sky-800">{group.header}</p>
            {group.items.length > 0 && (
              <ul className="space-y-1.5">
                {group.items.map((item, ii) => (
                  <li key={ii} className="flex items-start gap-2 text-base text-sky-700">
                    <span className="mt-0.5 shrink-0 font-mono text-sky-400">•</span>
                    <span className="font-mono">{item}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
