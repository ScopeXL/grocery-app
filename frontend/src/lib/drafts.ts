/**
 * Drafts survive closing the app mid-task (docs/UX.md §1). They live on this phone only, and a
 * private window or full storage simply means no draft, never an error.
 */
const PREFIX = "dinnerbell.draft.";

/** The saved value as stored: callers check its shape, since an old app version may have written it. */
export function loadDraft(key: string): unknown {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    return raw === null ? null : (JSON.parse(raw) as unknown);
  } catch {
    return null;
  }
}

export function saveDraft(key: string, value: unknown): void {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    // No room or no storage: the draft just isn't kept.
  }
}

export function clearDraft(key: string): void {
  try {
    localStorage.removeItem(PREFIX + key);
  } catch {
    // Nothing to clear.
  }
}
