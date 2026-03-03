import type { PredictionPayload, PredictionResult, ShapEntry } from "../types";

/**
 * Parse and validate a prediction JSON string.
 * Throws with a descriptive message if the payload is invalid.
 */
export function parsePredictionJson(text: string): PredictionPayload {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new Error("Invalid JSON in prediction file");
  }

  if (!raw || typeof raw !== "object") {
    throw new Error("Prediction file must contain a JSON object");
  }

  const obj = raw as Record<string, unknown>;

  if (!obj.modelId || typeof obj.modelId !== "string") {
    throw new Error("Prediction payload missing 'modelId' (string)");
  }
  if (!obj.runId || typeof obj.runId !== "string") {
    throw new Error("Prediction payload missing 'runId' (string)");
  }
  if (!Array.isArray(obj.patients) || obj.patients.length === 0) {
    throw new Error("Prediction payload must have non-empty 'patients' array");
  }

  const patients: PredictionResult[] = obj.patients.map(
    (p: unknown, i: number) => validatePatientResult(p, i)
  );

  return {
    modelId: obj.modelId,
    runId: obj.runId,
    patients,
  };
}

function validatePatientResult(
  raw: unknown,
  index: number
): PredictionResult {
  if (!raw || typeof raw !== "object") {
    throw new Error(`Patient ${index}: must be an object`);
  }

  const p = raw as Record<string, unknown>;

  if (!p.patientId || typeof p.patientId !== "string") {
    throw new Error(`Patient ${index}: missing 'patientId' (string)`);
  }
  if (typeof p.probability !== "number" || p.probability < 0 || p.probability > 1) {
    throw new Error(
      `Patient ${index} (${p.patientId}): 'probability' must be a number between 0 and 1`
    );
  }
  if (!p.classification || typeof p.classification !== "string") {
    throw new Error(
      `Patient ${index} (${p.patientId}): missing 'classification' (string)`
    );
  }
  if (typeof p.baseValue !== "number") {
    throw new Error(
      `Patient ${index} (${p.patientId}): missing 'baseValue' (number)`
    );
  }
  if (!Array.isArray(p.shapValues)) {
    throw new Error(
      `Patient ${index} (${p.patientId}): 'shapValues' must be an array`
    );
  }

  const shapValues: ShapEntry[] = p.shapValues.map(
    (s: unknown, j: number) => validateShapEntry(s, j, String(p.patientId))
  );

  return {
    patientId: p.patientId,
    probability: p.probability,
    classification: p.classification,
    baseValue: p.baseValue,
    shapValues,
  };
}

function validateShapEntry(
  raw: unknown,
  index: number,
  patientId: string
): ShapEntry {
  if (!raw || typeof raw !== "object") {
    throw new Error(`${patientId} SHAP ${index}: must be an object`);
  }

  const s = raw as Record<string, unknown>;

  if (!s.feature || typeof s.feature !== "string") {
    throw new Error(`${patientId} SHAP ${index}: missing 'feature' (string)`);
  }
  if (typeof s.value !== "number") {
    throw new Error(`${patientId} SHAP ${index}: missing 'value' (number)`);
  }
  if (typeof s.shapValue !== "number") {
    throw new Error(`${patientId} SHAP ${index}: missing 'shapValue' (number)`);
  }

  return {
    feature: s.feature,
    value: s.value,
    shapValue: s.shapValue,
  };
}

/**
 * Find the prediction result for a specific patient.
 */
export function getPredictionForPatient(
  payload: PredictionPayload,
  patientId: string
): PredictionResult | null {
  return payload.patients.find((p) => p.patientId === patientId) ?? null;
}
