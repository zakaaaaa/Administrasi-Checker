import { Suspense } from 'react';
import { CheckFormView } from '@/features/check/CheckFormView';

export default function NewCheckFormPage() {
  return (
    <Suspense fallback={<FormPageFallback />}>
      <CheckFormView />
    </Suspense>
  );
}

function FormPageFallback() {
  return (
    <main className="relative mx-auto max-w-6xl px-4 pb-24 pt-8 sm:px-6">
      <p className="text-sm text-foreground-muted">Memuat form…</p>
    </main>
  );
}
