import Ajv from "ajv";
import { readFileSync, readdirSync, existsSync } from "fs";
import { join, resolve } from "path";

const SCHEMA_PATH = resolve(import.meta.dirname, "../schemas/panel.schema.json");
const PROFILE_PANELS_DIR = resolve(import.meta.dirname, "../../profiles");
const LOCAL_PANELS_DIR = resolve(import.meta.dirname, "../src/config/panels");

function loadSchema(): object {
  const raw = readFileSync(SCHEMA_PATH, "utf-8");
  return JSON.parse(raw);
}

function findPanelFiles(dir: string): string[] {
  if (!existsSync(dir)) return [];

  const files: string[] = [];
  const entries = readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      // Check for panels/ subdirectory in profile directories
      const panelsDir = join(fullPath, "panels");
      if (existsSync(panelsDir)) {
        const panelFiles = readdirSync(panelsDir);
        for (const f of panelFiles) {
          if (f.endsWith(".json")) {
            files.push(join(panelsDir, f));
          }
        }
      }
    } else if (entry.name.endsWith(".json")) {
      files.push(fullPath);
    }
  }

  return files;
}

function main(): void {
  const schema = loadSchema();
  const ajv = new Ajv({ allErrors: true });
  const validate = ajv.compile(schema);

  const panelFiles = [
    ...findPanelFiles(PROFILE_PANELS_DIR),
    ...findPanelFiles(LOCAL_PANELS_DIR),
  ];

  if (panelFiles.length === 0) {
    console.error("No panel files found");
    process.exit(1);
  }

  let hasErrors = false;
  const seen = new Set<string>();

  for (const filePath of panelFiles) {
    const raw = readFileSync(filePath, "utf-8");
    let panel: Record<string, unknown>;

    try {
      panel = JSON.parse(raw);
    } catch {
      console.error(`[FAIL] ${filePath}: invalid JSON`);
      hasErrors = true;
      continue;
    }

    const valid = validate(panel);
    if (!valid) {
      console.error(`[FAIL] ${filePath}:`);
      for (const err of validate.errors || []) {
        console.error(`  ${err.instancePath || "/"}: ${err.message}`);
      }
      hasErrors = true;
    } else {
      const id = panel.id as string;
      if (seen.has(id)) {
        // Duplicate from profile overriding local -- OK, just note it
        console.log(`[NOTE] ${filePath}: panel "${id}" overrides local fallback`);
      } else {
        console.log(`[PASS] ${filePath}: panel "${id}"`);
      }
      seen.add(id);
    }
  }

  if (hasErrors) {
    console.error("\nPanel validation failed.");
    process.exit(1);
  }

  console.log(`\n${panelFiles.length} panel(s) validated successfully.`);
}

main();
