import type { PredictionResult, ShapEntry } from "../types";

const METER_WIDTH = 400;
const METER_HEIGHT = 32;
const SHAP_WIDTH = 480;
const SHAP_BAR_HEIGHT = 22;
const SHAP_ROW_HEIGHT = 28;
const SHAP_LABEL_WIDTH = 120;
const SHAP_VALUE_WIDTH = 60;
const SHAP_BAR_AREA_WIDTH = SHAP_WIDTH - SHAP_LABEL_WIDTH - SHAP_VALUE_WIDTH;

/**
 * Get the color for a probability value.
 * Green < 0.3, amber 0.3-0.7, red > 0.7
 */
function getProbabilityColor(p: number): string {
  if (p < 0.3) return "#4a9e6b";
  if (p < 0.7) return "#d4a24e";
  return "#c75a4a";
}

/**
 * Render a horizontal probability meter (0 to 1).
 */
function renderProbabilityMeter(probability: number): string {
  const fillWidth = Math.max(0, Math.min(1, probability)) * (METER_WIDTH - 4);
  const color = getProbabilityColor(probability);
  const pct = (probability * 100).toFixed(1);

  return `
    <div class="prediction-meter-container">
      <div class="prediction-meter-label">Risk Score</div>
      <svg
        viewBox="0 0 ${METER_WIDTH} ${METER_HEIGHT}"
        width="${METER_WIDTH}"
        height="${METER_HEIGHT}"
        class="prediction-meter"
        role="img"
        aria-label="Risk score: ${pct}%"
      >
        <rect x="0" y="0" width="${METER_WIDTH}" height="${METER_HEIGHT}"
              rx="4" fill="#1c1c21" stroke="#27272a" stroke-width="1" />
        <rect x="2" y="2" width="${fillWidth}" height="${METER_HEIGHT - 4}"
              rx="3" fill="${color}" opacity="0.85" />
        <text x="${METER_WIDTH / 2}" y="${METER_HEIGHT / 2 + 1}"
              text-anchor="middle" dominant-baseline="middle"
              fill="#e4e2dd" font-size="13" font-weight="600"
              font-family="'JetBrains Mono', monospace">
          ${pct}%
        </text>
      </svg>
      <div class="prediction-meter-scale">
        <span>0</span>
        <span>0.3</span>
        <span>0.7</span>
        <span>1.0</span>
      </div>
    </div>
  `;
}

/**
 * Render a classification badge pill.
 */
function renderClassificationBadge(
  classification: string,
  probability: number
): string {
  const color = getProbabilityColor(probability);
  return `
    <span class="prediction-badge" style="background: ${color}20; border: 1px solid ${color}; color: ${color}">
      ${classification}
    </span>
  `;
}

/**
 * Render SHAP waterfall as horizontal SVG bar chart.
 * Positive SHAP values extend right (red/amber), negative extend left (blue/green).
 * Sorted by |shapValue| descending.
 */
function renderShapWaterfall(
  shapValues: ShapEntry[],
  baseValue: number
): string {
  if (shapValues.length === 0) return "";

  const sorted = [...shapValues].sort(
    (a, b) => Math.abs(b.shapValue) - Math.abs(a.shapValue)
  );

  const maxAbsShap = Math.max(...sorted.map((s) => Math.abs(s.shapValue)));
  if (maxAbsShap === 0) return "";

  const chartHeight = sorted.length * SHAP_ROW_HEIGHT + 20;
  const barCenter = SHAP_LABEL_WIDTH + SHAP_BAR_AREA_WIDTH / 2;
  const scale = (SHAP_BAR_AREA_WIDTH / 2 - 10) / maxAbsShap;

  const bars = sorted.map((entry, i) => {
    const y = i * SHAP_ROW_HEIGHT + 10;
    const barWidth = Math.abs(entry.shapValue) * scale;
    const isPositive = entry.shapValue >= 0;
    const barX = isPositive ? barCenter : barCenter - barWidth;
    const barColor = isPositive ? "#c75a4a" : "#5ba3c9";

    const featureLabel = entry.feature.length > 14
      ? entry.feature.slice(0, 12) + ".."
      : entry.feature;

    const valueStr = Number.isFinite(entry.value)
      ? (Math.abs(entry.value) >= 100
          ? entry.value.toFixed(0)
          : entry.value.toFixed(2))
      : "";

    return `
      <g transform="translate(0, ${y})">
        <text x="${SHAP_LABEL_WIDTH - 8}" y="${SHAP_BAR_HEIGHT / 2 + 1}"
              text-anchor="end" dominant-baseline="middle"
              fill="#e4e2dd" font-size="11"
              font-family="'Inter', sans-serif">
          ${featureLabel}
        </text>
        <rect x="${barX}" y="2" width="${barWidth}" height="${SHAP_BAR_HEIGHT - 4}"
              rx="2" fill="${barColor}" opacity="0.8" />
        <text x="${SHAP_LABEL_WIDTH + SHAP_BAR_AREA_WIDTH + 4}" y="${SHAP_BAR_HEIGHT / 2 + 1}"
              text-anchor="start" dominant-baseline="middle"
              fill="#71717a" font-size="10"
              font-family="'JetBrains Mono', monospace">
          ${valueStr}
        </text>
      </g>
    `;
  });

  // Base value reference line
  const baseLine = `
    <line x1="${barCenter}" y1="5"
          x2="${barCenter}" y2="${chartHeight - 5}"
          stroke="#71717a" stroke-width="1" stroke-dasharray="3,3" />
    <text x="${barCenter}" y="${chartHeight}"
          text-anchor="middle" fill="#71717a" font-size="9"
          font-family="'JetBrains Mono', monospace">
      base: ${baseValue.toFixed(2)}
    </text>
  `;

  return `
    <div class="shap-waterfall-container">
      <div class="shap-waterfall-label">Feature Contributions (SHAP)</div>
      <svg
        viewBox="0 0 ${SHAP_WIDTH} ${chartHeight + 15}"
        width="${SHAP_WIDTH}"
        height="${chartHeight + 15}"
        class="shap-waterfall"
        role="img"
        aria-label="SHAP feature contributions"
      >
        ${baseLine}
        ${bars.join("")}
      </svg>
      <div class="shap-legend">
        <span class="shap-legend-item">
          <span class="shap-legend-dot" style="background: #c75a4a"></span>
          Increases risk
        </span>
        <span class="shap-legend-item">
          <span class="shap-legend-dot" style="background: #5ba3c9"></span>
          Decreases risk
        </span>
      </div>
    </div>
  `;
}

/**
 * Render the full prediction panel for a patient.
 * Shows probability meter, classification badge, and SHAP waterfall.
 */
export function renderPredictionPanel(
  prediction: PredictionResult | null
): string {
  if (!prediction) return "";

  const meter = renderProbabilityMeter(prediction.probability);
  const badge = renderClassificationBadge(
    prediction.classification,
    prediction.probability
  );
  const waterfall = renderShapWaterfall(
    prediction.shapValues,
    prediction.baseValue
  );

  return `
    <div class="prediction-panel">
      <div class="prediction-panel-header">
        <span class="prediction-panel-title">ML Prediction</span>
        ${badge}
      </div>
      ${meter}
      ${waterfall}
    </div>
  `;
}
