import { useCallback, useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { AdminMenuIcon } from './AdminMenuIcon';
import { API_URL } from './constants';
import type { ReviewerRecord } from './types';

type Props = {
  adminId: string;
};

type ListResponse = {
  reviewers: ReviewerRecord[];
  total: number;
  active_count: number;
};

type FormState = {
  full_name: string;
  username: string;
  password: string;
};

type ApiResult<T> = { ok: true; data: T } | { ok: false; message: string };

const EMPTY_FORM: FormState = { full_name: '', username: '', password: '' };
const PASSWORD_MIN = 8;

function formatDateTime(value: string | null): string {
  return value
    ? new Date(value).toLocaleString('id-ID', { dateStyle: 'short', timeStyle: 'short' })
    : '-';
}

function errorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail;
  // Error validasi FastAPI (422): [{ msg, loc, ... }]
  if (Array.isArray(detail) && detail.length && typeof detail[0]?.msg === 'string') {
    return detail[0].msg;
  }
  return fallback;
}

async function requestJson<T>(url: string, init: RequestInit, fallback: string): Promise<ApiResult<T>> {
  try {
    const res = await fetch(url, init);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, message: errorMessage(data?.detail, fallback) };
    return { ok: true, data: data as T };
  } catch (err) {
    return {
      ok: false,
      message: `Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`,
    };
  }
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
}

