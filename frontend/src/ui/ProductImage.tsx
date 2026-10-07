import { ShoppingBasket } from "lucide-react";
import { useState } from "react";

import { forgetImage } from "../lib/images";

/**
 * The only way a Kroger product photo is drawn (CLAUDE.md rule 3; Kroger's terms): never
 * cropped (`object-contain`), never filtered, never covered. Badges and prices sit beside it,
 * not on it. The tile is white in both themes, like a label. A missing or broken photo shows a
 * quiet basket instead.
 */
const SIZES = {
  40: "size-10",
  48: "size-12",
  64: "size-16",
  96: "size-24",
} as const;

export function ProductImage({
  src,
  alt,
  size = 64,
}: {
  src: string | null | undefined;
  alt: string;
  size?: keyof typeof SIZES;
}) {
  const [failed, setFailed] = useState(false);
  return (
    <div
      className={`${SIZES[size]} flex shrink-0 items-center justify-center rounded-tile border border-rule bg-photo-tile p-1`}
    >
      {src && !failed ? (
        <img
          src={src}
          alt={alt}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          className="size-full object-contain"
          onError={() => {
            setFailed(true);
            void forgetImage(src); // a broken copy saved for the store mustn't stick around
          }}
        />
      ) : (
        <ShoppingBasket aria-hidden="true" className="size-1/2 text-ink-soft" />
      )}
    </div>
  );
}
