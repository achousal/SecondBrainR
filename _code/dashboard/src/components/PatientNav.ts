/**
 * Render the patient navigation controls.
 */
export function renderPatientNav(
  currentIndex: number,
  total: number
): string {
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex < total - 1;

  return `
    <div class="patient-nav">
      <button
        class="nav-btn"
        id="btn-prev"
        ${hasPrev ? "" : "disabled"}
        aria-label="Previous patient"
      >&lt; Prev</button>
      <span class="nav-count">
        Patient ${currentIndex + 1} of ${total}
      </span>
      <button
        class="nav-btn"
        id="btn-next"
        ${hasNext ? "" : "disabled"}
        aria-label="Next patient"
      >Next &gt;</button>
      <input
        type="text"
        id="search-patient"
        class="nav-search"
        placeholder="Search ID..."
        aria-label="Search by patient ID"
      />
    </div>
  `;
}
