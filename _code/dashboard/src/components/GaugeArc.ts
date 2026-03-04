import { arc as d3Arc, type DefaultArcObject } from "d3-shape";
import type { BiomarkerConfig } from "../types";

const ARC_WIDTH = 200;
const ARC_HEIGHT = 120;
const OUTER_RADIUS = 85;
const INNER_RADIUS = 55;
const NEEDLE_LENGTH = 70;

/**
 * Render a half-arc gauge SVG for a biomarker value.
 * The arc spans 180 degrees (bottom semicircle), with zones as colored segments
 * and a needle indicator pointing to the patient value.
 */
export function renderGaugeArc(
  value: number | null,
  biomarker: BiomarkerConfig
): string {
  const zones = [...biomarker.zones].sort((a, b) => a.min - b.min);
  if (zones.length === 0) return "";

  const globalMin = zones[0].min;
  const globalMax = zones[zones.length - 1].max;
  const range = globalMax - globalMin;

  if (range <= 0) return "";

  const arcGen = d3Arc();
  const centerX = ARC_WIDTH / 2;
  const centerY = ARC_HEIGHT - 10;

  // Build arc segments
  const segments = zones.map((zone) => {
    const startFrac = (zone.min - globalMin) / range;
    const endFrac = (zone.max - globalMin) / range;
    // Map to angle: PI (left) to 0 (right)
    const startAngle = Math.PI - startFrac * Math.PI;
    const endAngle = Math.PI - endFrac * Math.PI;

    const arcData: DefaultArcObject = {
      innerRadius: INNER_RADIUS,
      outerRadius: OUTER_RADIUS,
      startAngle: Math.min(startAngle, endAngle),
      endAngle: Math.max(startAngle, endAngle),
      padAngle: 0,
    };
    const path = arcGen(arcData);

    return `<path d="${path}" fill="${zone.color}" opacity="0.85" />`;
  });

  // Needle
  let needleSvg = "";
  if (value !== null && Number.isFinite(value)) {
    const clamped = Math.max(globalMin, Math.min(globalMax, value));
    const frac = (clamped - globalMin) / range;
    const angle = Math.PI - frac * Math.PI;
    const tipX = Math.cos(angle) * NEEDLE_LENGTH;
    const tipY = -Math.sin(angle) * NEEDLE_LENGTH;

    needleSvg = `
      <line
        x1="0" y1="0"
        x2="${tipX.toFixed(2)}" y2="${(-tipY).toFixed(2)}"
        stroke="#e4e2dd"
        stroke-width="2.5"
        stroke-linecap="round"
        class="gauge-needle"
      />
      <circle cx="0" cy="0" r="4" fill="#e4e2dd" />
    `;
  }

  // Min/max labels
  const labels = `
    <text x="${-OUTER_RADIUS}" y="14" fill="#71717a" font-size="10" text-anchor="start">
      ${globalMin}
    </text>
    <text x="${OUTER_RADIUS}" y="14" fill="#71717a" font-size="10" text-anchor="end">
      ${globalMax}
    </text>
  `;

  return `
    <svg
      viewBox="0 0 ${ARC_WIDTH} ${ARC_HEIGHT}"
      width="${ARC_WIDTH}"
      height="${ARC_HEIGHT}"
      class="gauge-arc"
      role="img"
      aria-label="${biomarker.name} gauge"
    >
      <g transform="translate(${centerX}, ${centerY})">
        ${segments.join("\n")}
        ${needleSvg}
        ${labels}
      </g>
    </svg>
  `;
}
