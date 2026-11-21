/**
 * InkToLaTeX — main task pane entry point.
 *
 * Globals expected from <script> tags: Office, Word, katex.
 */

import { InkCanvas } from "./canvas";
import { recognize } from "./api";
import { insertText, insertAsFormula } from "./insert";

declare const Office: any;
declare const katex: any;

/* ---------- DOM helpers ---------- */

function $(id: string): HTMLElement {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Element #${id} not found`);
  return el;
}

function setStatus(msg: string, type: "error" | "success" | "" = ""): void {
  const el = $("status");
  el.textContent = msg;
  el.className = type;
}

/* ---------- KaTeX preview ---------- */

/**
 * Render a string that may contain inline `$…$` and display `$$…$$` math
 * into HTML using KaTeX. Non-math parts are HTML-escaped and wrapped in <span>.
 */
function renderPreview(text: string): string {
  if (!text.trim()) return "";

  // We process display math ($$…$$) first, then inline ($…$).
  // Use a placeholder approach to avoid double-processing.

  const parts: string[] = [];
  let remaining = text;

  // ---- display math $$...$$ ----
  const displayRe = /\$\$([\s\S]+?)\$\$/g;
  let last = 0;
  let match: RegExpExecArray | null;

  const segments: { start: number; end: number; html: string }[] = [];

  while ((match = displayRe.exec(remaining)) !== null) {
    segments.push({
      start: match.index,
      end: match.index + match[0].length,
      html: safeKaTeX(match[1], true),
    });
  }

  // ---- inline math $...$ (but not $$) ----
  const inlineRe = /(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)/g;
  while ((match = inlineRe.exec(remaining)) !== null) {
    // Skip if overlapping with a display segment
    const overlaps = segments.some(
      (s) => match!.index < s.end && match!.index + match![0].length > s.start
    );
    if (!overlaps) {
      segments.push({
        start: match.index,
        end: match.index + match[0].length,
        html: safeKaTeX(match[1], false),
      });
    }
  }

  // Sort by position
  segments.sort((a, b) => a.start - b.start);

  // Build output
  last = 0;
  for (const seg of segments) {
    if (seg.start > last) {
      parts.push(escapeHTML(remaining.slice(last, seg.start)));
    }
    parts.push(seg.html);
    last = seg.end;
  }
  if (last < remaining.length) {
    parts.push(escapeHTML(remaining.slice(last)));
  }

  return parts.join("");
}

function safeKaTeX(tex: string, displayMode: boolean): string {
  try {
    return katex.renderToString(tex, {
      displayMode,
      throwOnError: false,
      output: "html",
    });
  } catch {
    return `<span style="color:#d83b01" title="KaTeX error">${escapeHTML(tex)}</span>`;
  }
}

function escapeHTML(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* ---------- bootstrap ---------- */

function init(): void {
  const canvasEl = $("ink-canvas") as HTMLCanvasElement;
  if (!canvasEl) return;
  const inkCanvas = new InkCanvas(canvasEl);

  const clearBtn = $("clear-btn") as HTMLButtonElement;
  const undoBtn = $("undo-btn") as HTMLButtonElement;
  const recognizeBtn = $("recognize-btn") as HTMLButtonElement;
  const insertBtn = $("insert-btn") as HTMLButtonElement;
  const insertFormulaBtn = $("insert-formula-btn") as HTMLButtonElement;
  const resultText = $("result-text") as HTMLTextAreaElement;
  const preview = $("preview");

  /* ---- canvas toolbar ---- */
  clearBtn.addEventListener("click", () => {
    inkCanvas.clear();
    setStatus("");
  });

  undoBtn.addEventListener("click", () => {
    inkCanvas.undo();
  });

  /* ---- recognize ---- */
  recognizeBtn.addEventListener("click", async () => {
    const png = inkCanvas.toPNG();
    if (!png) {
      setStatus("Малюнок порожній — намалюйте щось спершу.", "error");
      return;
    }

    // Show loading state
    recognizeBtn.disabled = true;
    const originalHTML = recognizeBtn.innerHTML;
    recognizeBtn.innerHTML = '<span class="spinner"></span>Розпізнавання…';
    setStatus("");

    try {
      const result = await recognize(png);
      resultText.value = result;
      preview.innerHTML = renderPreview(result);
      setStatus("Розпізнано успішно!", "success");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(msg, "error");
    } finally {
      recognizeBtn.disabled = false;
      recognizeBtn.innerHTML = originalHTML;
    }
  });

  /* ---- live preview on textarea input ---- */
  resultText.addEventListener("input", () => {
    preview.innerHTML = renderPreview(resultText.value);
  });

  /* ---- insert into document ---- */
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
    } catch (err: unknown) {
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
    } catch (err: unknown) {
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
