/**
 * The two bits of motion that need a script (styles/motion.css, ADR 0027). Neither animates
 * anything itself: one sets an attribute, the other gives a changing key.
 */
import { useState } from "react";

/**
 * A ref for a list whose later rows ease in. It marks the list `data-arrivals` one frame after
 * the list appears, so the rows it opened with stay still and only rows added after do.
 */
export function arrivals(list: HTMLElement | null): (() => void) | undefined {
  if (!list) return undefined;
  const frame = requestAnimationFrame(() => {
    list.dataset.arrivals = "";
  });
  return () => {
    cancelAnimationFrame(frame);
  };
}

/**
 * How many times `value` has changed since the first render. As a key it re-plays a "changed"
 * animation (a total that pops); 0 means it hasn't changed yet, so nothing plays on first paint.
 * Arriving from nothing (null or undefined, still loading) isn't a change either.
 */
export function useChangeCount(value: unknown): number {
  const [seen, setSeen] = useState({ value, count: 0 });
  if (!Object.is(seen.value, value)) {
    const arriving = seen.value === null || seen.value === undefined;
    const next = { value, count: arriving ? seen.count : seen.count + 1 };
    setSeen(next);
    return next.count;
  }
  return seen.count;
}
