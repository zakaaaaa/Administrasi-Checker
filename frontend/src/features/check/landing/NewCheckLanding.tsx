'use client';

import type { FormEvent } from 'react';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useRevealOnScroll } from '@/hooks/useRevealOnScroll';
import { CheckLandingDecor } from './CheckLandingDecor';
import { CheckLandingFlowSection } from './CheckLandingFlowSection';
import { CheckLandingHero } from './CheckLandingHero';
import { CheckLandingTokenForm } from './CheckLandingTokenForm';

export function NewCheckLanding() {
  const [token, setToken] = useState('');
  const router = useRouter();
  useRevealOnScroll();

  function handleContinue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token.trim()) return;
    router.push(`/check/new/form?token=${encodeURIComponent(token.trim())}`);
  }

  return (
    <main className="relative mx-auto max-w-7xl px-4 pb-20 pt-10 sm:px-6">
      <CheckLandingDecor />
      <CheckLandingHero />

      <section id="flow-section" className="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
        <CheckLandingFlowSection />
        <CheckLandingTokenForm
          token={token}
          onTokenChange={setToken}
          onSubmit={handleContinue}
        />
      </section>
    </main>
  );
}
