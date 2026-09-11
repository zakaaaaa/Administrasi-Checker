export type MenuKey =
  | 'token'
  | 'monitoring'
  | 'dashboard'
  | 'users'
  | 'uploads'
  | 'reviewers'
  | 'server'
  | 'settings';

export type MenuItem = {
  key: MenuKey;
  label: string;
  description: string;
  active: boolean;
};

export type TokenRecord = {
  token: string;
  created_at: string | null;
  used: boolean;
  used_at: string | null;
};

export type ReviewerRecord = {
  id: string;
  username: string;
  full_name: string;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
  check_count: number;
  last_check_at: string | null;
};

export type IconName = MenuKey | 'home' | 'logout' | 'user' | 'key' | 'pulse';
