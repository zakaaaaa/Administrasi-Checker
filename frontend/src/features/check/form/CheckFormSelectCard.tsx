export function CheckFormSelectCard({
  active,
  onClick,
  label,
  description,
  compact,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  description: string;
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative flex flex-col items-start rounded-2xl border px-4 text-left transition ${
        compact ? 'py-3' : 'py-3.5'
      } ${
        active
          ? 'border-brand-500 bg-brand-50 shadow-[0_0_0_3px_hsl(var(--brand-400)_/_0.18)]'
          : 'border-border bg-surface-elevated hover:border-brand-200 hover:bg-surface-sunken'
      }`}
    >
      <span className={`text-sm font-semibold ${active ? 'text-brand-700' : 'text-foreground'}`}>
        {label}
      </span>
      <span className="mt-0.5 text-sm text-foreground-muted">{description}</span>
      {active && (
        <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-brand-500 text-white">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-3 w-3"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </span>
      )}
    </button>
  );
}
