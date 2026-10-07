/**
 * The signature moment (UX §7.6): a slightly wobbly marker stroke through a checked item's
 * name, drawn left to right in 250 ms in the checker's color. Each row's wobble comes from its
 * id, so it never changes between renders. It sits over the text, never over a photo.
 */
function wobble(seed: string): string {
  let hash = 2166136261;
  for (const char of seed) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  const y = (n: number) => (5 + (((hash >>> (n * 3)) & 7) - 3.5) * 0.4).toFixed(2);
  return `M1 ${y(0)} C 25 ${y(1)}, 50 ${y(2)}, 75 ${y(3)} S 95 ${y(4)}, 99 ${y(5)}`;
}

export function MarkerStrike({
  seed,
  color,
  animate,
}: {
  seed: string;
  color: string;
  animate: boolean;
}) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 100 10"
      preserveAspectRatio="none"
      className={`marker-${color} pointer-events-none absolute inset-x-0 top-1/2 h-4 w-full -translate-y-1/2 overflow-visible text-[var(--marker)]`}
    >
      <path
        d={wobble(seed)}
        fill="none"
        stroke="currentColor"
        strokeWidth={3}
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        pathLength={1}
        className={animate ? "marker-draw" : undefined}
      />
    </svg>
  );
}
