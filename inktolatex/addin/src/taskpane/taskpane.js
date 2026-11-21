/**
 * InkToLaTeX — Task Pane Client Bundle (ES6)
 *
 * Implements:
 * 1. InkCanvas (HTML5 Canvas with pointer events, high-DPI scaling, undo stack, cropping)
 * 2. API client (/recognize, /to-ooxml)
 * 3. KaTeX live math preview
 * 4. Word insertion (insertText, insertOoxml, with clipboard fallback)
 */

(function () {
  "use strict";

  const API_BASE = "http://localhost:8000";
  const TIMEOUT_MS = 30000;
  const MAX_HISTORY = 50;
  const CROP_PADDING = 20;

  /* =========================================================================
   * 1. InkCanvas
   * ========================================================================= */
  class InkCanvas {
    constructor(canvas) {
      this.canvas = canvas;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Cannot get 2D context from canvas");
      this.ctx = ctx;

      this.drawing = false;
      this.strokeColor = "#000000";
      this.strokeWidth = 2.5;
      this.history = [];
      this.dpr = window.devicePixelRatio || 1;

      this.resizeToCSS();
      this.pushHistory();

      this.canvas.addEventListener("pointerdown", this.onPointerDown.bind(this));
      this.canvas.addEventListener("pointermove", this.onPointerMove.bind(this));
      this.canvas.addEventListener("pointerup", this.onPointerUp.bind(this));
      this.canvas.addEventListener("pointercancel", this.onPointerUp.bind(this));

      if (typeof ResizeObserver !== "undefined") {
        const ro = new ResizeObserver(() => this.resizeToCSS());
        ro.observe(this.canvas);
      }
    }

    setStrokeWidth(w) {
      this.strokeWidth = w;
    }

    setStrokeColor(c) {
      this.strokeColor = c;
    }

    clear() {
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      this.history = [];
      this.pushHistory();
    }

    undo() {
      if (this.history.length <= 1) return;
      this.history.pop();
      const prev = this.history[this.history.length - 1];
      this.ctx.putImageData(prev, 0, 0);
    }

    isEmpty() {
      const { width, height } = this.canvas;
      if (width === 0 || height === 0) return true;
      const data = this.ctx.getImageData(0, 0, width, height).data;
      for (let i = 3; i < data.length; i += 4) {
        if (data[i] !== 0) return false;
      }
      return true;
    }

    toPNG() {
      if (this.isEmpty()) return null;

      const { width, height } = this.canvas;
      const imageData = this.ctx.getImageData(0, 0, width, height);
      const { data } = imageData;

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

      minX = Math.max(0, minX - CROP_PADDING);
      minY = Math.max(0, minY - CROP_PADDING);
      maxX = Math.min(width - 1, maxX + CROP_PADDING);
      maxY = Math.min(height - 1, maxY + CROP_PADDING);

      const cropW = maxX - minX + 1;
      const cropH = maxY - minY + 1;

      const tmp = document.createElement("canvas");
      tmp.width = cropW;
      tmp.height = cropH;
      const tmpCtx = tmp.getContext("2d");

      // White background
      tmpCtx.fillStyle = "#ffffff";
      tmpCtx.fillRect(0, 0, cropW, cropH);
      tmpCtx.drawImage(this.canvas, minX, minY, cropW, cropH, 0, 0, cropW, cropH);

      const dataURL = tmp.toDataURL("image/png");
      return dataURL.split(",")[1];
    }

    resizeToCSS() {
      const rect = this.canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      this.dpr = dpr;

      const w = rect.width > 0 ? rect.width : (this.canvas.clientWidth || 350);
      const h = rect.height > 0 ? rect.height : (this.canvas.clientHeight || 300);
      const newW = Math.max(100, Math.round(w * dpr));
      const newH = Math.max(100, Math.round(h * dpr));

      if (this.canvas.width === newW && this.canvas.height === newH) return;

      let snapshot = null;
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

    pushHistory() {
      if (this.history.length >= MAX_HISTORY) {
        this.history.shift();
      }
      this.history.push(this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height));
    }

    cssCoords(e) {
      const rect = this.canvas.getBoundingClientRect();
      return {
        x: (e.clientX - rect.left) * this.dpr,
        y: (e.clientY - rect.top) * this.dpr,
      };
    }

    onPointerDown(e) {
      this.drawing = true;
      if (this.canvas.setPointerCapture) {
        this.canvas.setPointerCapture(e.pointerId);
      }
      const { x, y } = this.cssCoords(e);
      this.ctx.save();
      this.ctx.resetTransform();
      this.ctx.beginPath();
      this.ctx.moveTo(x, y);
      this.ctx.strokeStyle = this.strokeColor;
      this.ctx.lineWidth = this.strokeWidth * this.dpr;
      this.ctx.lineCap = "round";
      this.ctx.lineJoin = "round";
    }

    onPointerMove(e) {
      if (!this.drawing) return;
      const { x, y } = this.cssCoords(e);
      this.ctx.lineTo(x, y);
      this.ctx.stroke();
      this.ctx.beginPath();
      this.ctx.moveTo(x, y);
    }

    onPointerUp(e) {
      if (!this.drawing) return;
      this.drawing = false;
      this.ctx.restore();
      this.pushHistory();
    }
  }

  /* =========================================================================
   * 2. API Client
   * ========================================================================= */
  async function recognize(pngBase64) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
      const response = await fetch(`${API_BASE}/recognize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: pngBase64 }),
        signal: controller.signal,
      });

      if (!response.ok) {
        let detail = "";
        try {
          const body = await response.json();
          detail = body.detail || body.message || JSON.stringify(body);
        } catch (_) {
          detail = await response.text().catch(() => "");
        }
        throw new Error(
          `Сервер повернув помилку ${response.status}${detail ? ": " + detail : ""}`
        );
      }

      const data = await response.json();
      if (typeof data.result !== "string") {
        throw new Error("Неочікуваний формат відповіді від сервера.");
      }
      return data.result;
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new Error("Час очікування відповіді від сервера вичерпано (30 с).");
      }
      if (err instanceof TypeError && (err.message.includes("fetch") || err.message.includes("network"))) {
        throw new Error(
          `Не вдалося з'єднатися з сервером (${API_BASE}). Переконайтеся, що бекенд запущено.`
        );
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  async function convertToOoxml(text) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
      const response = await fetch(`${API_BASE}/to-ooxml`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      });

      if (!response.ok) {
        let detail = "";
        try {
          const body = await response.json();
          detail = body.detail || body.message || JSON.stringify(body);
        } catch (_) {
          detail = await response.text().catch(() => "");
        }
        throw new Error(`Помилка конвертації в OOXML: ${detail || response.statusText}`);
      }

      const data = await response.json();
      if (typeof data.ooxml !== "string") {
        throw new Error("Неочікуваний формат OOXML від сервера.");
      }
      return data.ooxml;
    } finally {
      clearTimeout(timer);
    }
  }

  /* =========================================================================
   * 3. Word Insertion Helpers
   * ========================================================================= */
  async function insertText(text) {
    if (typeof Word !== "undefined" && Word.run) {
      try {
        await Word.run(async (context) => {
          const selection = context.document.getSelection();
          selection.insertText(text, Word.InsertLocation.replace);
          await context.sync();
        });
        return;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        throw new Error(`Помилка вставки тексту в документ Word: ${msg}`);
      }
    }

    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    throw new Error("Word не виявлено і буфер обміну недоступний.");
  }

  async function insertAsFormula(text) {
    if (typeof Word !== "undefined" && Word.run) {
      try {
        const ooxml = await convertToOoxml(text);
        await Word.run(async (context) => {
          const selection = context.document.getSelection();
          selection.insertOoxml(ooxml, Word.InsertLocation.replace);
          await context.sync();
        });
        return;
      } catch (err) {
        console.warn("Falling back to plain text insertion in Word:", err);
        await insertText(text);
        return;
      }
    }

    await insertText(text);
  }

  /* =========================================================================
   * 4. KaTeX Preview Rendering
   * ========================================================================= */
  function escapeHTML(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function safeKaTeX(tex, displayMode) {
    if (typeof katex === "undefined") {
      return `<code>${escapeHTML(tex)}</code>`;
    }
    try {
      return katex.renderToString(tex, {
        displayMode,
        throwOnError: false,
        output: "html",
      });
    } catch (_) {
      return `<span style="color:#d83b01" title="KaTeX error">${escapeHTML(tex)}</span>`;
    }
  }

  function renderPreview(text) {
    if (!text.trim()) return "";

    const segments = [];
    const displayRe = /\$\$([\s\S]+?)\$\$/g;
    let match;

    while ((match = displayRe.exec(text)) !== null) {
      segments.push({
        start: match.index,
        end: match.index + match[0].length,
        html: safeKaTeX(match[1], true),
      });
    }

    const inlineRe = /(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)/g;
    while ((match = inlineRe.exec(text)) !== null) {
      const overlaps = segments.some(
        (s) => match.index < s.end && match.index + match[0].length > s.start
      );
      if (!overlaps) {
        segments.push({
          start: match.index,
          end: match.index + match[0].length,
          html: safeKaTeX(match[1], false),
        });
      }
    }

    segments.sort((a, b) => a.start - b.start);

    const parts = [];
    let last = 0;
    for (const seg of segments) {
      if (seg.start > last) {
        parts.push(escapeHTML(text.slice(last, seg.start)));
      }
      parts.push(seg.html);
      last = seg.end;
    }
    if (last < text.length) {
      parts.push(escapeHTML(text.slice(last)));
    }

    return parts.join("");
  }

  /* =========================================================================
   * 5. UI Controller & Bootstrap
   * ========================================================================= */
  function $(id) {
    const el = document.getElementById(id);
    if (!el) throw new Error(`Element #${id} not found`);
    return el;
  }

  function setStatus(msg, type = "") {
    const el = $("status");
    el.textContent = msg;
    el.className = type;
  }

  function init() {
    const canvasEl = document.getElementById("ink-canvas");
    if (!canvasEl) return;

    const inkCanvas = new InkCanvas(canvasEl);

    const clearBtn = $("clear-btn");
    const undoBtn = $("undo-btn");
    const recognizeBtn = $("recognize-btn");
    const insertBtn = $("insert-btn");
    const insertFormulaBtn = $("insert-formula-btn");
    const resultText = $("result-text");
    const preview = $("preview");

    clearBtn.addEventListener("click", () => {
      inkCanvas.clear();
      setStatus("");
    });

    undoBtn.addEventListener("click", () => {
      inkCanvas.undo();
    });

    recognizeBtn.addEventListener("click", async () => {
      const png = inkCanvas.toPNG();
      if (!png) {
        setStatus("Малюнок порожній — намалюйте щось спершу.", "error");
        return;
      }

      recognizeBtn.disabled = true;
      const originalHTML = recognizeBtn.innerHTML;
      recognizeBtn.innerHTML = '<span class="spinner"></span>Розпізнавання…';
      setStatus("");

      try {
        const result = await recognize(png);
        resultText.value = result;
        preview.innerHTML = renderPreview(result);
        setStatus("Розпізнано успішно!", "success");
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setStatus(msg, "error");
      } finally {
        recognizeBtn.disabled = false;
        recognizeBtn.innerHTML = originalHTML;
      }
    });

    resultText.addEventListener("input", () => {
      preview.innerHTML = renderPreview(resultText.value);
    });

    insertBtn.addEventListener("click", async () => {
      const text = resultText.value.trim();
      if (!text) {
        setStatus("Нема тексту для вставки.", "error");
        return;
      }
      try {
        await insertText(text);
        if (typeof Word !== "undefined" && Word.run) {
          setStatus("Вставлено в документ ✓", "success");
        } else {
          setStatus("Скопійовано в буфер обміну (Word не активний) ✓", "success");
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setStatus(msg, "error");
      }
    });

    insertFormulaBtn.addEventListener("click", async () => {
      const text = resultText.value.trim();
      if (!text) {
        setStatus("Нема тексту для вставки.", "error");
        return;
      }
      try {
        await insertAsFormula(text);
        if (typeof Word !== "undefined" && Word.run) {
          setStatus("Вставлено як формулу Word ✓", "success");
        } else {
          setStatus("Скопійовано в буфер обміну (Word не активний) ✓", "success");
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setStatus(msg, "error");
      }
    });
  }

  if (typeof Office !== "undefined" && Office.onReady) {
    Office.onReady(() => init());
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => init());
  } else {
    init();
  }
})();
