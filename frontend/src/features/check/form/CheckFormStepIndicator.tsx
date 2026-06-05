export function CheckFormStepDot({
  state,
  label,
}: {
  state: 'done' | 'active' | 'todo';
  label: string;
}) {
  const dot =
    state === 'done'
      ? 'bg-brand-500 text-white'
      : state === 'active'
        ? 'bg-white text-brand-600 ring-2 ring-brand-500'
        : 'bg-surface-sunken text-foreground-subtle ring-1 ring-border';
  const text = state === 'todo' ? 'text-foreground-subtle' : 'text-foreground';
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${dot}`}
      >
        {state === 'done' ? (
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-2.5 w-2.5"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
        ) : (
          ''
        )}
      </span>
      <span className={`text-xs font-medium ${text}`}>{label}</span>
    </div>
  );
}

export function CheckFormStepBar({ state }: { state: 'active' | 'todo' }) {
  return (
    <span
      className={`h-0.5 max-w-[60px] flex-1 rounded-full ${state === 'active' ? 'bg-brand-300' : 'bg-border'}`}
    />
  );
}
