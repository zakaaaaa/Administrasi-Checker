'use client';

import { useEffect, useRef } from 'react';

/**
 * Tambahkan class `reveal-in` ke elemen `[data-reveal]` saat masuk viewport.
 */
export function useRevealOnScroll() {
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    const revealAll = () => {
      document.querySelectorAll('[data-reveal]').forEach((el) => {
        el.classList.add('reveal-in');
      });
    };

    if (!('IntersectionObserver' in window)) {
      revealAll();
      return;
    }

    observerRef.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('reveal-in');
            observerRef.current?.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
    );

    document.querySelectorAll('[data-reveal]').forEach((el) => {
      observerRef.current?.observe(el);
    });

    const fallback = setTimeout(revealAll, 800);

    return () => {
      observerRef.current?.disconnect();
      clearTimeout(fallback);
    };
  }, []);
}
