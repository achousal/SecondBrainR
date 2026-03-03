import type { Panel, BiomarkerConfig, ZoneConfig } from "../types";

// Profile panels (build-time resolved, inlined into bundle)
const profilePanels = import.meta.glob<{ default: Panel }>(
  "../../../profiles/*/panels/*.json",
  { eager: true, import: "default" }
);

// Local fallbacks for standalone dev
const localPanels = import.meta.glob<{ default: Panel }>(
  "./panels/*.json",
  { eager: true, import: "default" }
);

/**
 * Validate a single zone config. Returns an error message or null.
 */
function validateZone(zone: ZoneConfig, index: number): string | null {
  if (typeof zone.min !== "number" || typeof zone.max !== "number") {
    return `Zone ${index}: min and max must be numbers`;
  }
  if (zone.min >= zone.max) {
    return `Zone ${index}: min (${zone.min}) must be less than max (${zone.max})`;
  }
  if (!zone.label || typeof zone.label !== "string") {
    return `Zone ${index}: label is required`;
  }
  if (!zone.color || typeof zone.color !== "string") {
    return `Zone ${index}: color is required`;
  }
  return null;
}

/**
 * Validate a biomarker config. Returns error messages.
 */
function validateBiomarker(biomarker: BiomarkerConfig): string[] {
  const errors: string[] = [];

  if (!biomarker.id) errors.push("Biomarker missing id");
  if (!biomarker.name) errors.push("Biomarker missing name");
  if (!biomarker.unit) errors.push("Biomarker missing unit");
  if (!Array.isArray(biomarker.zones) || biomarker.zones.length === 0) {
    errors.push(`Biomarker ${biomarker.id}: must have at least one zone`);
  }

  biomarker.zones?.forEach((zone, i) => {
    const err = validateZone(zone, i);
    if (err) errors.push(`Biomarker ${biomarker.id}: ${err}`);
  });

  // Check zone continuity (zones should be contiguous)
  if (biomarker.zones && biomarker.zones.length > 1) {
    const sorted = [...biomarker.zones].sort((a, b) => a.min - b.min);
    for (let i = 1; i < sorted.length; i++) {
      if (sorted[i].min !== sorted[i - 1].max) {
        errors.push(
          `Biomarker ${biomarker.id}: gap or overlap between zones ${i - 1} and ${i}`
        );
      }
    }
  }

  return errors;
}

/**
 * Validate a full panel config. Returns error messages.
 */
export function validatePanel(panel: Panel): string[] {
  const errors: string[] = [];

  if (!panel.id) errors.push("Panel missing id");
  if (!panel.name) errors.push("Panel missing name");
  if (!panel.version) errors.push("Panel missing version");
  if (!Array.isArray(panel.biomarkers) || panel.biomarkers.length === 0) {
    errors.push("Panel must have at least one biomarker");
  }

  // Check for duplicate biomarker IDs
  const ids = new Set<string>();
  panel.biomarkers?.forEach((bm) => {
    if (ids.has(bm.id)) {
      errors.push(`Duplicate biomarker id: ${bm.id}`);
    }
    ids.add(bm.id);
    errors.push(...validateBiomarker(bm));
  });

  return errors;
}

/**
 * Collect panels from glob imports, deduplicating by ID.
 * Profile panels take priority over local fallbacks.
 */
function collectPanels(): Panel[] {
  const panelMap = new Map<string, Panel>();

  // Load local fallbacks first
  for (const [, mod] of Object.entries(localPanels)) {
    const panel = (mod as unknown) as Panel;
    if (panel?.id) {
      panelMap.set(panel.id, panel);
    }
  }

  // Profile panels override local (higher priority)
  for (const [, mod] of Object.entries(profilePanels)) {
    const panel = (mod as unknown) as Panel;
    if (panel?.id) {
      panelMap.set(panel.id, panel);
    }
  }

  return Array.from(panelMap.values());
}

/**
 * Load and validate all available panels.
 * Panels are collected from profile directories and local fallbacks.
 * Profile panels take priority (dedup by ID).
 * Throws if any panel is invalid.
 */
export function loadPanels(): Panel[] {
  const rawPanels = collectPanels();

  if (rawPanels.length === 0) {
    throw new Error("No panel configurations found");
  }

  for (const panel of rawPanels) {
    const errors = validatePanel(panel);
    if (errors.length > 0) {
      throw new Error(
        `Invalid panel "${panel.id || "unknown"}":\n${errors.join("\n")}`
      );
    }
  }

  return rawPanels;
}

/**
 * Get a panel by its ID.
 */
export function getPanelById(
  panels: Panel[],
  id: string
): Panel | undefined {
  return panels.find((p) => p.id === id);
}
