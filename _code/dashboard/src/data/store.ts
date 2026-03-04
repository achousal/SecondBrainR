import type { AppState, Panel, PatientRecord, ColumnMapping, PredictionPayload } from "../types";

/**
 * Create the initial application state.
 * All state is in-memory only -- page refresh clears everything.
 */
export function createInitialState(): AppState {
  return {
    panel: null,
    patients: [],
    currentIndex: 0,
    columnMapping: {},
    predictionData: null,
  };
}

/**
 * Set the active panel.
 */
export function setPanel(state: AppState, panel: Panel): AppState {
  return { ...state, panel, patients: [], currentIndex: 0, columnMapping: {} };
}

/**
 * Set patient data after file parsing.
 */
export function setPatients(
  state: AppState,
  patients: PatientRecord[],
  mapping: ColumnMapping
): AppState {
  return { ...state, patients, columnMapping: mapping, currentIndex: 0 };
}

/**
 * Navigate to a specific patient index.
 */
export function setCurrentIndex(state: AppState, index: number): AppState {
  if (index < 0 || index >= state.patients.length) return state;
  return { ...state, currentIndex: index };
}

/**
 * Get the current patient record, or null.
 */
export function getCurrentPatient(state: AppState): PatientRecord | null {
  if (state.patients.length === 0) return null;
  return state.patients[state.currentIndex] || null;
}

/**
 * Set prediction data.
 */
export function setPredictionData(
  state: AppState,
  data: PredictionPayload | null
): AppState {
  return { ...state, predictionData: data };
}
