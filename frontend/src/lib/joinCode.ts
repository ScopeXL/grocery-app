/** Add-a-phone codes as people type them (backend: auth/join.py). */
export const CODE_LENGTH = 8;
// The alphabet has no look-alikes: no 0, O, 1, I or L.
const CODE = /^[ABCDEFGHJKMNPQRSTUVWXYZ2-9]{8}$/;

/** Any case, spaces and dashes ignored; null when it can't be a code. */
export function normalizeCode(text: string): string | null {
  const code = text.replace(/[\s-]/g, "").toUpperCase();
  return CODE.test(code) ? code : null;
}

/** "4 F 7 K 9 Q X 2": how a screen reader should say it, a character at a time. */
export function spokenCode(code: string): string {
  return code.replace(/(.)(?=.)/g, "$1 ");
}

/** "4F7K 9QX2": two groups of four, easier to read out and type. */
export function displayCode(code: string): string {
  return `${code.slice(0, 4)} ${code.slice(4)}`;
}

/** The code a QR link carries: `/join#4F7K9QX2`. */
export function codeFromHash(hash: string): string | null {
  return normalizeCode(decodeURIComponent(hash.replace(/^#/, "")));
}
