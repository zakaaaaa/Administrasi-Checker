'use client';

import { useEffect, useState } from 'react';
import type { Session } from '@supabase/supabase-js';
import { supabase } from '@/lib/supabaseClient';

export type ReviewerSession = {
  status: 'loading' | 'authenticated' | 'unauthenticated';
  session: Session | null;
  email: string | null;
};

export function useReviewerSession(): ReviewerSession {
  const [state, setState] = useState<ReviewerSession>({
    status: 'loading',
    session: null,
    email: null,
  });

  useEffect(() => {
    let mounted = true;

    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      const session = data.session;
      setState({
        status: session ? 'authenticated' : 'unauthenticated',
        session,
        email: session?.user.email ?? null,
      });
    });

    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!mounted) return;
      setState({
        status: session ? 'authenticated' : 'unauthenticated',
        session,
        email: session?.user.email ?? null,
      });
    });

    return () => {
      mounted = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  return state;
}
