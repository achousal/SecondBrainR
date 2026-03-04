import type { PatientRecord, Panel } from "../types";
import { classifyZone } from "../utils/zone";

/**
 * Render the summary strip showing all biomarkers color-coded by zone.
 */
export function renderSummaryStrip(
  patient: PatientRecord,
  panel: Panel
): string {
  const items = panel.biomarkers.map((bm) => {
    const value = patient.values[bm.id];
    const result =
      value !== null && value !== undefined
        ? classifyZone(value, bm)
        : null;
    const color = result?.zone.color ?? "#71717a";
    const label = result?.zone.label ?? "N/A";

    return `
      <span class="summary-item" style="border-color: ${color}">
        <span class="summary-name">${bm.name}</span>
        <span class="summary-zone" style="color: ${color}">${label}</span>
      </span>
    `;
  });

  return `
    <div class="summary-strip">
      <span class="summary-label">Summary:</span>
      ${items.join("")}
    </div>
  `;
}
