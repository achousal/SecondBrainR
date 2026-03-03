import type { BiomarkerConfig, ColumnMapping } from "../types";

/**
 * Normalize a column header for matching: lowercase, strip non-alphanumeric.
 */
export function normalizeHeader(header: string): string {
  return header.toLowerCase().replace(/[^a-z0-9]/g, "");
}

/** Known column names for patient ID */
const ID_ALIASES = ["id", "patient_id", "subject_id", "eid", "pid", "patientid", "subjectid"];

/** Known column names for display name */
const NAME_ALIASES = ["name", "display_name", "patient_name", "displayname", "patientname"];

/** Known column names for age */
const AGE_ALIASES = ["age", "patient_age", "ageatvisit", "age_at_visit"];

/** Known column names for sex */
const SEX_ALIASES = ["sex", "gender", "patient_sex"];

/** Known column names for visit date */
const DATE_ALIASES = ["visit_date", "visitdate", "date", "visit", "date_of_visit"];

/**
 * Try to match a normalized header against a list of aliases.
 */
function matchAlias(normalizedHeader: string, aliases: string[]): boolean {
  return aliases.some((alias) => normalizeHeader(alias) === normalizedHeader);
}

/**
 * Auto-detect the ID column from headers.
 */
export function detectIdColumn(headers: string[]): string | null {
  for (const header of headers) {
    if (matchAlias(normalizeHeader(header), ID_ALIASES)) {
      return header;
    }
  }
  return null;
}

/**
 * Auto-detect the display name column from headers.
 */
export function detectNameColumn(headers: string[]): string | null {
  for (const header of headers) {
    if (matchAlias(normalizeHeader(header), NAME_ALIASES)) {
      return header;
    }
  }
  return null;
}

/**
 * Auto-detect the age column from headers.
 */
export function detectAgeColumn(headers: string[]): string | null {
  for (const header of headers) {
    if (matchAlias(normalizeHeader(header), AGE_ALIASES)) {
      return header;
    }
  }
  return null;
}

/**
 * Auto-detect the sex column from headers.
 */
export function detectSexColumn(headers: string[]): string | null {
  for (const header of headers) {
    if (matchAlias(normalizeHeader(header), SEX_ALIASES)) {
      return header;
    }
  }
  return null;
}

/**
 * Auto-detect the visit date column from headers.
 */
export function detectDateColumn(headers: string[]): string | null {
  for (const header of headers) {
    if (matchAlias(normalizeHeader(header), DATE_ALIASES)) {
      return header;
    }
  }
  return null;
}

/**
 * Auto-detect column mappings for biomarkers based on panel config aliases.
 * Returns mapping of biomarker ID -> column header for matched biomarkers.
 */
export function autoMapColumns(
  headers: string[],
  biomarkers: BiomarkerConfig[]
): ColumnMapping {
  const mapping: ColumnMapping = {};
  const normalizedHeaders = headers.map((h) => ({
    original: h,
    normalized: normalizeHeader(h),
  }));

  for (const biomarker of biomarkers) {
    const allAliases = [biomarker.id, ...biomarker.aliases];
    const normalizedAliases = allAliases.map(normalizeHeader);

    for (const { original, normalized } of normalizedHeaders) {
      if (normalizedAliases.includes(normalized)) {
        mapping[biomarker.id] = original;
        break;
      }
    }
  }

  return mapping;
}

/**
 * Check which biomarkers are unmapped.
 */
export function getUnmappedBiomarkers(
  mapping: ColumnMapping,
  biomarkers: BiomarkerConfig[]
): BiomarkerConfig[] {
  return biomarkers.filter((bm) => !(bm.id in mapping));
}
