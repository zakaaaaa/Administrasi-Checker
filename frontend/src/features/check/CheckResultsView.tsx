'use client';

import { useMemo } from 'react';
import type { CheckResults } from '@/features/check/types';

type Message = { level: string; text: string };
type ModuleData = { status?: string; messages?: Message[]; message?: string };

const MODULES = [
  { key: 'structure', label: 'Struktur Dokumen' },
  { key: 'ai_front_matter', label: 'Front Matter' },
  { key: 'physical_sheet', label: 'Lembar Fisik' },
  { key: 'format', label: 'Format Penulisan' },
  { key: 'page_numbering', label: 'Penomoran Halaman' },
  { key: 'budget', label: 'Anggaran' },
  { key: 'reference', label: 'Daftar Pustaka' },
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
  return /pelanggaran terdeteksi/.test(text);
}

function isBalanceSummary(text: string): boolean {
  return (
    /\d+ sitasi di teks tidak ditemukan/i.test(text) ||
    /tidak pernah disitasi di body teks/i.test(text)
  );
}

// Peta kalimat predefined per modul
function mapToSentence(module: string, masalah: string): string {
  const m = masalah.toLowerCase();

  switch (module) {
    case 'structure':
    case 'ai_front_matter': {
      if (/halaman[_\s]judul|sampul|pengesahan|ringkasan|abstrak|abstract/.test(m))
        return 'Kesalahan terdapat lembar judul / halaman sampul / lembar pengesahan / ringkasan / abstrak di proposal';
      if (/daftar[_\s]isi/.test(m))
        return 'Kesalahan tidak terdapat daftar isi';
      if (/luaran/.test(m))
        return 'Kesalahan menuliskan 4 luaran wajib PKM di proposal pada Bab 1 Pendahuluan';
      if (/jadwal/.test(m))
        return 'Kesalahan format jadwal kegiatan tidak sesuai Lampiran 1 buku panduan PKM 2026';
      if (/waktu|pelaksanaan/.test(m))
        return 'Kesalahan waktu pelaksanaan (tidak 3–4 bulan)';
      // Out-of-order, forbidden, atau section lain yang tidak dikenal
      return 'Kesalahan judul bab tidak sesuai panduan PKM 2026';
    }

    case 'format': {
      if (/ukuran kertas|bukan a4/.test(m))
        return 'Kesalahan ukuran kertas bukan A4';
      if (/font bukan|bukan times/.test(m)) {
        // Sertakan snippet teks yang salah font (format backend: Font bukan TNR — "snippet")
        const snippetMatch = masalah.match(/"([^"]+)"/);
        const snippet = snippetMatch ? ` — "${snippetMatch[1]}"` : '';
        return `Kesalahan tipe huruf tidak Times New Roman${snippet}`;
      }
      if (/ukuran font|bukan 12/.test(m))
        return 'Kesalahan ukuran huruf tidak 12';
      if (/margin/.test(m))
        return 'Kesalahan margin (kiri ≠ 4cm, atas / kanan / bawah ≠ 3cm)';
      if (/line spacing|spacing bukan/.test(m))
        return 'Kesalahan spasi teks/paragraf tidak 1,15';
      if (/justify|bukan justify/.test(m))
        return 'Kesalahan perataan teks/paragraf tidak rata kiri-kanan';
      if (/kolom/.test(m))
        return 'Kesalahan format paragraf tidak satu kolom';
      if (/italic|asing/.test(m)) {
        // Ekstrak daftar kata asing dari backend: "...asing (word1, word2) tapi..."
        const wordsMatch = masalah.match(/\(([^)]+)\)/);
        const words = wordsMatch ? ` (${wordsMatch[1]})` : '';
        return `Paragraf memuat kata asing${words} tapi belum italic`;
      }
      return masalah;
    }

    case 'page_numbering': {
      if (/letak|posisi|atas|bawah|header|footer/.test(m))
        return 'Kesalahan letak nomor halaman';
      return 'Kesalahan nomor halaman';
    }

    case 'physical_sheet':
      return 'Kesalahan jumlah halaman inti yang melebihi 10 halaman';

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

// Deduplikasi: satu kalimat predefined hanya muncul sekali; ambil severity terburuk
function deduplicateBySentence(items: ErrorItem[]): ErrorItem[] {
  const seen = new Map<string, ErrorItem>();
  for (const item of items) {
    const existing = seen.get(item.masalah);
    if (!existing) {
      seen.set(item.masalah, item);
    } else {
      const isFail = (e: ErrorItem) => e.level === 'fail' || e.level === 'error';
      if (!isFail(existing) && isFail(item)) {
        seen.set(item.masalah, item);
      }
    }
  }
  return Array.from(seen.values());
}

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
              masalah,
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
          masalah: key === 'budget' ? formatBudgetMessage(masalah) : mapToSentence(key, masalah),
          page: isBudgetNoPage ? null : extractPageNumber(lokasi),
        };
        if (key === 'budget') {
          budget.push(item);
        } else {
          flat.push(item);
        }
      }
    }

    // Flat list: tidak deduplikasi — tampilkan per halaman, urutkan ascending
    flat.sort((a, b) => {
      if (a.page === null && b.page === null) return 0;
      if (a.page === null) return -1;
      if (b.page === null) return 1;
      return a.page - b.page;
    });

    return {
      flatItems: flat,
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
        <div className="space-y-1.5">
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
    <div className={`flex items-start gap-3 rounded-xl border px-3 py-2.5 ${rowCls}`}>
      <span className={`mt-2 h-2 w-2 shrink-0 rounded-full ${dotCls}`} />
      {showPage && (
        <span className={`mt-0.5 w-16 shrink-0 font-mono text-xs font-medium ${pageCls}`}>
          {item.page !== null ? `Hal. ${item.page}` : ''}
        </span>
      )}
      <p className={`flex-1 text-sm font-medium leading-snug ${textCls}`}>{item.masalah}</p>
      <span className={`shrink-0 rounded px-1.5 py-0.5 font-mono text-xs font-medium ${tagCls}`}>
        {item.moduleLabel}
      </span>
    </div>
  );
}

function GroupedSection({ label, items, showPage = false }: { label: string; items: ErrorItem[]; showPage?: boolean }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
        {label}
      </p>
      <div className="space-y-1.5">
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
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
        Saran Perbaikan
      </p>
      <div className="space-y-3">
        {groups.map((group, gi) => (
          <div key={gi} className="rounded-2xl border border-sky-200 bg-sky-50/60 p-4">
            <p className="mb-2.5 text-sm font-semibold text-sky-800">{group.header}</p>
            {group.items.length > 0 && (
              <ul className="space-y-1">
                {group.items.map((item, ii) => (
                  <li key={ii} className="flex items-start gap-2 text-sm text-sky-700">
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
