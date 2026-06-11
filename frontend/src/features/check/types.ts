export type ModuleResult = {
  status?: string;
  messages?: { level: string; text: string }[];
  [key: string]: unknown;
};

export type CheckResults = {
  submission_id: string;
  status: string;
  overall_status: string;
  results: {
    structure: ModuleResult;
    physical_sheet: ModuleResult;
    format: ModuleResult;
    page_numbering: ModuleResult;
    budget: ModuleResult;
    reference: ModuleResult;
    ai_front_matter?: ModuleResult;
    luaran?: ModuleResult;
    lampiran?: ModuleResult;
    surat_pernyataan?: ModuleResult;
    biodata_date?: ModuleResult;
    signature_crop?: ModuleResult;
    schedule?: ModuleResult;
    similarity?: ModuleResult;
  };
};
