import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";
import {
  parsePredictionJson,
  getPredictionForPatient,
} from "../data/prediction_loader";

const FIXTURE_PATH = resolve(__dirname, "fixtures/sample_predictions.json");
const fixtureText = readFileSync(FIXTURE_PATH, "utf-8");

describe("parsePredictionJson", () => {
  it("parses valid fixture", () => {
    const payload = parsePredictionJson(fixtureText);
    expect(payload.modelId).toBe("ad_classifier_v2");
    expect(payload.runId).toBe("run_20260215");
    expect(payload.patients).toHaveLength(3);
  });

  it("parses patient fields correctly", () => {
    const payload = parsePredictionJson(fixtureText);
    const p1 = payload.patients[0];
    expect(p1.patientId).toBe("P001");
    expect(p1.probability).toBe(0.87);
    expect(p1.classification).toBe("AD Positive");
    expect(p1.baseValue).toBe(0.35);
    expect(p1.shapValues).toHaveLength(5);
  });

  it("parses SHAP entries correctly", () => {
    const payload = parsePredictionJson(fixtureText);
    const shap = payload.patients[0].shapValues[0];
    expect(shap.feature).toBe("ptau217");
    expect(shap.value).toBe(2.34);
    expect(shap.shapValue).toBe(0.28);
  });

  it("throws on invalid JSON", () => {
    expect(() => parsePredictionJson("not json")).toThrow("Invalid JSON");
  });

  it("throws on non-object", () => {
    expect(() => parsePredictionJson('"string"')).toThrow("JSON object");
  });

  it("throws on missing modelId", () => {
    expect(() =>
      parsePredictionJson(JSON.stringify({ runId: "x", patients: [{}] }))
    ).toThrow("modelId");
  });

  it("throws on missing runId", () => {
    expect(() =>
      parsePredictionJson(JSON.stringify({ modelId: "x", patients: [{}] }))
    ).toThrow("runId");
  });

  it("throws on empty patients", () => {
    expect(() =>
      parsePredictionJson(
        JSON.stringify({ modelId: "x", runId: "y", patients: [] })
      )
    ).toThrow("non-empty");
  });

  it("throws on missing patientId", () => {
    expect(() =>
      parsePredictionJson(
        JSON.stringify({
          modelId: "x",
          runId: "y",
          patients: [{ probability: 0.5, classification: "X", baseValue: 0.3, shapValues: [] }],
        })
      )
    ).toThrow("patientId");
  });

  it("throws on probability out of range", () => {
    expect(() =>
      parsePredictionJson(
        JSON.stringify({
          modelId: "x",
          runId: "y",
          patients: [
            {
              patientId: "P1",
              probability: 1.5,
              classification: "X",
              baseValue: 0.3,
              shapValues: [],
            },
          ],
        })
      )
    ).toThrow("probability");
  });

  it("throws on missing classification", () => {
    expect(() =>
      parsePredictionJson(
        JSON.stringify({
          modelId: "x",
          runId: "y",
          patients: [
            {
              patientId: "P1",
              probability: 0.5,
              baseValue: 0.3,
              shapValues: [],
            },
          ],
        })
      )
    ).toThrow("classification");
  });

  it("throws on invalid SHAP entry", () => {
    expect(() =>
      parsePredictionJson(
        JSON.stringify({
          modelId: "x",
          runId: "y",
          patients: [
            {
              patientId: "P1",
              probability: 0.5,
              classification: "X",
              baseValue: 0.3,
              shapValues: [{ feature: "f1" }],
            },
          ],
        })
      )
    ).toThrow("value");
  });
});

describe("getPredictionForPatient", () => {
  const payload = parsePredictionJson(fixtureText);

  it("finds patient by ID", () => {
    const result = getPredictionForPatient(payload, "P001");
    expect(result).not.toBeNull();
    expect(result!.probability).toBe(0.87);
  });

  it("finds second patient", () => {
    const result = getPredictionForPatient(payload, "P002");
    expect(result).not.toBeNull();
    expect(result!.probability).toBe(0.15);
  });

  it("returns null for unknown patient", () => {
    expect(getPredictionForPatient(payload, "UNKNOWN")).toBeNull();
  });

  it("returns null for empty string", () => {
    expect(getPredictionForPatient(payload, "")).toBeNull();
  });
});
