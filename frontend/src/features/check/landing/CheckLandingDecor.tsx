export function CheckLandingDecor() {
  return (
    <>
      <div
        aria-hidden
        className="check-landing-dot-pattern pointer-events-none absolute inset-0 -z-10"
      />
      <div
        aria-hidden
        className="check-landing-blob -z-10 left-[-80px] top-[40px] h-72 w-72 bg-brand-300/35"
      />
      <div
        aria-hidden
        className="check-landing-blob -z-10 right-[-60px] top-[200px] h-80 w-80 bg-amber-200/35"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute left-4 top-6 flex flex-col gap-3"
      >
        <span className="block h-3 w-3 rounded-full bg-brand-400/80" />
        <span className="ml-6 block h-2 w-2 rounded-full bg-amber-300/70" />
        <span className="block h-1.5 w-1.5 rounded-full bg-brand-300/60" />
      </div>
      <div
        aria-hidden
        className="pointer-events-none absolute bottom-10 right-8 flex flex-col items-end gap-3"
      >
        <span className="block h-2 w-2 rounded-full bg-brand-300/70" />
        <span className="mr-6 block h-3 w-3 rounded-full bg-amber-300/80" />
        <span className="block h-1.5 w-1.5 rounded-full bg-brand-300/60" />
      </div>
    </>
  );
}
