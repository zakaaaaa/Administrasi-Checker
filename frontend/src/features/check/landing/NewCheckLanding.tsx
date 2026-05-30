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
    <main className="relative mx-auto max-w-7xl px-4 pb-20 pt-6 sm:px-6 lg:pt-8">
      <CheckLandingDecor />

      <section className="grid gap-8 pt-8 lg:grid-cols-[minmax(0,1fr)_390px] lg:items-start lg:pt-12">
        <CheckLandingHero />
        <CheckLandingTokenForm
          token={token}
          onTokenChange={setToken}
          onSubmit={handleContinue}
        />
      </section>

      <section id="flow-section" className="mt-10">
        <CheckLandingFlowSection />
      </section>
    </main>
  );
}
