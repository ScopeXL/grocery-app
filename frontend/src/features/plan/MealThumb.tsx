import { ProductImage } from "../../ui/ProductImage";
import type { DishRef } from "./types";

/** A planned meal's tile: the household's photo (croppable), else its first product photo. */
export function MealThumb({ dish }: { dish: DishRef }) {
  if (dish.photo_url) {
    return (
      <img src={dish.photo_url} alt="" className="size-16 shrink-0 rounded-tile object-cover" />
    );
  }
  return <ProductImage src={dish.item_images[0] ?? null} alt="" size={64} />;
}

/**
 * The Tonight card's picture: the household's photo in a wide crop (full size, not the
 * thumbnail), or a short strip of the meal's product photos, each whole.
 */
export function MealPicture({ dish }: { dish: DishRef }) {
  if (dish.photo_url) {
    return (
      <img
        src={dish.photo_url.replace(/\/thumb$/, "")}
        alt=""
        className="aspect-[2/1] max-h-72 w-full object-cover"
      />
    );
  }
  return (
    <div className="flex w-full flex-wrap items-center justify-center gap-2 bg-counter p-4">
      {dish.item_images.length > 0 ? (
        dish.item_images.map((src) => <ProductImage key={src} src={src} alt="" size={64} />)
      ) : (
        <ProductImage src={null} alt="" size={64} />
      )}
    </div>
  );
}
