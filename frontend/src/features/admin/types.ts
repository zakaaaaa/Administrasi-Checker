export type MenuKey =
  | 'token'
  | 'monitoring'
  | 'dashboard'
  | 'users'
  | 'uploads'
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

export type IconName = MenuKey | 'home' | 'logout' | 'user' | 'key' | 'pulse';
