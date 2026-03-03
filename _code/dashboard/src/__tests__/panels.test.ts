import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, existsSync } from "fs";
import { join, resolve } from "path";
import { validatePanel } from "../config/reference_ranges";
import type { Panel } from "../types";

const PROFILE_PANELS_DIR = resolve(__dirname, "../../../profiles/bioinformatics/panels");
const LOCAL_PANELS_DIR = resolve(__dirname, "../config/panels");

function loadPanelFile(path: string): Panel {
  return JSON.parse(readFileSync(path, "utf-8"));
}

function getPanelFiles(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => join(dir, f));
}

describe("profile panel files", () => {
  const files = getPanelFiles(PROFILE_PANELS_DIR);

  it("profile panels directory exists and has panels", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  for (const file of files) {
    const name = file.split("/").pop()!;

    it(`${name} is valid JSON`, () => {
      expect(() => loadPanelFile(file)).not.toThrow();
    });

    it(`${name} passes panel validation`, () => {
      const panel = loadPanelFile(file);
      const errors = validatePanel(panel);
      expect(errors).toEqual([]);
    });

    it(`${name} has required fields`, () => {
      const panel = loadPanelFile(file);
      expect(panel.id).toBeTruthy();
      expect(panel.name).toBeTruthy();
      expect(panel.version).toBeTruthy();
      expect(panel.biomarkers.length).toBeGreaterThan(0);
    });

    it(`${name} has contiguous zones for each biomarker`, () => {
      const panel = loadPanelFile(file);
      for (const bm of panel.biomarkers) {
        const sorted = [...bm.zones].sort((a, b) => a.min - b.min);
        for (let i = 1; i < sorted.length; i++) {
          expect(sorted[i].min).toBe(sorted[i - 1].max);
        }
      }
    });
  }
});

describe("local panel files", () => {
  const files = getPanelFiles(LOCAL_PANELS_DIR);

  it("local panels directory has fallback panels", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  for (const file of files) {
    const name = file.split("/").pop()!;

    it(`${name} passes validation`, () => {
      const panel = loadPanelFile(file);
      const errors = validatePanel(panel);
      expect(errors).toEqual([]);
    });
  }
});

describe("panel deduplication", () => {
  it("profile and local panels have matching IDs", () => {
    const profileFiles = getPanelFiles(PROFILE_PANELS_DIR);
    const localFiles = getPanelFiles(LOCAL_PANELS_DIR);

    const profileIds = new Set(profileFiles.map((f) => loadPanelFile(f).id));
    const localIds = new Set(localFiles.map((f) => loadPanelFile(f).id));

    // All local panels should also exist in profiles (profile overrides local)
    for (const id of localIds) {
      expect(profileIds.has(id)).toBe(true);
    }
  });
});
