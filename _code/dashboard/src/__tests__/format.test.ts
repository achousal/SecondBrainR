import { describe, it, expect } from "vitest";
import { formatValue, formatWithUnit, formatPatientId } from "../utils/format";

describe("formatValue", () => {
  // Standard ranges
  it("formats values >= 100 with no decimals", () => {
    expect(formatValue(142)).toBe("142");
    expect(formatValue(1000)).toBe("1000");
    expect(formatValue(999.9)).toBe("1000");
  });

  it("formats values >= 10 with 1 decimal", () => {
    expect(formatValue(22.5)).toBe("22.5");
    expect(formatValue(10.0)).toBe("10.0");
    expect(formatValue(99.99)).toBe("100.0");
  });

  it("formats values >= 1 with 2 decimals", () => {
    expect(formatValue(2.34)).toBe("2.34");
    expect(formatValue(1.0)).toBe("1.00");
    expect(formatValue(9.999)).toBe("10.00");
  });

  it("formats values >= 0.01 with 3 decimals", () => {
    expect(formatValue(0.062)).toBe("0.062");
    expect(formatValue(0.01)).toBe("0.010");
  });

  it("formats values < 0.01 in scientific notation", () => {
    expect(formatValue(0.005)).toBe("5.00e-3");
    expect(formatValue(0.001)).toBe("1.00e-3");
    expect(formatValue(0.0001)).toBe("1.00e-4");
  });

  // Edge cases
  it("formats zero", () => {
    expect(formatValue(0)).toBe("0");
  });

  it("returns -- for null", () => {
    expect(formatValue(null)).toBe("--");
  });

  it("returns -- for undefined", () => {
    expect(formatValue(undefined)).toBe("--");
  });

  it("returns -- for NaN", () => {
    expect(formatValue(NaN)).toBe("--");
  });

  it("returns -- for Infinity", () => {
    expect(formatValue(Infinity)).toBe("--");
  });

  // Negative values
  it("formats negative values", () => {
    expect(formatValue(-5.5)).toBe("-5.50");
    expect(formatValue(-150)).toBe("-150");
    expect(formatValue(-0.05)).toBe("-0.050");
  });
});

describe("formatWithUnit", () => {
  it("appends unit to formatted value", () => {
    expect(formatWithUnit(2.34, "pg/mL")).toBe("2.34 pg/mL");
  });

  it("omits unit for ratio", () => {
    expect(formatWithUnit(0.062, "ratio")).toBe("0.062");
  });

  it("omits unit for empty string", () => {
    expect(formatWithUnit(5.5, "")).toBe("5.50");
  });

  it("returns -- for null regardless of unit", () => {
    expect(formatWithUnit(null, "pg/mL")).toBe("--");
  });
});

describe("formatPatientId", () => {
  it("returns ID as-is when short", () => {
    expect(formatPatientId("P001")).toBe("P001");
  });

  it("truncates long IDs", () => {
    const longId = "VERY_LONG_PATIENT_IDENTIFIER_12345";
    const result = formatPatientId(longId, 20);
    expect(result.length).toBe(20);
    expect(result.endsWith("...")).toBe(true);
  });

  it("returns Unknown for empty string", () => {
    expect(formatPatientId("")).toBe("Unknown");
  });

  it("handles exact maxLength", () => {
    expect(formatPatientId("12345678901234567890", 20)).toBe("12345678901234567890");
  });
});
