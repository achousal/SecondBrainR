import Papa from "papaparse";
import * as XLSX from "xlsx";
import type { PatientRecord, Panel, ColumnMapping } from "../types";
import {
  autoMapColumns,
  detectIdColumn,
  detectNameColumn,
  detectAgeColumn,
  detectSexColumn,
  detectDateColumn,
} from "./mapper";

/** Parsed result with column mapping info */
export interface ParseResult {
  patients: PatientRecord[];
  mapping: ColumnMapping;
  headers: string[];
  unmappedBiomarkers: string[];
}

/**
 * Parse a File object (CSV or Excel) and return patient records.
 */
export async function parseFile(
  file: File,
  panel: Panel
): Promise<ParseResult> {
  const ext = file.name.split(".").pop()?.toLowerCase();

  if (ext === "csv" || ext === "tsv") {
    return parseCsv(await file.text(), panel);
  }
  if (ext === "xlsx" || ext === "xls") {
    return parseExcel(await file.arrayBuffer(), panel);
  }

  throw new Error(`Unsupported file format: .${ext}. Use .csv, .tsv, .xlsx, or .xls`);
}

/**
 * Parse CSV text and return patient records mapped to a panel.
 */
export function parseCsv(text: string, panel: Panel): ParseResult {
  const result = Papa.parse<Record<string, string>>(text, {
    header: true,
    skipEmptyLines: true,
    dynamicTyping: false,
  });

  if (result.errors.length > 0) {
    const firstError = result.errors[0];
    throw new Error(`CSV parse error at row ${firstError.row}: ${firstError.message}`);
  }

  const headers = result.meta.fields || [];
  return mapToPatients(result.data, headers, panel);
}

/**
 * Parse Excel buffer and return patient records mapped to a panel.
 */
export function parseExcel(buffer: ArrayBuffer, panel: Panel): ParseResult {
  const workbook = XLSX.read(buffer, { type: "array" });
  const sheetName = workbook.SheetNames[0];
  if (!sheetName) throw new Error("Excel file has no sheets");

  const sheet = workbook.Sheets[sheetName];
  const data = XLSX.utils.sheet_to_json<Record<string, string>>(sheet, {
    defval: "",
  });

  if (data.length === 0) throw new Error("Excel sheet is empty");

  const headers = Object.keys(data[0]);
  return mapToPatients(data, headers, panel);
}

/**
 * Map raw row data to PatientRecord objects using panel config.
 */
function mapToPatients(
  rows: Record<string, string>[],
  headers: string[],
  panel: Panel
): ParseResult {
  const mapping = autoMapColumns(headers, panel.biomarkers);
  const idCol = detectIdColumn(headers);
  const nameCol = detectNameColumn(headers);
  const ageCol = detectAgeColumn(headers);
  const sexCol = detectSexColumn(headers);
  const dateCol = detectDateColumn(headers);

  const unmappedBiomarkers = panel.biomarkers
    .filter((bm) => !(bm.id in mapping))
    .map((bm) => bm.name);

  const patients: PatientRecord[] = rows.map((row, index) => {
    const values: Record<string, number | null> = {};
    for (const [biomarkerId, colHeader] of Object.entries(mapping)) {
      const raw = row[colHeader];
      const num = parseFloat(String(raw));
      values[biomarkerId] = Number.isFinite(num) ? num : null;
    }

    const id = idCol ? String(row[idCol] || `Patient_${index + 1}`) : `Patient_${index + 1}`;
    const displayName = nameCol ? String(row[nameCol] || "") : undefined;
    const age = ageCol ? parseFloat(String(row[ageCol])) : undefined;
    const sex = sexCol ? String(row[sexCol] || "") : undefined;
    const visitDate = dateCol ? String(row[dateCol] || "") : undefined;

    return {
      id,
      displayName: displayName || undefined,
      age: age && Number.isFinite(age) ? age : undefined,
      sex: sex || undefined,
      visitDate: visitDate || undefined,
      values,
    };
  });

  return { patients, mapping, headers, unmappedBiomarkers };
}
