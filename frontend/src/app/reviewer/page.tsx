'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ReviewerLoginScreen } from '@/features/reviewer/ReviewerLoginScreen';
import { useReviewerSession } from '@/features/reviewer/useReviewerSession';

export default function ReviewerLandingPage() {
  const router = useRouter();
  const session = useReviewerSession();

  useEffect(() => {
    if (session.status === 'authenticated') {
      router.replace('/reviewer/check');
    }
  }, [session.status, router]);

  if (session.status === 'loading') {
    return (
      <main className="relative flex min-h-[calc(100vh-4rem)] items-center justify-center px-4 py-10 sm:px-6">
        <p className="text-sm text-foreground-muted">Memeriksa sesi…</p>
      </main>
    );
  }
  if (session.status === 'authenticated') return null;

  return <ReviewerLoginScreen />;
}