function RefreshIcon({ loading }: { loading: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`}
    >
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 1 0 .49-3.51" />
    </svg>
  );
}

function ModalShell({
  label,
  onClose,
  children,
}: {
  label: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={label}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/55 p-4 backdrop-blur-sm"
    >
      <div className="max-h-[calc(100vh-2rem)] w-full max-w-md overflow-y-auto rounded-2xl border border-border bg-surface-elevated p-6 shadow-xl sm:p-7">
        {children}
      </div>
    </div>
  );
}

function FieldLabel({ htmlFor, children }: { htmlFor: string; children: ReactNode }) {
  return (
    <label
      htmlFor={htmlFor}
      className="text-[10px] font-semibold uppercase tracking-wide text-foreground-subtle"
    >
      {children}
    </label>
  );
}

function ReviewerFormModal({
  mode,
  initial,
  saving,
  error,
  onSubmit,
  onClose,
}: {
  mode: 'create' | 'edit';
  initial: FormState;
  saving: boolean;
  error: string;
  onSubmit: (form: FormState) => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState<FormState>(initial);
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState('');
  const isCreate = mode === 'create';

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLocalError('');
    if (!form.full_name.trim()) return setLocalError('Nama lengkap wajib diisi.');
    if (form.username.trim().length < 3) return setLocalError('Username minimal 3 karakter.');
    if ((isCreate || form.password) && form.password.length < PASSWORD_MIN) {
      return setLocalError(`Password minimal ${PASSWORD_MIN} karakter.`);
    }
    onSubmit(form);
  }

  const shownError = localError || error;

  return (
    <ModalShell label={isCreate ? 'Tambah reviewer' : 'Ubah reviewer'} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground">
            {isCreate ? 'Tambah Reviewer' : 'Ubah Reviewer'}
          </h2>
          <p className="mt-1 text-xs text-foreground-muted">
            {isCreate
              ? 'Akun ini dipakai untuk login di halaman /reviewer.'
              : 'Kosongkan password jika tidak ingin menggantinya.'}
          </p>
        </div>

        <div className="flex flex-col gap-1">
          <FieldLabel htmlFor="rv-name">Nama Lengkap</FieldLabel>
          <input
            id="rv-name"
            autoFocus
            value={form.full_name}
            maxLength={120}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            placeholder="contoh: Budi Santoso"
            className="glass-input w-full rounded-xl px-3 py-2 text-sm"
          />
        </div>

        <div className="flex flex-col gap-1">
          <FieldLabel htmlFor="rv-username">Username</FieldLabel>
          <input
            id="rv-username"
            value={form.username}
            maxLength={50}
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            onChange={(e) => setForm({ ...form, username: e.target.value.toLowerCase() })}
            placeholder="contoh: budi.santoso"
            className="glass-input w-full rounded-xl px-3 py-2 font-mono text-sm"
          />
          <p className="text-[11px] text-foreground-subtle">
            Huruf kecil, angka, titik, garis bawah, atau tanda hubung.
          </p>
        </div>

        <div className="flex flex-col gap-1">
          <FieldLabel htmlFor="rv-password">{isCreate ? 'Password' : 'Password Baru (opsional)'}</FieldLabel>
          <div className="relative">
            <input
              id="rv-password"
              type={showPassword ? 'text' : 'password'}
              value={form.password}
              maxLength={72}
              autoComplete="new-password"
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder={isCreate ? `Minimal ${PASSWORD_MIN} karakter` : 'Biarkan kosong jika tidak diganti'}
              className="glass-input w-full rounded-xl py-2 pl-3 pr-16 text-sm"
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg px-2 py-1 text-[11px] font-semibold text-foreground-muted hover:bg-white/50"
            >
              {showPassword ? 'Sembunyi' : 'Lihat'}
            </button>
          </div>
        </div>

        {shownError && (
          <div className="rounded-2xl border border-red-300 bg-red-50/70 p-3 text-sm font-semibold text-red-700">
            {shownError}
          </div>
        )}

        <div className="flex flex-col-reverse gap-2 pt-1 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold text-foreground-muted transition hover:bg-white/50"
          >
            Batal
          </button>
          <button
            type="submit"
            disabled={saving}
            className="btn-liquid btn-liquid-primary px-5 py-2.5 text-sm font-semibold disabled:opacity-60"
          >
            {saving ? 'Menyimpan...' : isCreate ? 'Tambah Reviewer' : 'Simpan Perubahan'}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function DeleteReviewerModal({
  reviewer,
  deleting,
  error,
  onConfirm,
  onClose,
}: {
  reviewer: ReviewerRecord;
  deleting: boolean;
  error: string;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <ModalShell label="Hapus reviewer" onClose={onClose}>
      <h2 className="text-lg font-semibold text-foreground">Hapus reviewer?</h2>
      <p className="mt-2 text-sm text-foreground-muted">
        Akun <span className="font-semibold text-foreground">{reviewer.full_name}</span>{' '}
        (<code className="font-mono text-xs">{reviewer.username}</code>) akan dihapus permanen dan tidak bisa
        login lagi.
      </p>
      {reviewer.check_count > 0 && (
        <p className="mt-2 text-sm text-foreground-muted">
          Riwayat {reviewer.check_count} pengecekan miliknya tetap tersimpan di Riwayat Upload. Kalau hanya ingin
          memblokir sementara, pilih <span className="font-semibold">Nonaktifkan</span> saja.
        </p>
      )}
      {error && (
        <div className="mt-3 rounded-2xl border border-red-300 bg-red-50/70 p-3 text-sm font-semibold text-red-700">
          {error}
        </div>
      )}
      <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <button
          type="button"
          onClick={onClose}
          className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold text-foreground-muted transition hover:bg-white/50"
        >
          Batal
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={deleting}
          className="rounded-xl bg-red-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-60"
        >
          {deleting ? 'Menghapus...' : 'Hapus'}
        </button>
      </div>
    </ModalShell>
  );
}

export function ReviewerManagementPanel({ adminId }: Props) {
  const [reviewers, setReviewers] = useState<ReviewerRecord[]>([]);
  const [activeCount, setActiveCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [listError, setListError] = useState('');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [notice, setNotice] = useState('');

  const [formMode, setFormMode] = useState<'create' | 'edit' | null>(null);
  const [editing, setEditing] = useState<ReviewerRecord | null>(null);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);

  const [deleting, setDeleting] = useState<ReviewerRecord | null>(null);
  const [deleteError, setDeleteError] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [togglingId, setTogglingId] = useState('');

  const fetchReviewers = useCallback(async () => {
    if (!adminId) return;
    setLoading(true);
    setListError('');
    const params = new URLSearchParams({ admin_id: adminId });
    if (debouncedSearch) params.set('q', debouncedSearch);
    const result = await requestJson<ListResponse>(
      `${API_URL}/api/admin/reviewers?${params.toString()}`,
      {},
      'Gagal memuat daftar reviewer',
    );
    if (result.ok) {
      setReviewers(Array.isArray(result.data.reviewers) ? result.data.reviewers : []);
      setActiveCount(result.data.active_count ?? 0);
    } else {
      setListError(result.message);
    }
    setLoading(false);
  }, [adminId, debouncedSearch]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchReviewers();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchReviewers]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 350);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(''), 4000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  function openCreate() {
    setEditing(null);
    setFormError('');
    setFormMode('create');
  }

  function openEdit(reviewer: ReviewerRecord) {
    setEditing(reviewer);
    setFormError('');
    setFormMode('edit');
  }

  function closeForm() {
    if (saving) return;
    setFormMode(null);
    setEditing(null);
  }

  async function handleSubmit(form: FormState) {
    setSaving(true);
    setFormError('');
    const payload = {
      admin_id: adminId,
      full_name: form.full_name,
      username: form.username,
      ...(form.password ? { password: form.password } : {}),
    };
    const result =
      formMode === 'edit' && editing
        ? await requestJson<{ reviewer: ReviewerRecord }>(
            `${API_URL}/api/admin/reviewers/${editing.id}`,
            jsonInit('PATCH', payload),
            'Gagal menyimpan perubahan',
          )
        : await requestJson<{ reviewer: ReviewerRecord }>(
            `${API_URL}/api/admin/reviewers`,
            jsonInit('POST', payload),
            'Gagal menambah reviewer',
          );
    setSaving(false);
    if (!result.ok) {
      setFormError(result.message);
      return;
    }
    setNotice(
      formMode === 'edit'
        ? `Data reviewer ${result.data.reviewer.full_name} diperbarui.`
        : `Reviewer ${result.data.reviewer.full_name} ditambahkan. Login di /reviewer dengan username ${result.data.reviewer.username}.`,
    );
    setFormMode(null);
    setEditing(null);
    void fetchReviewers();
  }

  async function handleToggleActive(reviewer: ReviewerRecord) {
    setTogglingId(reviewer.id);
    setListError('');
    const result = await requestJson<{ reviewer: ReviewerRecord }>(
      `${API_URL}/api/admin/reviewers/${reviewer.id}`,
      jsonInit('PATCH', { admin_id: adminId, is_active: !reviewer.is_active }),
      'Gagal mengubah status reviewer',
    );
    setTogglingId('');
    if (!result.ok) {
      setListError(result.message);
      return;
    }
    setNotice(
      `Reviewer ${reviewer.full_name} ${result.data.reviewer.is_active ? 'diaktifkan' : 'dinonaktifkan'}.`,
    );
    void fetchReviewers();
  }

  async function handleDelete() {
    if (!deleting) return;
    setDeleteLoading(true);
    setDeleteError('');
    const params = new URLSearchParams({ admin_id: adminId });
    const result = await requestJson<{ deleted: boolean }>(
      `${API_URL}/api/admin/reviewers/${deleting.id}?${params.toString()}`,
      { method: 'DELETE' },
      'Gagal menghapus reviewer',
    );
    setDeleteLoading(false);
    if (!result.ok) {
      setDeleteError(result.message);
      return;
    }
    setNotice(`Reviewer ${deleting.full_name} dihapus.`);
    setDeleting(null);
    void fetchReviewers();
  }

  const total = reviewers.length;
  const inactiveCount = total - activeCount;

  return (
    <div className="glass-surface rounded-[1.5rem] p-6 sm:p-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <AdminMenuIcon name="reviewers" className="h-4 w-4 text-brand-600" />
          <h2 className="text-lg font-semibold text-foreground">Kelola Reviewer</h2>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={fetchReviewers}
            disabled={loading}
            className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl border border-border px-3 text-xs font-medium text-foreground-muted transition hover:border-brand-200 hover:text-foreground disabled:opacity-50"
          >
            <RefreshIcon loading={loading} />
            Refresh
          </button>
          <button
            type="button"
            onClick={openCreate}
            className="btn-liquid btn-liquid-primary inline-flex h-10 items-center px-4 text-xs font-semibold"
          >
            + Tambah Reviewer
          </button>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded-full bg-white/50 px-3 py-1 text-xs font-semibold text-foreground-muted">
          {debouncedSearch ? 'Hasil' : 'Total'}: {total}
        </span>
        <span className="rounded-full bg-green-100/80 px-3 py-1 text-xs font-semibold text-green-700">
          Aktif: {activeCount}
        </span>
        <span className="rounded-full bg-slate-200/70 px-3 py-1 text-xs font-semibold text-slate-700">
          Nonaktif: {inactiveCount}
        </span>
      </div>

      <div className="mt-4 flex flex-col gap-1 sm:max-w-sm">
        <FieldLabel htmlFor="reviewer-search">Cari Reviewer</FieldLabel>
        <input
          id="reviewer-search"
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Nama atau username"
          className="glass-input w-full rounded-xl px-3 py-2 text-xs font-medium placeholder:text-foreground-subtle"
        />
      </div>

      {notice && (
        <div className="mt-4 rounded-2xl border border-green-300 bg-green-50/70 p-3 text-sm font-semibold text-green-700">
          {notice}
        </div>
      )}

      {listError && (
        <div className="mt-4 rounded-2xl border border-red-300 bg-red-50/70 p-3 text-sm font-semibold text-red-700">
          {listError}
        </div>
      )}

      {loading && reviewers.length === 0 && (
        <div className="mt-6 py-8 text-center text-sm text-foreground-muted">Memuat data reviewer...</div>
      )}

      {!loading && !listError && reviewers.length === 0 && (
        <div className="mt-6 rounded-2xl border border-dashed border-border bg-surface py-8 text-center">
          <p className="text-sm text-foreground-muted">
            {debouncedSearch
              ? 'Tidak ada reviewer yang cocok dengan pencarian.'
              : 'Belum ada akun reviewer. Klik "Tambah Reviewer" untuk membuat.'}
          </p>
        </div>
      )}

      {reviewers.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-2xl">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border">
                {['Reviewer', 'Status', 'Jumlah Cek', 'Terakhir Cek', 'Dibuat', 'Aksi'].map((h) => (
                  <th
                    key={h}
                    className={`px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-foreground-subtle ${
                      h === 'Aksi' ? 'text-right' : ''
                    }`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {reviewers.map((r) => (
                <tr key={r.id} className="border-b border-border transition hover:bg-surface">
                  <td className="px-3 py-2.5">
                    <p className="font-semibold text-foreground">{r.full_name}</p>
                    <code className="font-mono text-xs text-foreground-muted">{r.username}</code>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    {r.is_active ? (
                      <span className="inline-flex items-center rounded-full bg-green-100/80 px-2.5 py-0.5 text-xs font-semibold text-green-700">
                        Aktif
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-slate-200/70 px-2.5 py-0.5 text-xs font-semibold text-slate-700">
                        Nonaktif
                      </span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 font-mono text-xs text-foreground">
                    {r.check_count}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-xs text-foreground-muted">
                    {formatDateTime(r.last_check_at)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-xs text-foreground-muted">
                    {formatDateTime(r.created_at)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <div className="flex justify-end gap-1.5">
                      <button
                        type="button"
                        onClick={() => openEdit(r)}
                        className="rounded-lg border border-border px-2.5 py-1.5 text-xs font-semibold text-foreground-muted transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
                      >
                        Ubah
                      </button>
                      <button
                        type="button"
                        onClick={() => handleToggleActive(r)}
                        disabled={togglingId === r.id}
                        className="rounded-lg border border-border px-2.5 py-1.5 text-xs font-semibold text-foreground-muted transition hover:bg-white/60 hover:text-foreground disabled:opacity-50"
                      >
                        {togglingId === r.id ? '...' : r.is_active ? 'Nonaktifkan' : 'Aktifkan'}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setDeleteError('');
                          setDeleting(r);
                        }}
                        className="rounded-lg border border-red-200 px-2.5 py-1.5 text-xs font-semibold text-red-600 transition hover:bg-red-50"
                      >
                        Hapus
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {formMode && (
        <ReviewerFormModal
          key={editing?.id ?? 'new'}
          mode={formMode}
          initial={
            editing
              ? { full_name: editing.full_name, username: editing.username, password: '' }
              : EMPTY_FORM
          }
          saving={saving}
          error={formError}
          onSubmit={handleSubmit}
          onClose={closeForm}
        />
      )}

      {deleting && (
        <DeleteReviewerModal
          reviewer={deleting}
          deleting={deleteLoading}
          error={deleteError}
          onConfirm={handleDelete}
          onClose={() => {
            if (!deleteLoading) setDeleting(null);
          }}
        />
      )}
    </div>
  );
}
