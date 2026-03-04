/** Zone classification for a biomarker value */
export type ZoneLabel = string;

/** A single zone boundary definition */
export interface ZoneConfig {
  label: ZoneLabel;
  min: number;
  max: number;
  color: string;
  interpretation: string;
}

/** Configuration for a single biomarker within a panel */
export interface BiomarkerConfig {
  id: string;
  name: string;
  unit: string;
  aliases: string[];
  zones: ZoneConfig[];
  source?: string;
  notes?: string;
}

/** A panel groups related biomarkers for a specific clinical context */
export interface Panel {
  id: string;
  name: string;
  version: string;
  description: string;
  biomarkers: BiomarkerConfig[];
}

/** Column mapping from CSV/Excel headers to panel biomarker IDs */
export interface ColumnMapping {
  [biomarkerId: string]: string; // biomarker id -> column header
}

/** A single patient's data row */
export interface PatientRecord {
  id: string;
  displayName?: string;
  age?: number;
  sex?: string;
  visitDate?: string;
  values: Record<string, number | null>;
}

/** Zone classification result for a single value */
export interface ZoneResult {
  zone: ZoneConfig;
  value: number;
  biomarker: BiomarkerConfig;
}

/** Application state (in-memory only, no persistence) */
export interface AppState {
  panel: Panel | null;
  patients: PatientRecord[];
  currentIndex: number;
  columnMapping: ColumnMapping;
  predictionData: PredictionPayload | null;
}

// -- Phase 2: Prediction interfaces (stubs for future ML integration) --

/** SHAP value for a single feature */
export interface ShapEntry {
  feature: string;
  value: number;
  shapValue: number;
}

/** Prediction result for a single patient */
export interface PredictionResult {
  patientId: string;
  probability: number;
  classification: string;
  shapValues: ShapEntry[];
  baseValue: number;
}

/** Full prediction payload from ML pipeline */
export interface PredictionPayload {
  modelId: string;
  runId: string;
  patients: PredictionResult[];
}

/** Dashboard branding configuration */
export interface DashboardConfig {
  title: string;
  institution: string;
  logoSvg?: string;
  disclaimer: string;
  footer: string;
}
