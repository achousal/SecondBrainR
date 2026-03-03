import type { PatientRecord } from "../types";
import { formatPatientId } from "../utils/format";

/**
 * Render the patient header showing demographics.
 */
export function renderPatientHeader(patient: PatientRecord): string {
  const name = patient.displayName || formatPatientId(patient.id);
  const parts = [name];

  if (patient.age !== undefined) {
    parts.push(`Age: ${patient.age}`);
  }
  if (patient.sex) {
    parts.push(`Sex: ${patient.sex}`);
  }
  if (patient.visitDate) {
    parts.push(`Visit: ${patient.visitDate}`);
  }

  return `
    <div class="patient-header">
      ${parts.map((p, i) => `<span class="patient-header-item">${p}</span>${i < parts.length - 1 ? '<span class="patient-header-sep">|</span>' : ""}`).join("")}
    </div>
  `;
}
