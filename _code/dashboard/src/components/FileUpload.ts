/**
 * Render the file upload zone (drag-drop + file picker).
 */
export function renderFileUpload(): string {
  return `
    <div class="file-upload" id="file-upload-zone">
      <div class="file-upload-inner">
        <p class="file-upload-text">Drop CSV or Excel file here</p>
        <p class="file-upload-sub">or click to browse</p>
        <input
          type="file"
          id="file-input"
          accept=".csv,.tsv,.xlsx,.xls"
          class="file-input-hidden"
          aria-label="Upload patient data file"
        />
      </div>
    </div>
  `;
}
