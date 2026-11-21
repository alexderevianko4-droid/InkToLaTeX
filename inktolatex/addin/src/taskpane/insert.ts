/**
 * Word document insertion helpers.
 *
 * Office and Word are global objects provided by the Office.js script tag —
 * do NOT import them as modules.
 */

import { convertToOoxml } from "./api";

declare const Word: any;

/**
 * Insert plain text at the current cursor position (replaces selection).
 */
export async function insertText(text: string): Promise<void> {
  if (typeof Word !== "undefined" && Word.run) {
    try {
      await Word.run(async (context: any) => {
        const selection = context.document.getSelection();
        selection.insertText(text, Word.InsertLocation.replace);
        await context.sync();
      });
      return;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      throw new Error(`Помилка вставки тексту в документ: ${msg}`);
    }
  }

  // Fallback for standalone browser preview: copy to clipboard
  if (navigator?.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  throw new Error("Word не виявлено (відкрито не в надбудові Word).");
}

/**
 * Insert text as native Word Math Equation using OMML / OOXML.
 *
 * Converts LaTeX formulas into Office Math Markup Language (OMML) via the backend
 * and inserts the resulting OpenXML package into the document.
 */
export async function insertAsFormula(text: string): Promise<void> {
  if (typeof Word !== "undefined" && Word.run) {
    try {
      const ooxml = await convertToOoxml(text);
      await Word.run(async (context: any) => {
        const selection = context.document.getSelection();
        selection.insertOoxml(ooxml, Word.InsertLocation.replace);
        await context.sync();
      });
      return;
    } catch (err: unknown) {
      console.warn("Falling back to plain text insertion in Word:", err);
      await insertText(text);
      return;
    }
  }

  // Fallback for standalone browser preview
  await insertText(text);
}
