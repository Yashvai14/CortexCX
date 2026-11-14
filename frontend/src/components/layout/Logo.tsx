export function Logo({ size = 32, dark = false }: { size?: number; dark?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-label="CortexCX">
      <defs>
        <linearGradient id="lg-cx" x1="4" y1="4" x2="36" y2="36">
          <stop stopColor="#8b6cff" />
          <stop offset="1" stopColor="#19e3b6" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="12" fill={dark ? '#ffffff' : 'var(--fg)'} />
      <path
        d="M26 14.5A8 8 0 1 0 26 25.5"
        stroke="url(#lg-cx)"
        strokeWidth="3.4"
        strokeLinecap="round"
      />
      <circle cx="28.5" cy="20" r="2.4" fill="url(#lg-cx)" />
    </svg>
  );
}
