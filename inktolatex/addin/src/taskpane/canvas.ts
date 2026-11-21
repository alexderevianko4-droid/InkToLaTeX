/**
 * InkCanvas — pointer-event based drawing surface with undo, clear, and PNG export.
 */

const MAX_HISTORY = 50;
const CROP_PADDING = 20;

export class InkCanvas {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private drawing = false;
  private strokeColor = "#000000";
  private strokeWidth = 2.5;
  private history: ImageData[] = [];
  private dpr: number;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Cannot get 2D context from canvas");
    this.ctx = ctx;

    this.dpr = window.devicePixelRatio || 1;
    this.resizeToCSS();

    // Save the initial blank state
    this.pushHistory();

    this.canvas.addEventListener("pointerdown", this.onPointerDown);
    this.canvas.addEventListener("pointermove", this.onPointerMove);
    this.canvas.addEventListener("pointerup", this.onPointerUp);
    this.canvas.addEventListener("pointercancel", this.onPointerUp);

    // Re-scale when the container is resized (e.g. task pane resize)
    if (typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(() => this.resizeToCSS());
      ro.observe(this.canvas);
    }
  }

  /* ---------- public API ---------- */

  /** Set stroke width in CSS pixels. */
  setStrokeWidth(w: number): void {
    this.strokeWidth = w;
  }

  /** Set stroke colour. */
  setStrokeColor(c: string): void {
    this.strokeColor = c;
  }

  /** Clear the canvas and reset history. */
  clear(): void {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.history = [];
    this.pushHistory();
  }

  /** Undo the last stroke (restore previous snapshot). */
  undo(): void {
    if (this.history.length <= 1) return; // nothing to undo
    this.history.pop(); // remove current state
    const prev = this.history[this.history.length - 1];
    this.ctx.putImageData(prev, 0, 0);
  }

  /** Is the canvas visually empty? */
  isEmpty(): boolean {
    const { width, height } = this.canvas;
    const data = this.ctx.getImageData(0, 0, width, height).data;
    // Check if every pixel is fully transparent
    for (let i = 3; i < data.length; i += 4) {
      if (data[i] !== 0) return false;
    }
    return true;
  }

  /**
   * Export the drawing as a base64-encoded PNG (no data-URL prefix).
   * Returns `null` when the canvas is empty.
   * The image is cropped to the bounding box of the ink with 20 px padding
   * and placed on a white background.
   */
  toPNG(): string | null {
    if (this.isEmpty()) return null;

    const { width, height } = this.canvas;
    const imageData = this.ctx.getImageData(0, 0, width, height);
    const { data } = imageData;

    // --- find bounding box of non-transparent pixels ---
    let minX = width;
    let minY = height;
    let maxX = 0;
    let maxY = 0;

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4;
        if (data[idx + 3] !== 0) {
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
      }
    }

    // Apply padding and clamp
    minX = Math.max(0, minX - CROP_PADDING);
    minY = Math.max(0, minY - CROP_PADDING);
    maxX = Math.min(width - 1, maxX + CROP_PADDING);
    maxY = Math.min(height - 1, maxY + CROP_PADDING);

    const cropW = maxX - minX + 1;
    const cropH = maxY - minY + 1;

    // --- build output on a temp canvas ---
    const tmp = document.createElement("canvas");
    tmp.width = cropW;
    tmp.height = cropH;
    const tmpCtx = tmp.getContext("2d")!;

    // White background
    tmpCtx.fillStyle = "#ffffff";
    tmpCtx.fillRect(0, 0, cropW, cropH);

    // Draw cropped region
    tmpCtx.drawImage(this.canvas, minX, minY, cropW, cropH, 0, 0, cropW, cropH);

    const dataURL = tmp.toDataURL("image/png");
    // Strip the prefix "data:image/png;base64,"
    return dataURL.split(",")[1];
  }

  /* ---------- private helpers ---------- */

  /**
   * Resize the internal bitmap to match CSS size × devicePixelRatio
   * while keeping existing content.
   */
  private resizeToCSS(): void {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.dpr = dpr;

    const w = rect.width > 0 ? rect.width : (this.canvas.clientWidth || 350);
    const h = rect.height > 0 ? rect.height : (this.canvas.clientHeight || 300);
    const newW = Math.max(100, Math.round(w * dpr));
    const newH = Math.max(100, Math.round(h * dpr));

    if (this.canvas.width === newW && this.canvas.height === newH) return;

    // Preserve content
    let snapshot: ImageData | null = null;
    if (this.canvas.width > 0 && this.canvas.height > 0) {
      snapshot = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
    }

    this.canvas.width = newW;
    this.canvas.height = newH;
    this.ctx.scale(dpr, dpr);

    if (snapshot) {
      this.ctx.putImageData(snapshot, 0, 0);
    }
  }

  private pushHistory(): void {
    if (this.history.length >= MAX_HISTORY) {
      this.history.shift();
    }
    this.history.push(this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height));
  }

  private cssCoords(e: PointerEvent): { x: number; y: number } {
    const rect = this.canvas.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) * this.dpr,
      y: (e.clientY - rect.top) * this.dpr,
    };
  }

  /* ---------- pointer event handlers ---------- */

  private onPointerDown = (e: PointerEvent): void => {
    this.drawing = true;
    this.canvas.setPointerCapture(e.pointerId);

    const { x, y } = this.cssCoords(e);
    this.ctx.save();
    this.ctx.resetTransform(); // draw in raw pixel space
    this.ctx.beginPath();
    this.ctx.moveTo(x, y);
    this.ctx.strokeStyle = this.strokeColor;
    this.ctx.lineWidth = this.strokeWidth * this.dpr;
    this.ctx.lineCap = "round";
    this.ctx.lineJoin = "round";
  };

  private onPointerMove = (e: PointerEvent): void => {
    if (!this.drawing) return;
    const { x, y } = this.cssCoords(e);
    this.ctx.lineTo(x, y);
    this.ctx.stroke();
    this.ctx.beginPath();
    this.ctx.moveTo(x, y);
  };

  private onPointerUp = (_e: PointerEvent): void => {
    if (!this.drawing) return;
    this.drawing = false;
    this.ctx.restore();
    this.pushHistory();
  };
}
