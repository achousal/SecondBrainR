import { describe, it, expect } from "vitest";
import {
  validatePanel,
  loadPanels,
  getPanelById,
} from "../config/reference_ranges";
import type { Panel } from "../types";

describe("validatePanel", () => {
  it("validates a well-formed panel", () => {
    const panel: Panel = {
      id: "test",
      name: "Test Panel",
      version: "1.0.0",
      description: "A test panel",
      biomarkers: [
        {
          id: "bm1",
          name: "Biomarker 1",
          unit: "mg/L",
          aliases: ["bm1"],
          zones: [
            { label: "Low", min: 0, max: 5, color: "#4a9e6b", interpretation: "Low" },
            { label: "High", min: 5, max: 100, color: "#c75a4a", interpretation: "High" },
          ],
        },
      ],
    };
    expect(validatePanel(panel)).toEqual([]);
  });

  it("rejects panel without id", () => {
    const panel = { id: "", name: "Test", version: "1", description: "", biomarkers: [] } as Panel;
    const errors = validatePanel(panel);
    expect(errors.length).toBeGreaterThan(0);
    expect(errors.some((e) => e.includes("id"))).toBe(true);
  });

  it("rejects panel without biomarkers", () => {
    const panel = { id: "t", name: "T", version: "1", description: "", biomarkers: [] } as Panel;
    const errors = validatePanel(panel);
    expect(errors.some((e) => e.includes("at least one biomarker"))).toBe(true);
  });

  it("rejects zone with min >= max", () => {
    const panel: Panel = {
      id: "t",
      name: "T",
      version: "1",
      description: "",
      biomarkers: [
        {
          id: "bm",
          name: "BM",
          unit: "x",
          aliases: [],
          zones: [{ label: "Bad", min: 10, max: 5, color: "#000", interpretation: "" }],
        },
      ],
    };
    const errors = validatePanel(panel);
    expect(errors.some((e) => e.includes("min") && e.includes("max"))).toBe(true);
  });

  it("detects zone gaps", () => {
    const panel: Panel = {
      id: "t",
      name: "T",
      version: "1",
      description: "",
      biomarkers: [
        {
          id: "bm",
          name: "BM",
          unit: "x",
          aliases: [],
          zones: [
            { label: "A", min: 0, max: 5, color: "#000", interpretation: "" },
            { label: "B", min: 6, max: 10, color: "#000", interpretation: "" },
          ],
        },
      ],
    };
    const errors = validatePanel(panel);
    expect(errors.some((e) => e.includes("gap or overlap"))).toBe(true);
  });

  it("detects duplicate biomarker IDs", () => {
    const panel: Panel = {
      id: "t",
      name: "T",
      version: "1",
      description: "",
      biomarkers: [
        {
          id: "same",
          name: "A",
          unit: "x",
          aliases: [],
          zones: [{ label: "Z", min: 0, max: 10, color: "#000", interpretation: "" }],
        },
        {
          id: "same",
          name: "B",
          unit: "x",
          aliases: [],
          zones: [{ label: "Z", min: 0, max: 10, color: "#000", interpretation: "" }],
        },
      ],
    };
    const errors = validatePanel(panel);
    expect(errors.some((e) => e.includes("Duplicate"))).toBe(true);
  });
});

describe("loadPanels", () => {
  it("loads all 3 built-in panels", () => {
    const panels = loadPanels();
    expect(panels).toHaveLength(3);
  });

  it("all panels pass validation", () => {
    const panels = loadPanels();
    for (const panel of panels) {
      expect(validatePanel(panel)).toEqual([]);
    }
  });

  it("panels have expected IDs", () => {
    const panels = loadPanels();
    const ids = panels.map((p) => p.id);
    expect(ids).toContain("ad_classification");
    expect(ids).toContain("vascbrain");
    expect(ids).toContain("general_clinical");
  });
});

describe("getPanelById", () => {
  it("finds panel by id", () => {
    const panels = loadPanels();
    const panel = getPanelById(panels, "ad_classification");
    expect(panel).toBeDefined();
    expect(panel!.name).toContain("AD");
  });

  it("returns undefined for unknown id", () => {
    const panels = loadPanels();
    expect(getPanelById(panels, "nonexistent")).toBeUndefined();
  });
});
