/**
 * A saved list as plain text, for anyone without the app (UX §4.15 "Share as text"): sections
 * in walking order, one line per item, nothing that only makes sense on screen.
 */
import type { components } from "../api/schema";

type TripItem = components["schemas"]["TripItemOut"];

export function tripText(title: string, items: readonly TripItem[]): string {
  const live = items.filter((item) => !item.removed);
  const sorted = [...live].sort(
    (a, b) =>
      a.section_order - b.section_order ||
      a.bay - b.bay ||
      a.name.localeCompare(b.name) ||
      a.id.localeCompare(b.id),
  );
  const lines = [title];
  let section: string | null = null;
  for (const item of sorted) {
    const label = item.section_label ?? "Other";
    if (label !== section) {
      lines.push("", label);
      section = label;
    }
    const mark = item.state === "done" ? "✓ " : item.state === "missed" ? "✗ " : "";
    lines.push(`- ${mark}${item.name}: ${item.qty_text}`);
  }
  return lines.join("\n");
}

/** The phone's share sheet when there is one; otherwise the clipboard. Says which it used. */
export async function shareText(
  title: string,
  text: string,
): Promise<"shared" | "copied" | "none"> {
  if (typeof navigator.share === "function") {
    try {
      await navigator.share({ title, text });
      return "shared";
    } catch {
      return "none"; // cancelled
    }
  }
  try {
    await navigator.clipboard.writeText(text);
    return "copied";
  } catch {
    return "none";
  }
}
