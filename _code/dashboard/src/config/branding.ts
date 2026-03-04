import type { DashboardConfig } from "../types";

/** Default branding when no profile config is found */
const DEFAULTS: DashboardConfig = {
  title: "Biomarker Report",
  institution: "",
  disclaimer: "",
  footer: "",
};

// Load dashboard configs from profiles (build-time resolved)
const profileConfigs = import.meta.glob<{ default: Record<string, string> }>(
  "../../../profiles/*/dashboard_config.yaml",
  { eager: true, import: "default" }
);

/**
 * Load branding configuration from the first available profile.
 * Falls back to defaults if no config found.
 */
export function loadBranding(): DashboardConfig {
  const entries = Object.values(profileConfigs);

  if (entries.length === 0) {
    return DEFAULTS;
  }

  // Use the first profile config found
  const raw = entries[0] as unknown as Record<string, string>;

  return {
    title: raw.title || DEFAULTS.title,
    institution: raw.institution || DEFAULTS.institution,
    logoSvg: raw.logoSvg || undefined,
    disclaimer: raw.disclaimer || DEFAULTS.disclaimer,
    footer: raw.footer || DEFAULTS.footer,
  };
}
