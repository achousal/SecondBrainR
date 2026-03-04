import "./styles/tokens.css";
import "./styles/layout.css";
import "./styles/gauge.css";
import "./styles/prediction.css";

import type { AppState, DashboardConfig, Panel, PatientRecord } from "./types";
import { loadPanels, getPanelById } from "./config/reference_ranges";
import { loadBranding } from "./config/branding";
import { parseFile } from "./data/parser";
import { parsePredictionJson, getPredictionForPatient } from "./data/prediction_loader";
import {
  createInitialState,
  setPanel,
  setPatients,
  setCurrentIndex,
  getCurrentPatient,
  setPredictionData,
} from "./data/store";

import { renderPanelSelector } from "./components/PanelSelector";
import { renderFileUpload } from "./components/FileUpload";
import { renderPatientHeader } from "./components/PatientHeader";
import { renderPatientNav } from "./components/PatientNav";
import { renderGaugeCard } from "./components/GaugeCard";
import { renderSummaryStrip } from "./components/SummaryStrip";
import { renderPredictionPanel } from "./components/PredictionPanel";
import { printDashboard } from "./utils/print";

let state: AppState = createInitialState();
let panels: Panel[] = [];
let branding: DashboardConfig;

function render(): void {
  const app = document.getElementById("app");
  if (!app) return;

  const patient = getCurrentPatient(state);

  // Top bar
  const institutionBadge = branding.institution
    ? `<span class="dashboard-institution">${branding.institution}</span>`
    : "";
  const topbar = `
    <div class="dashboard-topbar">
      <span class="dashboard-title">${branding.title}</span>
      ${institutionBadge}
      ${renderPanelSelector(panels, state.panel?.id ?? null)}
      <div class="topbar-spacer"></div>
      ${state.panel ? '<label class="btn-action" for="file-input-main">Upload CSV</label><input type="file" id="file-input-main" accept=".csv,.tsv,.xlsx,.xls" class="file-input-hidden" />' : ""}
      ${patient ? '<label class="btn-action" for="prediction-input">Load Predictions</label><input type="file" id="prediction-input" accept=".json" class="file-input-hidden" />' : ""}
      ${patient ? '<button id="btn-print" class="btn-action">Print</button>' : ""}
    </div>
  `;

  // Patient area
  let content = "";
  if (!state.panel) {
    content = '<div class="empty-state">Select a biomarker panel to begin.</div>';
  } else if (state.patients.length === 0) {
    content = renderFileUpload();
  } else if (patient) {
    const header = renderPatientHeader(patient);
    const nav = renderPatientNav(state.currentIndex, state.patients.length);

    const gauges = state.panel.biomarkers
      .map((bm) => renderGaugeCard(patient.values[bm.id] ?? null, bm))
      .join("");

    const summary = renderSummaryStrip(patient, state.panel);
    const predictionResult = state.predictionData
      ? getPredictionForPatient(state.predictionData, patient.id)
      : null;
    const prediction = renderPredictionPanel(predictionResult);

    const disclaimer = branding.disclaimer
      ? `<div class="dashboard-disclaimer">${branding.disclaimer}</div>`
      : "";

    content = `
      ${header}
      ${nav}
      <div class="gauge-grid">${gauges}</div>
      ${prediction}
      ${disclaimer}
      ${summary}
    `;
  }

  const footer = branding.footer
    ? `<div class="dashboard-footer">${branding.footer}</div>`
    : "";

  app.innerHTML = topbar + content + footer;
  bindEvents();
}

function bindEvents(): void {
  // Panel selector
  const selector = document.getElementById("panel-selector") as HTMLSelectElement | null;
  selector?.addEventListener("change", () => {
    const panel = getPanelById(panels, selector.value);
    if (panel) {
      state = setPanel(state, panel);
      render();
    }
  });

  // File upload (top bar)
  const fileInputMain = document.getElementById("file-input-main") as HTMLInputElement | null;
  fileInputMain?.addEventListener("change", handleFileUpload);

  // File upload (drop zone)
  const fileInput = document.getElementById("file-input") as HTMLInputElement | null;
  fileInput?.addEventListener("change", handleFileUpload);

  const dropZone = document.getElementById("file-upload-zone");
  if (dropZone) {
    dropZone.addEventListener("click", () => fileInput?.click());
    dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropZone.classList.add("drag-over");
    });
    dropZone.addEventListener("dragleave", () => {
      dropZone.classList.remove("drag-over");
    });
    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.classList.remove("drag-over");
      const file = (e as DragEvent).dataTransfer?.files[0];
      if (file) processFile(file);
    });
  }

  // Patient navigation
  document.getElementById("btn-prev")?.addEventListener("click", () => {
    state = setCurrentIndex(state, state.currentIndex - 1);
    render();
  });
  document.getElementById("btn-next")?.addEventListener("click", () => {
    state = setCurrentIndex(state, state.currentIndex + 1);
    render();
  });

  // Patient search
  const searchInput = document.getElementById("search-patient") as HTMLInputElement | null;
  searchInput?.addEventListener("input", () => {
    const query = searchInput.value.toLowerCase().trim();
    if (!query) return;
    const idx = state.patients.findIndex(
      (p) =>
        p.id.toLowerCase().includes(query) ||
        (p.displayName?.toLowerCase().includes(query) ?? false)
    );
    if (idx >= 0) {
      state = setCurrentIndex(state, idx);
      render();
    }
  });

  // Prediction upload
  const predictionInput = document.getElementById("prediction-input") as HTMLInputElement | null;
  predictionInput?.addEventListener("change", handlePredictionUpload);

  // Print button
  document.getElementById("btn-print")?.addEventListener("click", printDashboard);
}

async function handleFileUpload(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) await processFile(file);
}

async function processFile(file: File): Promise<void> {
  if (!state.panel) return;

  try {
    const result = await parseFile(file, state.panel);
    state = setPatients(state, result.patients, result.mapping);

    if (result.unmappedBiomarkers.length > 0) {
      // For now, proceed with partial mapping and log unmapped biomarkers
      const msg = `Note: ${result.unmappedBiomarkers.length} biomarker(s) not found in file: ${result.unmappedBiomarkers.join(", ")}`;
      showMessage(msg, "warning");
    }

    render();
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to parse file";
    showError(message);
  }
}

async function handlePredictionUpload(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  try {
    const text = await file.text();
    const payload = parsePredictionJson(text);
    state = setPredictionData(state, payload);
    showMessage(`Loaded predictions: ${payload.patients.length} patient(s) from ${payload.modelId}`, "info");
    render();
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to parse predictions";
    showError(message);
  }
}

function showError(message: string): void {
  const app = document.getElementById("app");
  if (!app) return;
  const errorDiv = document.createElement("div");
  errorDiv.className = "error-message";
  errorDiv.textContent = message;
  app.appendChild(errorDiv);
  setTimeout(() => errorDiv.remove(), 5000);
}

function showMessage(message: string, _type: "warning" | "info" = "info"): void {
  const app = document.getElementById("app");
  if (!app) return;
  const msgDiv = document.createElement("div");
  msgDiv.className = "error-message";
  msgDiv.style.borderColor = "var(--color-accent)";
  msgDiv.style.color = "var(--color-accent)";
  msgDiv.textContent = message;
  app.appendChild(msgDiv);
  setTimeout(() => msgDiv.remove(), 5000);
}

// Initialize
try {
  panels = loadPanels();
  branding = loadBranding();
} catch (err) {
  const message = err instanceof Error ? err.message : "Failed to load panels";
  document.body.innerHTML = `<div class="error-message">${message}</div>`;
  throw err;
}

render();
