export type ModuleResult = {
  status?: string;
  messages?: { level: string; text: string }[];
  [key: string]: unknown;
};

export type ModuleKey =
  | 'structure'
  | 'physical_sheet'
  | 'format'
  | 'page_numbering'
  | 'budget'
  | 'reference'
  | 'ai_content'
  | 'ai_format';

export type CheckResults = {
  submission_id: string;
  status: string;
  overall_status: string;
  // Partial: skema tertentu (mis. PKM-AI) hanya kirim subset modul.
  results: Partial<Record<ModuleKey, ModuleResult>>;
};
