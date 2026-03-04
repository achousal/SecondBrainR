import type { Panel } from "../types";

/**
 * Render a panel selection dropdown.
 */
export function renderPanelSelector(
  panels: Panel[],
  selectedId: string | null
): string {
  const options = panels.map((p) => {
    const selected = p.id === selectedId ? "selected" : "";
    return `<option value="${p.id}" ${selected}>${p.name}</option>`;
  });

  return `
    <select id="panel-selector" class="panel-select" aria-label="Select biomarker panel">
      <option value="" disabled ${selectedId ? "" : "selected"}>Select panel...</option>
      ${options.join("")}
    </select>
  `;
}
