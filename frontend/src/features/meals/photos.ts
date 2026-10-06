/**
 * Meal photos: shrunk on the phone first (cellular uploads in a store are slow), then the
 * server re-encodes them as WebP without metadata (ADR 0020).
 */
import { ApiError } from "../../api/client";

const MAX_SIDE = 1600;

export interface UploadedPhoto {
  id: string;
  width: number;
  height: number;
}

export async function uploadPhoto(file: File): Promise<UploadedPhoto> {
  let body: Blob = file;
  try {
    body = await shrink(file);
  } catch {
    // The browser couldn't decode it here; let the server try the original.
  }
  let response: Response;
  try {
    response = await fetch("/api/photos", {
      method: "POST",
      body,
      credentials: "same-origin",
      headers: { "Content-Type": body.type || "image/jpeg", "X-Dinner-Bell": "1" },
    });
  } catch {
    throw new ApiError(0, "offline", "Not saved — you're offline. Try again when you have signal.");
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (payload as { error?: { code?: string; message?: string } } | null)?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "error",
      error?.message ?? "That photo couldn't be saved. Try again.",
    );
  }
  return payload as UploadedPhoto;
}

async function shrink(file: File): Promise<Blob> {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const context = canvas.getContext("2d");
  if (!context) throw new Error("no canvas");
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) resolve(blob);
        else reject(new Error("couldn't encode"));
      },
      "image/jpeg",
      0.85,
    );
  });
}
