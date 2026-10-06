/** The Dinner Bell mark: a bell drawn with a marker stroke (docs/UX.md §7.7).
 * Keep the paths in sync with scripts/build-icons.mjs. */
export function BellMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 512 512" className={className} role="img" aria-label="Dinner Bell">
      <rect width="512" height="512" rx="112" className="fill-lemon" />
      <g
        className="stroke-on-lemon"
        fill="none"
        strokeWidth="30"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M256 102v40" />
        <path d="M148 330c24-22 26-52 26-86 0-56 36-98 82-98s82 42 82 98c0 34 2 64 26 86" />
        <path d="M122 336c44-14 224-14 268 0" />
        <path d="M230 370a26 26 0 0 0 52 0" />
      </g>
    </svg>
  );
}
