'use client';

// Batas progress selama MENUNGGU respons. Bar parkir di sini (tahap OCR),
// bukan di "Menyusun hasil". 100% hanya saat respons betulan datang.
export const PROGRESS_WAIT_CAP = 85;

// Tahap-tahap yang berjalan SELAMA proses. Bobot = alokasi waktu relatif;
// OCR 20% lebih lama (1.2) dari lainnya (1.0).
const PROCESSING_STAGES: { label: string; weight: number }[] = [
  { label: 'Mengunggah dokumen', weight: 1 },
  { label: 'Membaca struktur dokumen', weight: 1 },
  { label: 'Memeriksa format & penomoran', weight: 1 },
  { label: 'Memindai lampiran (OCR)', weight: 1.2 },
];

// Threshold `at` tahap proses dihitung dari bobot, diskala ke PROGRESS_WAIT_CAP →
// lebar bar tiap tahap ∝ alokasi waktunya (laju fill seragam, OCR 20% lebih lebar).
// "Menyusun hasil" = finalisasi: ditaruh di PROGRESS_WAIT_CAP, hanya aktif setelah
// respons datang (saat progress didorong melewati batas tunggu menuju 100%).
const TOTAL_WEIGHT = PROCESSING_STAGES.reduce((sum, s) => sum + s.weight, 0);
export const PROGRESS_STAGES: { label: string; at: number }[] = (() => {
  let acc = 0;
  const stages = PROCESSING_STAGES.map((s) => {
    const at = (acc / TOTAL_WEIGHT) * PROGRESS_WAIT_CAP;
    acc += s.weight;
    return { label: s.label, at };
  });
  stages.push({ label: 'Menyusun hasil', at: PROGRESS_WAIT_CAP });
  return stages;
})();

function Spinner() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4 animate-spin text-brand-500">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.2" />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

function CheckMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-3 w-3"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export function CheckProgressModal({ progress }: { progress: number }) {
  const pct = Math.min(100, Math.round(progress));

  // Stage berjalan = stage terakhir yang ambangnya sudah dilewati.
  let activeIdx = 0;
  for (let i = 0; i < PROGRESS_STAGES.length; i++) {
    if (pct >= PROGRESS_STAGES[i].at) activeIdx = i;
  }
  const allDone = pct >= 100;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Proses pengecekan dokumen"
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/55 p-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-md rounded-2xl border border-border bg-surface-elevated p-6 shadow-xl sm:p-7">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-semibold text-foreground">
            {allDone ? 'Pengecekan selesai' : 'Memeriksa dokumen…'}
          </h2>
          <span className="font-display text-2xl font-bold tabular-nums text-brand-600">
            {pct}%
          </span>
        </div>

        {/* Progress bar */}
        <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-surface-sunken">
          <div
            className="h-full rounded-full bg-brand-500 transition-[width] duration-300 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>

        {/* Stage list */}
        <ul className="mt-5 space-y-2.5">
          {PROGRESS_STAGES.map((stage, i) => {
            const done = allDone || i < activeIdx;
            const active = !allDone && i === activeIdx;
            return (
              <li key={stage.label} className="flex items-center gap-3">
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${
                    done
                      ? 'bg-brand-500 text-white'
                      : active
                        ? 'bg-brand-50'
                        : 'bg-surface-sunken'
                  }`}
                >
                  {done ? <CheckMark /> : active ? <Spinner /> : null}
                </span>
                <span
                  className={`text-sm ${
                    done || active ? 'text-foreground' : 'text-foreground-subtle'
                  } ${active ? 'font-medium' : ''}`}
                >
                  {stage.label}
                </span>
              </li>
            );
          })}
        </ul>

        <p className="mt-5 text-xs text-foreground-subtle">
          Mohon jangan tutup atau muat ulang halaman ini sampai proses selesai.
        </p>
      </div>
    </div>
  );
}
