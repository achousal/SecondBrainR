import { describe, it, expect } from "vitest";
import {
  normalizeHeader,
  autoMapColumns,
  detectIdColumn,
  detectNameColumn,
  detectAgeColumn,
  detectSexColumn,
  detectDateColumn,
  getUnmappedBiomarkers,
} from "../data/mapper";
import type { BiomarkerConfig } from "../types";

const sampleBiomarkers: BiomarkerConfig[] = [
  {
    id: "ptau217",
    name: "p-tau 217",
    unit: "pg/mL",
    aliases: ["ptau217", "p-tau217", "ptau_217", "p_tau_217"],
    zones: [],
  },
  {
    id: "nfl",
    name: "NfL",
    unit: "pg/mL",
    aliases: ["nfl", "neurofilament", "nfl_plasma"],
    zones: [],
  },
  {
    id: "gfap",
    name: "GFAP",
    unit: "pg/mL",
    aliases: ["gfap", "glial_fibrillary"],
    zones: [],
  },
];

describe("normalizeHeader", () => {
  it("lowercases and strips non-alphanumeric", () => {
    expect(normalizeHeader("P-tau_217")).toBe("ptau217");
  });

  it("handles spaces", () => {
    expect(normalizeHeader("Ab 42 / Ab 40")).toBe("ab42ab40");
  });

  it("handles all caps", () => {
    expect(normalizeHeader("GFAP")).toBe("gfap");
  });

  it("handles empty string", () => {
    expect(normalizeHeader("")).toBe("");
  });

  it("handles already normalized", () => {
    expect(normalizeHeader("nfl")).toBe("nfl");
  });

  it("strips dots and special chars", () => {
    expect(normalizeHeader("hs.CRP (mg/L)")).toBe("hscrpmgl");
  });
});

describe("detectIdColumn", () => {
  it("detects patient_id", () => {
    expect(detectIdColumn(["patient_id", "ptau217", "nfl"])).toBe("patient_id");
  });

  it("detects ID (case insensitive)", () => {
    expect(detectIdColumn(["ID", "ptau217"])).toBe("ID");
  });

  it("detects subject_id", () => {
    expect(detectIdColumn(["subject_id", "ptau217"])).toBe("subject_id");
  });

  it("detects eid", () => {
    expect(detectIdColumn(["eid", "ptau217"])).toBe("eid");
  });

  it("returns null when no ID column", () => {
    expect(detectIdColumn(["ptau217", "nfl"])).toBeNull();
  });
});

describe("detectNameColumn", () => {
  it("detects name", () => {
    expect(detectNameColumn(["name", "age"])).toBe("name");
  });

  it("detects display_name", () => {
    expect(detectNameColumn(["display_name", "age"])).toBe("display_name");
  });

  it("returns null when no name column", () => {
    expect(detectNameColumn(["id", "ptau217"])).toBeNull();
  });
});

describe("detectAgeColumn", () => {
  it("detects age", () => {
    expect(detectAgeColumn(["age", "sex"])).toBe("age");
  });

  it("detects age_at_visit", () => {
    expect(detectAgeColumn(["age_at_visit", "sex"])).toBe("age_at_visit");
  });

  it("returns null when no age column", () => {
    expect(detectAgeColumn(["id", "ptau217"])).toBeNull();
  });
});

describe("detectSexColumn", () => {
  it("detects sex", () => {
    expect(detectSexColumn(["sex", "age"])).toBe("sex");
  });

  it("detects gender", () => {
    expect(detectSexColumn(["gender", "age"])).toBe("gender");
  });

  it("returns null when no sex column", () => {
    expect(detectSexColumn(["id", "ptau217"])).toBeNull();
  });
});

describe("detectDateColumn", () => {
  it("detects visit_date", () => {
    expect(detectDateColumn(["visit_date", "age"])).toBe("visit_date");
  });

  it("detects date", () => {
    expect(detectDateColumn(["date", "age"])).toBe("date");
  });

  it("returns null when no date column", () => {
    expect(detectDateColumn(["id", "ptau217"])).toBeNull();
  });
});

describe("autoMapColumns", () => {
  it("maps exact match columns", () => {
    const headers = ["patient_id", "ptau217", "nfl", "gfap"];
    const mapping = autoMapColumns(headers, sampleBiomarkers);
    expect(mapping).toEqual({
      ptau217: "ptau217",
      nfl: "nfl",
      gfap: "gfap",
    });
  });

  it("maps alias match (case insensitive, stripped)", () => {
    const headers = ["ID", "p-tau_217", "Neurofilament", "GFAP"];
    const mapping = autoMapColumns(headers, sampleBiomarkers);
    expect(mapping["ptau217"]).toBe("p-tau_217");
    expect(mapping["nfl"]).toBe("Neurofilament");
    expect(mapping["gfap"]).toBe("GFAP");
  });

  it("handles partial match (only some biomarkers)", () => {
    const headers = ["patient_id", "ptau217"];
    const mapping = autoMapColumns(headers, sampleBiomarkers);
    expect(mapping).toEqual({ ptau217: "ptau217" });
    expect(mapping["nfl"]).toBeUndefined();
    expect(mapping["gfap"]).toBeUndefined();
  });

  it("handles no matches", () => {
    const headers = ["column_a", "column_b"];
    const mapping = autoMapColumns(headers, sampleBiomarkers);
    expect(Object.keys(mapping)).toHaveLength(0);
  });

  it("handles empty headers", () => {
    const mapping = autoMapColumns([], sampleBiomarkers);
    expect(Object.keys(mapping)).toHaveLength(0);
  });

  it("handles empty biomarkers", () => {
    const mapping = autoMapColumns(["ptau217"], []);
    expect(Object.keys(mapping)).toHaveLength(0);
  });
});

describe("getUnmappedBiomarkers", () => {
  it("returns biomarkers not in mapping", () => {
    const mapping = { ptau217: "ptau217" };
    const unmapped = getUnmappedBiomarkers(mapping, sampleBiomarkers);
    expect(unmapped).toHaveLength(2);
    expect(unmapped.map((b) => b.id)).toEqual(["nfl", "gfap"]);
  });

  it("returns empty when all mapped", () => {
    const mapping = { ptau217: "ptau217", nfl: "nfl", gfap: "gfap" };
    const unmapped = getUnmappedBiomarkers(mapping, sampleBiomarkers);
    expect(unmapped).toHaveLength(0);
  });

  it("returns all when none mapped", () => {
    const unmapped = getUnmappedBiomarkers({}, sampleBiomarkers);
    expect(unmapped).toHaveLength(3);
  });
});
