/**
 * Keep BELL in sync with src/ui/BellMark.tsx.
 * Rasterizes the Dinner Bell mark into the PNG icons the PWA manifest and iOS need.
 * Run with `pnpm icons` after changing the mark; the PNGs are committed.
 */
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const LEMON = "#ffdb3d";
const INK = "#2b1d30";
const BELL = `
  <g fill="none" stroke="${INK}" stroke-width="30" stroke-linecap="round" stroke-linejoin="round">
    <path d="M256 102v40" />
    <path d="M148 330c24-22 26-52 26-86 0-56 36-98 82-98s82 42 82 98c0 34 2 64 26 86" />
    <path d="M122 336c44-14 224-14 268 0" />
    <path d="M230 370a26 26 0 0 0 52 0" />
  </g>`;

/** rounded: transparent corners (purpose "any"); scale < 1 keeps the bell in the safe zone. */
function svg({ rounded, scale }) {
  const offset = (512 - 512 * scale) / 2;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <rect width="512" height="512" ${rounded ? 'rx="112"' : ""} fill="${LEMON}" />
  <g transform="translate(${offset} ${offset}) scale(${scale})">${BELL}</g>
</svg>`;
}

const publicDir = fileURLToPath(new URL("../public/", import.meta.url));
writeFileSync(`${publicDir}favicon.svg`, svg({ rounded: true, scale: 1 }) + "\n");

const targets = [
  { file: "icons/icon-192.png", size: 192, rounded: true, scale: 1 },
  { file: "icons/icon-512.png", size: 512, rounded: true, scale: 1 },
  { file: "icons/icon-maskable-512.png", size: 512, rounded: false, scale: 0.8 },
  { file: "apple-touch-icon.png", size: 180, rounded: false, scale: 0.9 },
];

const browser = await chromium.launch();
const page = await browser.newPage();
for (const target of targets) {
  await page.setViewportSize({ width: target.size, height: target.size });
  const markup = svg(target).replace(
    'width="512" height="512"',
    `width="${target.size}" height="${target.size}"`,
  );
  await page.setContent(`<html><body style="margin:0">${markup}</body></html>`);
  await page.screenshot({ path: `${publicDir}${target.file}`, omitBackground: target.rounded });
  console.log(`wrote public/${target.file}`);
}
await browser.close();
