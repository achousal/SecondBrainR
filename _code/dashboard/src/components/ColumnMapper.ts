import type { BiomarkerConfig } from "../types";

/**
 * Render the manual column mapping UI.
 * Shown only when auto-detection fails for some biomarkers.
 */
export function renderColumnMapper(
  unmappedBiomarkers: BiomarkerConfig[],
  availableHeaders: string[]
): string {
  if (unmappedBiomarkers.length === 0) return "";

  const rows = unmappedBiomarkers.map((bm) => {
    const headerOptions = availableHeaders.map(
      (h) => `<option value="${h}">${h}</option>`
    );

    return `
      <tr>
        <td class="mapper-biomarker">${bm.name} (${bm.unit})</td>
        <td class="mapper-aliases">${bm.aliases.join(", ")}</td>
        <td>
          <select class="mapper-select" data-biomarker-id="${bm.id}">
            <option value="">-- skip --</option>
            ${headerOptions.join("")}
          </select>
        </td>
      </tr>
    `;
  });

  return `
    <div class="column-mapper">
      <h3 class="mapper-title">Column Mapping Required</h3>
      <p class="mapper-desc">
        Some biomarkers could not be auto-detected. Please map them manually or skip.
      </p>
      <table class="mapper-table">
        <thead>
          <tr>
            <th>Biomarker</th>
            <th>Expected aliases</th>
            <th>Map to column</th>
          </tr>
        </thead>
        <tbody>
          ${rows.join("")}
        </tbody>
      </table>
      <button id="btn-apply-mapping" class="btn-action">Apply Mapping</button>
    </div>
  `;
}
