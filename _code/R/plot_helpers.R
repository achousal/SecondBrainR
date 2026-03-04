# plot_helpers.R -- Axis helpers and save utilities
#
# Provides y-axis scale helpers and an extended save_plot().
#
# Depends on: ggplot2, palettes.R (for canonical color definitions)

# -- Y-axis helpers ------------------------------------------------------------

#' Auto-range y-axis (for scatter plots)
#'
#' No forced zero; tight padding (2% below, 5% above).
#'
#' @return A ggplot2 scale_y_continuous object.
#' @export
scale_y_auto <- function() {
  ggplot2::scale_y_continuous(expand = ggplot2::expansion(mult = c(0.02, 0.05)))
}

#' Zero-floor y-axis (for box/violin plots)
#'
#' Forces y = 0 as the lower bound with configurable expand padding.
#'
#' @param expand_mult Multiplicative expansion (default c(0.05, 0.25)
#'   for violin; use c(0, 0.10) for box).
#' @return A ggplot2 scale_y_continuous object.
#' @export
scale_y_zero <- function(expand_mult = c(0.05, 0.25)) {
  ggplot2::scale_y_continuous(
    limits = c(0, NA),
    expand = ggplot2::expansion(mult = expand_mult)
  )
}

# -- Save helper ---------------------------------------------------------------

#' Save a plot with canonical defaults
#'
#' Defaults to PDF (vector). Supports "pdf", "png", "svg", "tiff".
#' Optionally writes a sidecar _pvalues.txt file alongside the figure.
#'
#' @param plot A ggplot object.
#' @param path Output file path (extension determines format if fmt is NULL).
#' @param width Width in inches (default 10).
#' @param height Height in inches (default 6).
#' @param fmt Output format: "pdf" (default), "png", "svg", "tiff".
#'   If NULL, inferred from file extension.
#' @param dpi Resolution for raster formats (default 300).
#' @param pvalues Optional: named numeric vector or data.frame of p-values
#'   to save as a sidecar file.
#' @export
save_plot <- function(plot, path, width = 10, height = 6,
                      fmt = "pdf", dpi = 300, pvalues = NULL) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)

  # Infer device from format
  device <- if (!is.null(fmt)) fmt else tools::file_ext(path)
  if (device == "") device <- "pdf"

  ggplot2::ggsave(
    filename = path,
    plot = plot,
    width = width,
    height = height,
    device = device,
    dpi = dpi
  )
  message("Saved plot: ", path)

  # Sidecar p-values
  if (!is.null(pvalues)) {
    sidecar <- sub("\\.[^.]+$", "_pvalues.txt", path)
    if (is.data.frame(pvalues)) {
      utils::write.table(pvalues, sidecar, sep = "\t", row.names = FALSE,
                         quote = FALSE)
    } else {
      lines <- paste(names(pvalues), sapply(pvalues, function(p) {
        if (p < 0.001) "p < 0.001" else sprintf("p = %.3f", p)
      }), sep = "\t")
      writeLines(lines, sidecar)
    }
    message("Saved p-values: ", sidecar)
  }
}
