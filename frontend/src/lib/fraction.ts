/**
 * Just enough exact fractions for the amount steppers ("1 1/2" + 1/2). The math that matters
 * happens on the server (docs/PLAN.md §8); this only steps and shows values.
 */
export interface Fraction {
  n: number;
  d: number;
}

function gcd(a: number, b: number): number {
  let [x, y] = [Math.abs(a), Math.abs(b)];
  while (y) [x, y] = [y, x % y];
  return x || 1;
}

function reduce(n: number, d: number): Fraction {
  const g = gcd(n, d);
  return d < 0 ? { n: -n / g, d: -d / g } : { n: n / g, d: d / g };
}

/** Reads "3/8", "2", "0.5" and "1 1/2". Anything else is null. */
export function parseFraction(text: string): Fraction | null {
  const value = text.trim();
  let match = /^(\d+)\s+(\d+)\/(\d+)$/.exec(value);
  if (match) {
    const [whole, n, d] = [Number(match[1]), Number(match[2]), Number(match[3])];
    return d ? reduce(whole * d + n, d) : null;
  }
  match = /^(\d+)\/(\d+)$/.exec(value);
  if (match) {
    const [n, d] = [Number(match[1]), Number(match[2])];
    return d ? reduce(n, d) : null;
  }
  match = /^(\d*)(?:\.(\d{1,6}))?$/.exec(value);
  if (match && value !== "" && value !== ".") {
    const digits = match[2] ?? "";
    const scale = 10 ** digits.length;
    return reduce(Number(match[1] ?? "0") * scale + Number(digits || "0"), scale);
  }
  return null;
}

export function add(a: Fraction, b: Fraction): Fraction {
  return reduce(a.n * b.d + b.n * a.d, a.d * b.d);
}

export function isPositive(a: Fraction): boolean {
  return a.n > 0;
}

/** The API's text form: "3/2". */
export function toText(a: Fraction): string {
  return a.d === 1 ? String(a.n) : `${String(a.n)}/${String(a.d)}`;
}

/** How people write it: "1 1/2". */
export function toMixed(a: Fraction): string {
  const whole = Math.trunc(a.n / a.d);
  const rest = a.n % a.d;
  if (rest === 0) return String(whole);
  return whole
    ? `${String(whole)} ${String(rest)}/${String(a.d)}`
    : `${String(rest)}/${String(a.d)}`;
}
