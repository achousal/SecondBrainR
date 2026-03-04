import type { BiomarkerConfig } from "../types";
import { renderGaugeArc } from "./GaugeArc";
import { formatWithUnit } from "../utils/format";
import { classifyZone } from "../utils/zone";

/**
 * Render a single biomarker gauge card.
 * Shows: biomarker name, unit, gauge arc, value, zone label, interpretation, source.
 */
export function renderGaugeCard(
  value: number | null,
  biomarker: BiomarkerConfig
): string {
  const gauge = renderGaugeArc(value, biomarker);
  const formatted = formatWithUnit(value, biomarker.unit);
  const result = value !== null ? classifyZone(value, biomarker) : null;
  const zoneLabel = result?.zone.label ?? "No data";
  const zoneColor = result?.zone.color ?? "#71717a";
  const interpretation = result?.zone.interpretation ?? "";
  const source = biomarker.source ?? "";

  return `
    <div class="gauge-card">
      <div class="gauge-card-header">
        <span class="gauge-card-name">${biomarker.name}</span>
        <span class="gauge-card-unit">${biomarker.unit}</span>
      </div>
      <div class="gauge-card-arc">
        ${gauge}
      </div>
      <div class="gauge-card-value">${formatted}</div>
      <div class="gauge-card-zone" style="color: ${zoneColor}">
        <span class="zone-badge" style="background: ${zoneColor}20; border: 1px solid ${zoneColor}; color: ${zoneColor}">
          ${zoneLabel}
        </span>
      </div>
      <div class="gauge-card-interpretation">${interpretation}</div>
      ${source ? `<div class="gauge-card-source">${source}</div>` : ""}
    </div>
  `;
}
