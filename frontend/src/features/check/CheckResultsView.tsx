'use client';

import type { CheckResults } from '@/features/check/types';

type Message = { level: string; text: string };

export function CheckResultsView({ result }: { result: CheckResults }) {
  const overallColor =
    result.overall_status === 'pass'
      ? 'text-emerald-700'
      : result.overall_status === 'warning'
        ? 'text-amber-700'
        : 'text-red-700';

  const modules = [
    { key: 'structure', label: 'Struktur Dokumen' },
    { key: 'physical_sheet', label: 'Jumlah Lembar Fisik' },
    { key: 'format', label: 'Format Penulisan' },
    { key: 'page_numbering', label: 'Penomoran Halaman' },
    { key: 'budget', label: 'Audit Anggaran' },
    { key: 'reference', label: 'Daftar Pustaka' },
  ] as const;

  return (
    <section id="check-result-content" className="glass-surface rounded-[1.75rem] p-6 sm:p-8">
      <p className="font-mono text-sm uppercase tracking-[0.2em] text-foreground-subtle">
        Hasil Pengecekan
      </p>
      <div className="mt-2 flex items-baseline gap-3">
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">Status keseluruhan:</h2>
        <span className={`text-2xl font-semibold uppercase ${overallColor}`}>
          {result.overall_status === 'pass'
            ? 'Lulus'
            : result.overall_status === 'warning'
              ? 'Perlu Diperhatikan'
              : 'Belum Lulus'}
        </span>
      </div>
      <p className="mt-1 text-sm text-foreground-subtle">
        Submission ID: <code>{result.submission_id}</code>
      </p>

      <div className="mt-6 grid gap-3">
        {modules.map(({ key, label }) => {
          const mod = result.results[key] as {
            status?: string;
            messages?: Message[];
            message?: string;
          };
          const status = mod?.status ?? 'unknown';
          const messages = Array.isArray(mod?.messages)
            ? mod.messages
            : typeof mod?.message === 'string' && mod.message.trim()
              ? [{ level: 'error' as const, text: mod.message }]
              : [];
          return <ModuleCard key={key} label={label} status={status} messages={messages} />;
        })}
      </div>
    </section>
  );
}

function ModuleCard({
  label,
  status,
  messages,
}: {
  label: string;
  status: string;
  messages: Message[];
}) {
  const statusBadge =
    status === 'pass'
      ? { text: 'Lulus', cls: 'text-emerald-700 bg-emerald-50/70 border-emerald-200' }
      : status === 'warning'
        ? { text: 'Perhatian', cls: 'text-amber-700 bg-amber-50/70 border-amber-200' }
        : status === 'fail'
          ? { text: 'Belum Lulus', cls: 'text-red-700 bg-red-50/70 border-red-200' }
          : status === 'error'
            ? { text: 'Error', cls: 'text-red-700 bg-red-50/70 border-red-200' }
            : { text: status, cls: 'text-gray-700 bg-gray-50/70 border-gray-200' };

  const fails = messages.filter((m) => m.level === 'fail' || m.level === 'error');
  const warnings = messages.filter((m) => m.level === 'warning');
  const passes = messages.filter((m) => m.level === 'pass' || m.level === 'info');
  const defaultOpen = status !== 'pass';

  return (
    <details open={defaultOpen} className="glass-surface-subtle rounded-2xl border border-white/50">
      <summary className="flex cursor-pointer items-center justify-between p-4 text-sm">
        <div className="flex items-center gap-3">
          <span className="font-medium text-foreground">{label}</span>
          {messages.length > 0 && (
            <span className="text-xs text-foreground-subtle">({messages.length} catatan)</span>
          )}
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusBadge.cls}`}>
          {statusBadge.text}
        </span>
      </summary>

      <div className="border-t border-white/40 px-4 py-4">
        {messages.length === 0 ? (
          <p className="text-sm text-foreground-muted">Tidak ada catatan.</p>
        ) : (
          <div className="space-y-4">
            {fails.length > 0 && (
              <MessageTable
                title="Harus Diperbaiki"
                items={fails}
                rowCls="text-red-800"
                titleCls="text-red-700"
              />
            )}
            {warnings.length > 0 && (
              <MessageTable
                title="Perlu Diperhatikan"
                items={warnings}
                rowCls="text-amber-800"
                titleCls="text-amber-700"
              />
            )}
            {passes.length > 0 && (
              <MessageTable
                title="Sudah Sesuai"
                items={passes}
                rowCls="text-emerald-800"
                titleCls="text-emerald-700"
              />
            )}
          </div>
        )}
      </div>
    </details>
  );
}

function MessageTable({
  title,
  items,
  rowCls,
  titleCls,
}: {
  title: string;
  items: Message[];
  rowCls: string;
  titleCls: string;
}) {
  return (
    <div>
      <p className={`mb-2 text-xs font-semibold uppercase tracking-wider ${titleCls}`}>
        {title} ({items.length})
      </p>
      <div className="overflow-hidden rounded-xl border border-white/40 bg-white/30">
        <table className="w-full text-sm">
          <thead className="bg-white/40 text-xs uppercase tracking-wider text-foreground-subtle">
            <tr>
              <th className="w-12 px-3 py-2 text-left">#</th>
              <th className="px-3 py-2 text-left">Catatan</th>
            </tr>
          </thead>
          <tbody>
            {items.map((m, i) => {
              const { lokasi, masalah } = parseMessage(m.text);
              return (
                <tr key={i} className="border-t border-white/30 align-top">
                  <td className={`px-3 py-2 text-xs ${rowCls}`}>{i + 1}</td>
                  <td className={`px-3 py-2 leading-relaxed ${rowCls}`}>
                    {lokasi && (
                      <span className="mr-2 inline-block rounded bg-white/50 px-2 py-0.5 text-[11px] font-medium">
                        {lokasi}
                      </span>
                    )}
                    {masalah}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function parseMessage(text: string): { lokasi: string; masalah: string } {
  const cleaned = text.replace(/^\s*•\s*/, '').trim();
  const match = cleaned.match(/^\[([^\]]+)\]\s*(.+)$/);
  if (match) return { lokasi: match[1], masalah: match[2] };
  return { lokasi: '', masalah: cleaned };
}
