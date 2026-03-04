import type { BiomarkerConfig, ZoneConfig, ZoneResult } from "../types";

/**
 * Classify a value into its zone based on a biomarker's zone configuration.
 * Returns the matching zone, or null if the value is outside all defined ranges.
 *
 * Zones are matched by inclusive min, exclusive max (min <= value < max),
 * except for the last zone which is inclusive on both ends (min <= value <= max).
 */
export function classifyZone(
  value: number,
  biomarker: BiomarkerConfig
): ZoneResult | null {
  if (!Number.isFinite(value)) return null;
  if (biomarker.zones.length === 0) return null;

  const sorted = [...biomarker.zones].sort((a, b) => a.min - b.min);

  for (let i = 0; i < sorted.length; i++) {
    const zone = sorted[i];
    const isLast = i === sorted.length - 1;

    if (isLast) {
      // Last zone: inclusive on both ends
      if (value >= zone.min && value <= zone.max) {
        return { zone, value, biomarker };
      }
    } else {
      // Other zones: inclusive min, exclusive max
      if (value >= zone.min && value < zone.max) {
        return { zone, value, biomarker };
      }
    }
  }

  return null;
}

/**
 * Get a zone color for a value, with fallback for out-of-range.
 */
export function getZoneColor(
  value: number,
  biomarker: BiomarkerConfig
): string {
  const result = classifyZone(value, biomarker);
  return result?.zone.color ?? "#71717a"; // text-muted fallback
}

/**
 * Get the zone label for a value.
 */
export function getZoneLabel(
  value: number,
  biomarker: BiomarkerConfig
): string {
  const result = classifyZone(value, biomarker);
  return result?.zone.label ?? "Unknown";
}

/**
 * Get the interpretation text for a value's zone.
 */
export function getZoneInterpretation(
  value: number,
  biomarker: BiomarkerConfig
): string {
  const result = classifyZone(value, biomarker);
  return result?.zone.interpretation ?? "";
}

/**
 * Check if a value falls in a "concerning" zone (not normal/low-risk).
 * A zone is concerning if its label is NOT one of the recognized normal labels.
 */
export function isConcerning(
  value: number,
  biomarker: BiomarkerConfig
): boolean {
  const result = classifyZone(value, biomarker);
  if (!result) return false;
  const normalLabels = ["normal", "low risk", "rule-out", "negative"];
  return !normalLabels.includes(result.zone.label.toLowerCase());
}
