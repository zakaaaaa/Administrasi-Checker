/**
 * Dekorasi background global (orbs + grain) — dipisah dari `layout.tsx` agar ringkas.
 */
export function RootShellOrbs() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="orb orb-brand h-[520px] w-[520px] left-[-180px] top-[-160px] animate-float-slow" />
      <div className="orb orb-accent h-[440px] w-[440px] right-[-140px] top-[20%] animate-float-slower" />
      <div className="orb orb-warm h-[380px] w-[380px] left-[30%] bottom-[-120px] animate-float-slow" />
      <div className="grain" />
    </div>
  );
}
