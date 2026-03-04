/**
 * Trigger the browser print dialog.
 * In non-browser environments, this is a no-op.
 */
export function printDashboard(): void {
  if (typeof window !== "undefined" && window.print) {
    window.print();
  }
}
