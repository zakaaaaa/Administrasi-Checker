export type SkemaCode =
  | 'PKM-KC'
  | 'PKM-K'
  | 'PKM-RE'
  | 'PKM-RSH'
  | 'PKM-PM'
  | 'PKM-PI'
  | 'PKM-KI'
  | 'PKM-VGK'
  | 'PKM-GFT'
  | 'PKM-AI';

export type ReportCode = 'PROPOSAL' | 'PROGRESS_REPORT' | 'FINAL_REPORT' | 'SCIENTIFIC_ARTICLE';

export type ReportOption = { code: ReportCode; label: string; desc: string };

export const ALL_REPORTS: ReportOption[] = [
  { code: 'PROPOSAL', label: 'Proposal', desc: 'Pengajuan awal kegiatan' },
  { code: 'PROGRESS_REPORT', label: 'Laporan Kemajuan', desc: 'Update progress mid-term' },
  { code: 'FINAL_REPORT', label: 'Laporan Akhir', desc: 'Hasil akhir kegiatan' },
  { code: 'SCIENTIFIC_ARTICLE', label: 'Artikel Ilmiah', desc: 'Publikasi karya tulis' },
];

const THREE_REPORTS: ReportCode[] = ['PROPOSAL', 'PROGRESS_REPORT', 'FINAL_REPORT'];

export const SKEMA_LAPORAN_MAP: Record<SkemaCode, ReportCode[]> = {
  'PKM-K': THREE_REPORTS,
  'PKM-RE': THREE_REPORTS,
  'PKM-PM': THREE_REPORTS,
  'PKM-KC': THREE_REPORTS,
  'PKM-VGK': THREE_REPORTS,
  'PKM-RSH': THREE_REPORTS,
  'PKM-KI': THREE_REPORTS,
  'PKM-PI': THREE_REPORTS,
  'PKM-GFT': ['PROPOSAL'],
  'PKM-AI': ['SCIENTIFIC_ARTICLE'],
};

export const SKEMA_OPTIONS: { value: SkemaCode; label: string; desc: string }[] = [
  { value: 'PKM-KC', label: 'PKM-KC', desc: 'Karsa Cipta' },
  { value: 'PKM-K', label: 'PKM-K', desc: 'Kewirausahaan' },
  { value: 'PKM-RE', label: 'PKM-RE', desc: 'Riset Eksakta' },
  { value: 'PKM-RSH', label: 'PKM-RSH', desc: 'Riset Sosial Humaniora' },
  { value: 'PKM-PM', label: 'PKM-PM', desc: 'Pengabdian Masyarakat' },
  { value: 'PKM-PI', label: 'PKM-PI', desc: 'Penerapan IPTEK' },
  { value: 'PKM-KI', label: 'PKM-KI', desc: 'Karya Inovatif' },
  { value: 'PKM-VGK', label: 'PKM-VGK', desc: 'Video Gagasan Konstruktif' },
  { value: 'PKM-GFT', label: 'PKM-GFT', desc: 'Gagasan Futuristik Tertulis' },
  { value: 'PKM-AI', label: 'PKM-AI', desc: 'Artikel Ilmiah' },
];

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
export const LAST_RESULT_STORAGE_KEY = 'last_check_result_v1';
export const MAX_FILE_MB = 25;

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}
