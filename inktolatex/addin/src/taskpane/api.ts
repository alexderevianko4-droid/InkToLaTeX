/**
 * API client for the InkToLaTeX backend.
 */

export const API_BASE = "http://localhost:8000";

const TIMEOUT_MS = 30_000;

/**
 * Send a base64-encoded PNG to the recognition endpoint and return the LaTeX string.
 */
export async function recognize(pngBase64: string): Promise<string> {
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
      } catch {
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
  } catch (err: unknown) {
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

/**
 * Convert text with LaTeX to Word Flat OPC OOXML for native equation insertion.
 */
export async function convertToOoxml(text: string): Promise<string> {
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
      } catch {
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
