/**
 * Format a number for display with appropriate significant figures.
 * - Values >= 100: no decimal places
 * - Values >= 10: 1 decimal place
 * - Values >= 1: 2 decimal places
 * - Values >= 0.01: 3 decimal places
 * - Values < 0.01: scientific notation
 */
export function formatValue(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }

  const abs = Math.abs(value);

  if (abs === 0) return "0";
  if (abs >= 100) return value.toFixed(0);
  if (abs >= 10) return value.toFixed(1);
  if (abs >= 1) return value.toFixed(2);
  if (abs >= 0.01) return value.toFixed(3);
  return value.toExponential(2);
}

/**
 * Format a value with its unit string.
 */
export function formatWithUnit(
  value: number | null | undefined,
  unit: string
): string {
  const formatted = formatValue(value);
  if (formatted === "--") return formatted;
  if (!unit || unit === "ratio") return formatted;
  return `${formatted} ${unit}`;
}

/**
 * Format a patient ID for display, truncating if very long.
 */
export function formatPatientId(id: string, maxLength = 20): string {
  if (!id) return "Unknown";
  if (id.length <= maxLength) return id;
  return id.slice(0, maxLength - 3) + "...";
}
