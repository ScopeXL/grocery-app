/** What kind of device and display mode we're running in (docs/PLAN.md §9.6). */

export function isIOS(userAgent = navigator.userAgent, touchPoints = navigator.maxTouchPoints) {
  // iPadOS reports itself as a Mac, so also check for a touch screen.
  const appleMobile = ["iPhone", "iPad", "iPod"].some((name) => userAgent.includes(name));
  return appleMobile || (userAgent.includes("Macintosh") && touchPoints > 1);
}

export function isAndroid(userAgent = navigator.userAgent) {
  return userAgent.includes("Android");
}

export function isStandalone(): boolean {
  const iosStandalone = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return iosStandalone || window.matchMedia("(display-mode: standalone)").matches;
}

const SAFARI_SKIP_KEY = "db.install-guide-skipped";

/** On an iPhone in a normal Safari tab, the install guide comes before signing in. */
export function shouldShowInstallFirst(): boolean {
  if (!isIOS() || isStandalone()) return false;
  try {
    return localStorage.getItem(SAFARI_SKIP_KEY) !== "1";
  } catch {
    return true;
  }
}

export function skipInstallGuide(): void {
  try {
    localStorage.setItem(SAFARI_SKIP_KEY, "1");
  } catch {
    // storage unavailable (private mode): the guide will simply show again next time
  }
}
