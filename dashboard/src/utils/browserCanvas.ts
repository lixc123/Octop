export interface CanvasPoint {
  x: number;
  y: number;
}

/** Map a screen pointer position to canvas pixel coordinates. */
export function getCanvasCoords(
  canvas: HTMLCanvasElement | null,
  e: { clientX: number; clientY: number },
): CanvasPoint {
  if (!canvas) return { x: 0, y: 0 };
  const rect = canvas.getBoundingClientRect();
  const sourceWidth = canvas.width;
  const sourceHeight = canvas.height;
  if (
    rect.width === 0 ||
    rect.height === 0 ||
    sourceWidth === 0 ||
    sourceHeight === 0
  ) {
    return { x: 0, y: 0 };
  }

  // BrowserViewer uses object-fit: contain. The DOM rect includes the
  // letterbox bars, so map through the actual fitted bitmap instead of
  // stretching pointer coordinates across the whole element.
  const fitScale = Math.min(
    rect.width / sourceWidth,
    rect.height / sourceHeight,
  );
  const contentWidth = sourceWidth * fitScale;
  const contentHeight = sourceHeight * fitScale;
  const offsetX = (rect.width - contentWidth) / 2;
  const offsetY = (rect.height - contentHeight) / 2;
  const clamp = (value: number, max: number) =>
    Math.max(0, Math.min(max, value));

  return {
    x: Math.round(
      clamp((e.clientX - rect.left - offsetX) / fitScale, sourceWidth),
    ),
    y: Math.round(
      clamp((e.clientY - rect.top - offsetY) / fitScale, sourceHeight),
    ),
  };
}

/** Paint a JPEG base64 frame onto a canvas (WebSocket stream). */
export function paintBase64JpegToCanvas(
  canvas: HTMLCanvasElement | null,
  base64Data: string,
): void {
  if (!canvas) return;
  const img = new Image();
  img.onload = () => {
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    if (canvas.width !== img.width || canvas.height !== img.height) {
      canvas.width = img.width;
      canvas.height = img.height;
    }
    ctx.imageSmoothingEnabled = true;
    if ("imageSmoothingQuality" in ctx) {
      ctx.imageSmoothingQuality = "high";
    }
    ctx.drawImage(img, 0, 0);
  };
  img.src = `data:image/jpeg;base64,${base64Data}`;
}

/** Paint a screenshot blob onto a canvas (HTTP polling). */
export async function paintBlobToCanvas(
  canvas: HTMLCanvasElement | null,
  blob: Blob,
): Promise<boolean> {
  if (!canvas) return false;
  const bitmap = await createImageBitmap(blob);
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0);
  bitmap.close();
  return true;
}

export function clearCanvas(canvas: HTMLCanvasElement | null): void {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
}
