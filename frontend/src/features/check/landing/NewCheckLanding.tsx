'use client';

import type { FormEvent } from 'react';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useRevealOnScroll } from '@/hooks/useRevealOnScroll';
import { CheckLandingTopNav } from './CheckLandingTopNav';
import { CheckLandingHero } from './CheckLandingHero';
import { CheckLandingResultPreview } from './CheckLandingResultPreview';
import { CheckLandingScope } from './CheckLandingScope';
import { CheckLandingBenefits } from './CheckLandingBenefits';
import { CheckLandingFlowSection } from './CheckLandingFlowSection';
import { CheckLandingFaq } from './CheckLandingFaq';
import { CheckLandingTokenForm } from './CheckLandingTokenForm';
import { CheckLandingFooter } from './CheckLandingFooter';

export function NewCheckLanding() {
  const [token, setToken] = useState('');
  const router = useRouter();
  useRevealOnScroll();

  function scrollToStart() {
    document.getElementById('mulai')?.scrollIntoView({ behavior: 'smooth' });
  }

  function handleContinue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token.trim()) return;
    router.push(`/check/new/form?token=${encodeURIComponent(token.trim())}`);
  }

  return (
    <div className="relative min-h-screen">
      <CheckLandingTopNav onStart={scrollToStart} />

      <main>
        <CheckLandingHero onStart={scrollToStart} />
        <CheckLandingResultPreview />
        <CheckLandingScope />
        <CheckLandingBenefits />
        <CheckLandingFlowSection />
        <CheckLandingFaq />
        <CheckLandingTokenForm
          token={token}
          onTokenChange={setToken}
          onSubmit={handleContinue}
        />
      </main>

      <CheckLandingFooter />
    </div>
  );
}
