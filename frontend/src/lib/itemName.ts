/**
 * What an item is called (docs/UX.md §4.9). Item names are the household's own words, never
 * Kroger's description (ADR 0016). When someone picks a store product before finishing a word,
 * only that last word is finished, from the product's name: "Shredd" becomes "Shredded".
 */
const NAME_MAX = 80;

/** Trimmed, single spaces, a capital first letter. */
export function tidyName(text: string): string {
  const trimmed = text.trim().replace(/\s+/g, " ");
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
}

/** Case- and accent-blind, so "jalapen" finds "Jalapeño". */
function fold(word: string): string {
  return word.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

/**
 * The name to suggest for a picked product: what was typed, with its last word finished when
 * it's the start of a word in the product's name. A trailing space means the word was done.
 */
export function suggestItemName(typed: string, description: string): string {
  const words = typed.trim().split(/\s+/).filter(Boolean);
  const last = words.at(-1);
  if (last !== undefined && !/\s$/.test(typed)) {
    const partial = fold(last);
    const match = (description.match(/[\p{L}\p{N}][\p{L}\p{N}'’-]*/gu) ?? []).find((word) =>
      fold(word).startsWith(partial),
    );
    if (match) words[words.length - 1] = match.toLowerCase();
  }
  return tidyName(words.join(" ")).slice(0, NAME_MAX);
}
