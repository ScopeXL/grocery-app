/**
 * Server clock offset, estimated from the X-Server-Time-Ms header on API responses.
 * Keeps the lowest-latency of the last 8 samples (docs/PLAN.md §9.2). Offline trip ops (M3)
 * use it to stamp actions with corrected, strictly increasing times.
 */

interface Sample {
  offset: number;
  roundTrip: number;
}

const samples: Sample[] = [];
const MAX_SAMPLES = 8;
let lastIssued = 0;

export function recordClockSample(sentAt: number, receivedAt: number, serverTime: number): void {
  const roundTrip = receivedAt - sentAt;
  if (!Number.isFinite(serverTime) || roundTrip < 0) return;
  samples.push({ offset: serverTime - (sentAt + receivedAt) / 2, roundTrip });
  if (samples.length > MAX_SAMPLES) samples.shift();
}

export function clockOffset(): number {
  let best: Sample | undefined;
  for (const sample of samples) {
    if (!best || sample.roundTrip < best.roundTrip) best = sample;
  }
  return best ? Math.round(best.offset) : 0;
}

/** Corrected time that never repeats or goes backwards on this device. */
export function nextTimestamp(now = Date.now()): number {
  lastIssued = Math.max(now + clockOffset(), lastIssued + 1);
  return lastIssued;
}

export function resetClockForTests(): void {
  samples.length = 0;
  lastIssued = 0;
}
