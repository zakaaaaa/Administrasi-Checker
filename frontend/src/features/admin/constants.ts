import type { MenuItem } from './types';

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
export const STORAGE_KEY = 'admin_session_v1';

export const MENU_ITEMS: MenuItem[] = [
  {
    key: 'dashboard',
    label: 'Overview',
    description: 'Ringkasan metrik harian.',
    active: false,
  },
  {
    key: 'token',
    label: 'Generate Token',
    description: 'Buat token sekali pakai untuk user.',
    active: true,
  },
  {
    key: 'monitoring',
    label: 'Monitoring Token',
    description: 'Pantau status pemakaian token.',
    active: true,
  },
  {
    key: 'uploads',
    label: 'Riwayat Upload',
    description: 'Log seluruh berkas masuk.',
    active: true,
  },
  {
    key: 'server',
    label: 'Monitoring Server',
    description: 'CPU, RAM, dan Disk usage.',
    active: false,
  },
];
