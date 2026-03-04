import { describe, it, expect } from "vitest";
import {
  classifyZone,
  getZoneColor,
  getZoneLabel,
  getZoneInterpretation,
  isConcerning,
} from "../utils/zone";
import type { BiomarkerConfig } from "../types";

// Test biomarker with 3 zones
const ptau217: BiomarkerConfig = {
  id: "ptau217",
  name: "p-tau 217",
  unit: "pg/mL",
  aliases: ["ptau217"],
  zones: [
    { label: "Rule-out", min: 0, max: 0.42, color: "#5ba3c9", interpretation: "Amyloid unlikely" },
    { label: "Intermediate", min: 0.42, max: 1.07, color: "#d4a24e", interpretation: "Borderline" },
    { label: "Rule-in", min: 1.07, max: 100, color: "#c75a4a", interpretation: "Amyloid likely" },
  ],
};

// Test biomarker with inverted zones (lower is worse, like eGFR)
const egfr: BiomarkerConfig = {
  id: "egfr",
  name: "eGFR",
  unit: "mL/min/1.73m2",
  aliases: ["egfr"],
  zones: [
    { label: "Severe", min: 0, max: 30, color: "#c75a4a", interpretation: "Stage 4-5" },
    { label: "Moderate", min: 30, max: 60, color: "#d4a24e", interpretation: "Stage 3" },
    { label: "Normal", min: 60, max: 90, color: "#5ba3c9", interpretation: "Mild reduction" },
    { label: "Normal", min: 90, max: 300, color: "#4a9e6b", interpretation: "Normal" },
  ],
};

// Biomarker with no zones
const empty: BiomarkerConfig = {
  id: "empty",
  name: "Empty",
  unit: "x",
  aliases: [],
  zones: [],
};

describe("classifyZone", () => {
  // Basic zone classification
  it("classifies value in first zone", () => {
    const result = classifyZone(0.2, ptau217);
    expect(result).not.toBeNull();
    expect(result!.zone.label).toBe("Rule-out");
  });

  it("classifies value in middle zone", () => {
    const result = classifyZone(0.7, ptau217);
    expect(result).not.toBeNull();
    expect(result!.zone.label).toBe("Intermediate");
  });

  it("classifies value in last zone", () => {
    const result = classifyZone(2.5, ptau217);
    expect(result).not.toBeNull();
    expect(result!.zone.label).toBe("Rule-in");
  });

  // Boundary conditions
  it("classifies value at exact zone boundary (lower)", () => {
    const result = classifyZone(0, ptau217);
    expect(result).not.toBeNull();
    expect(result!.zone.label).toBe("Rule-out");
  });

  it("classifies value at zone transition (0.42)", () => {
    // 0.42 is the min of Intermediate zone, but also the max of Rule-out
    // With inclusive-min/exclusive-max for non-last zones, 0.42 falls in Intermediate
    const result = classifyZone(0.42, ptau217);
    expect(result).not.toBeNull();
    expect(result!.zone.label).toBe("Intermediate");
  });

  it("classifies value at zone transition (1.07)", () => {
    const result = classifyZone(1.07, ptau217);
    expect(result).not.toBeNull();
    expect(result!.zone.label).toBe("Rule-in");
  });

  it("classifies value at upper boundary of last zone", () => {
    const result = classifyZone(100, ptau217);
    expect(result).not.toBeNull();
    expect(result!.zone.label).toBe("Rule-in");
  });

  // Edge cases
  it("returns null for NaN", () => {
    expect(classifyZone(NaN, ptau217)).toBeNull();
  });

  it("returns null for Infinity", () => {
    expect(classifyZone(Infinity, ptau217)).toBeNull();
  });

  it("returns null for -Infinity", () => {
    expect(classifyZone(-Infinity, ptau217)).toBeNull();
  });

  it("returns null for value below all zones", () => {
    expect(classifyZone(-1, ptau217)).toBeNull();
  });

  it("returns null for value above all zones", () => {
    expect(classifyZone(101, ptau217)).toBeNull();
  });

  it("returns null for empty zones", () => {
    expect(classifyZone(5, empty)).toBeNull();
  });

  // Multi-zone biomarker (4 zones)
  it("classifies in 4-zone biomarker - lowest", () => {
    const result = classifyZone(15, egfr);
    expect(result!.zone.label).toBe("Severe");
  });

  it("classifies in 4-zone biomarker - middle", () => {
    const result = classifyZone(45, egfr);
    expect(result!.zone.label).toBe("Moderate");
  });

  it("classifies in 4-zone biomarker - highest", () => {
    const result = classifyZone(150, egfr);
    expect(result!.zone.label).toBe("Normal");
  });

  it("includes value and biomarker in result", () => {
    const result = classifyZone(0.5, ptau217);
    expect(result!.value).toBe(0.5);
    expect(result!.biomarker.id).toBe("ptau217");
  });
});

describe("getZoneColor", () => {
  it("returns zone color for valid value", () => {
    expect(getZoneColor(0.2, ptau217)).toBe("#5ba3c9");
    expect(getZoneColor(0.7, ptau217)).toBe("#d4a24e");
    expect(getZoneColor(2.0, ptau217)).toBe("#c75a4a");
  });

  it("returns fallback for out-of-range", () => {
    expect(getZoneColor(-5, ptau217)).toBe("#71717a");
  });

  it("returns fallback for NaN", () => {
    expect(getZoneColor(NaN, ptau217)).toBe("#71717a");
  });
});

describe("getZoneLabel", () => {
  it("returns zone label for valid value", () => {
    expect(getZoneLabel(0.2, ptau217)).toBe("Rule-out");
    expect(getZoneLabel(0.7, ptau217)).toBe("Intermediate");
    expect(getZoneLabel(2.0, ptau217)).toBe("Rule-in");
  });

  it("returns Unknown for out-of-range", () => {
    expect(getZoneLabel(-5, ptau217)).toBe("Unknown");
  });
});

describe("getZoneInterpretation", () => {
  it("returns interpretation for valid value", () => {
    expect(getZoneInterpretation(0.2, ptau217)).toBe("Amyloid unlikely");
    expect(getZoneInterpretation(2.0, ptau217)).toBe("Amyloid likely");
  });

  it("returns empty string for out-of-range", () => {
    expect(getZoneInterpretation(-5, ptau217)).toBe("");
  });
});

describe("isConcerning", () => {
  it("Rule-in is concerning", () => {
    expect(isConcerning(2.0, ptau217)).toBe(true);
  });

  it("Intermediate is concerning", () => {
    expect(isConcerning(0.7, ptau217)).toBe(true);
  });

  it("Rule-out is not concerning (matches 'rule-out' in normalLabels)", () => {
    expect(isConcerning(0.2, ptau217)).toBe(false);
  });

  it("Normal is not concerning", () => {
    expect(isConcerning(150, egfr)).toBe(false);
  });

  it("returns false for out-of-range", () => {
    expect(isConcerning(-5, ptau217)).toBe(false);
  });
});
