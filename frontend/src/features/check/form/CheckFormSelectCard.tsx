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
          ? 'border-brand-500 bg-brand-50/80 shadow-[0_0_0_3px_rgba(249,115,22,0.12)]'
          : 'border-white/60 bg-white/40 hover:border-brand-200 hover:bg-white/65'
      }`}
    >
      <span className={`text-sm font-semibold ${active ? 'text-brand-700' : 'text-foreground'}`}>
        {label}
      </span>
      <span className="mt-0.5 text-xs text-foreground-muted">{description}</span>
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
