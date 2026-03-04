# plot_builders.R -- Standard plot builder functions
#
# Each builder returns a ggplot object with theme_research() applied.
# Uses canonical palettes from palettes.R and sizes from theme_research.R.
# Depends on: ggplot2, theme_research.R, palettes.R

# -- Violin plot ---------------------------------------------------------------

#' Build a violin + jitter plot
#'
#' @param data Data frame.
#' @param x Unquoted column for x-axis (categorical).
#' @param y Unquoted column for y-axis (numeric).
#' @param fill Unquoted column for fill (optional).
#' @param title Plot title (optional).
#' @param palette Named character vector of colors (optional).
#' @param base_size Base font size (default 14).
#' @return A ggplot object.
#' @export
build_violin <- function(data, x, y, fill = NULL,
                         title = NULL, palette = NULL,
                         base_size = 14) {
  p <- ggplot2::ggplot(data, ggplot2::aes(
    x = {{ x }}, y = {{ y }}, fill = {{ fill }}
  )) +
    ggplot2::geom_violin(alpha = 0.6, trim = FALSE) +
    ggplot2::geom_jitter(width = 0.15, size = 1, alpha = 0.5) +
    theme_research(base_size = base_size)

  if (!is.null(title)) {
    p <- p + ggplot2::ggtitle(title)
  }
  if (!is.null(palette)) {
    p <- p + ggplot2::scale_fill_manual(values = palette)
  }
  p
}

# -- Box plot ------------------------------------------------------------------

#' Build a box + jitter plot
#'
#' @param data Data frame.
#' @param x Unquoted column for x-axis (categorical).
#' @param y Unquoted column for y-axis (numeric).
#' @param fill Unquoted column for fill (optional).
#' @param title Plot title (optional).
#' @param palette Named character vector of colors (optional).
#' @param base_size Base font size (default 14).
#' @return A ggplot object.
#' @export
build_box <- function(data, x, y, fill = NULL,
                      title = NULL, palette = NULL,
                      base_size = 14) {
  p <- ggplot2::ggplot(data, ggplot2::aes(
    x = {{ x }}, y = {{ y }}, fill = {{ fill }}
  )) +
    ggplot2::geom_boxplot(outlier.shape = NA, alpha = 0.6) +
    ggplot2::geom_jitter(width = 0.15, size = 1, alpha = 0.5) +
    theme_research(base_size = base_size)

  if (!is.null(title)) {
    p <- p + ggplot2::ggtitle(title)
  }
  if (!is.null(palette)) {
    p <- p + ggplot2::scale_fill_manual(values = palette)
  }
  p
}

# -- Scatter plot --------------------------------------------------------------

#' Build a scatter plot with optional regression line
#'
#' @param data Data frame.
#' @param x Unquoted column for x-axis.
#' @param y Unquoted column for y-axis.
#' @param color Unquoted column for color (optional).
#' @param title Plot title (optional).
#' @param palette Named character vector of colors (optional).
#' @param add_lm Logical: add a linear regression line (default FALSE).
#' @param base_size Base font size (default 14).
#' @return A ggplot object.
#' @export
build_scatter <- function(data, x, y, color = NULL,
                          title = NULL, palette = NULL,
                          add_lm = FALSE, base_size = 14) {
  p <- ggplot2::ggplot(data, ggplot2::aes(
    x = {{ x }}, y = {{ y }}, colour = {{ color }}
  )) +
    ggplot2::geom_point(alpha = 0.6, size = 2) +
    theme_research(base_size = base_size)

  if (add_lm) {
    p <- p + ggplot2::geom_smooth(method = "lm", se = TRUE, alpha = 0.2)
  }
  if (!is.null(title)) {
    p <- p + ggplot2::ggtitle(title)
  }
  if (!is.null(palette)) {
    p <- p + ggplot2::scale_colour_manual(values = palette)
  }
  p
}

# -- Heatmap -------------------------------------------------------------------

#' Build a correlation/expression heatmap
#'
#' @param mat Numeric matrix (rownames and colnames used as labels).
#' @param title Plot title (optional).
#' @param palette Diverging palette name (default "RdBu" from DIVERGING_PALETTE).
#' @param limits Numeric vector of length 2 for color scale limits
#'   (default symmetric around 0).
#' @param base_size Base font size (default 14).
#' @return A ggplot object.
#' @export
build_heatmap <- function(mat, title = NULL, palette = NULL,
                          limits = NULL, base_size = 14) {
  if (is.null(palette)) palette <- DIVERGING_PALETTE
  if (is.null(limits)) {
    finite_vals <- mat[is.finite(mat)]
    if (length(finite_vals) == 0) {
      limits <- c(-1, 1)
    } else {
      max_abs <- max(abs(finite_vals))
      limits <- c(-max_abs, max_abs)
    }
  }

  df <- data.frame(
    row = rep(rownames(mat), ncol(mat)),
    col = rep(colnames(mat), each = nrow(mat)),
    value = as.vector(mat),
    stringsAsFactors = FALSE
  )

  p <- ggplot2::ggplot(df, ggplot2::aes(x = col, y = row, fill = value)) +
    ggplot2::geom_tile(color = "white") +
    ggplot2::scale_fill_distiller(
      palette = palette, limits = limits, direction = -1
    ) +
    ggplot2::coord_equal() +
    theme_research(base_size = base_size) +
    ggplot2::theme(
      axis.text.x = ggplot2::element_text(angle = 45, hjust = 1),
      axis.title = ggplot2::element_blank()
    )

  if (!is.null(title)) {
    p <- p + ggplot2::ggtitle(title)
  }
  p
}

# -- Volcano plot --------------------------------------------------------------

#' Build a volcano plot for differential expression
#'
#' @param data Data frame with columns for log2 fold change and p-value.
#' @param x Unquoted column for log2 fold change.
#' @param y Unquoted column for p-value (will be -log10 transformed).
#' @param color Unquoted column for direction category (optional).
#' @param title Plot title (optional).
#' @param fc_thresh Fold change threshold for vertical lines (default 1).
#' @param p_thresh P-value threshold for horizontal line (default 0.05).
#' @param base_size Base font size (default 14).
#' @return A ggplot object.
#' @export
build_volcano <- function(data, x, y, color = NULL,
                          title = NULL,
                          fc_thresh = 1, p_thresh = 0.05,
                          base_size = 14) {
  y_vals <- rlang::eval_tidy(rlang::enquo(y), data)
  if (any(y_vals <= 0, na.rm = TRUE)) {
    warning("Non-positive p-values detected; clamping to .Machine$double.xmin before -log10 transform")
    data <- dplyr::mutate(data, !!rlang::enquo(y) := pmax(!!rlang::enquo(y), .Machine$double.xmin))
  }
  p <- ggplot2::ggplot(data, ggplot2::aes(
    x = {{ x }},
    y = -log10({{ y }}),
    colour = {{ color }}
  )) +
    ggplot2::geom_point(alpha = 0.5, size = 1.5) +
    ggplot2::geom_hline(
      yintercept = -log10(p_thresh), linetype = "dashed", color = "grey50"
    ) +
    ggplot2::geom_vline(
      xintercept = c(-fc_thresh, fc_thresh),
      linetype = "dashed", color = "grey50"
    ) +
    ggplot2::scale_colour_manual(values = DIRECTION_COLORS) +
    ggplot2::labs(y = expression(-log[10](p))) +
    theme_research(base_size = base_size)

  if (!is.null(title)) {
    p <- p + ggplot2::ggtitle(title)
  }
  p
}

# -- Forest plot ---------------------------------------------------------------

#' Build a forest plot for effect sizes with confidence intervals
#'
#' @param data Data frame with columns: label, estimate, ci_lower, ci_upper.
#' @param title Plot title (optional).
#' @param null_value Value for null effect line (default 0).
#' @param base_size Base font size (default 14).
#' @return A ggplot object.
#' @export
build_forest <- function(data, title = NULL,
                         null_value = 0, base_size = 14) {
  p <- ggplot2::ggplot(data, ggplot2::aes(
    x = estimate, y = stats::reorder(label, estimate),
    xmin = ci_lower, xmax = ci_upper
  )) +
    ggplot2::geom_pointrange(size = 0.5) +
    ggplot2::geom_vline(
      xintercept = null_value, linetype = "dashed", color = "grey50"
    ) +
    ggplot2::labs(y = NULL) +
    theme_research(base_size = base_size)

  if (!is.null(title)) {
    p <- p + ggplot2::ggtitle(title)
  }
  p
}

# -- ROC curve -----------------------------------------------------------------

#' Build an ROC curve plot
#'
#' Expects a data frame with columns: fpr (false positive rate),
#' tpr (true positive rate), and optionally a grouping column.
#'
#' @param data Data frame with fpr and tpr columns.
#' @param group Unquoted column for grouping multiple curves (optional).
#' @param title Plot title (optional).
#' @param palette Named character vector of colors (optional).
#' @param base_size Base font size (default 14).
#' @return A ggplot object.
#' @export
build_roc <- function(data, group = NULL, title = NULL,
                      palette = NULL, base_size = 14) {
  p <- ggplot2::ggplot(data, ggplot2::aes(
    x = fpr, y = tpr, colour = {{ group }}
  )) +
    ggplot2::geom_line(linewidth = 0.8) +
    ggplot2::geom_abline(
      slope = 1, intercept = 0, linetype = "dashed", color = "grey50"
    ) +
    ggplot2::labs(x = "False Positive Rate", y = "True Positive Rate") +
    ggplot2::coord_equal() +
    theme_research(base_size = base_size)

  if (!is.null(title)) {
    p <- p + ggplot2::ggtitle(title)
  }
  if (!is.null(palette)) {
    p <- p + ggplot2::scale_colour_manual(values = palette)
  }
  p
}

# -- Bar plot ------------------------------------------------------------------

#' Build a bar plot with optional error bars
#'
#' @param data Data frame.
#' @param x Unquoted column for x-axis (categorical).
#' @param y Unquoted column for y-axis (numeric, e.g. mean).
#' @param fill Unquoted column for fill (optional).
#' @param ymin Unquoted column for lower error bar (optional).
#' @param ymax Unquoted column for upper error bar (optional).
#' @param title Plot title (optional).
#' @param palette Named character vector of colors (optional).
#' @param base_size Base font size (default 14).
#' @return A ggplot object.
#' @export
build_bar <- function(data, x, y, fill = NULL,
                      ymin = NULL, ymax = NULL,
                      title = NULL, palette = NULL,
                      base_size = 14) {
  p <- ggplot2::ggplot(data, ggplot2::aes(
    x = {{ x }}, y = {{ y }}, fill = {{ fill }}
  )) +
    ggplot2::geom_col(position = ggplot2::position_dodge(width = 0.8),
                      alpha = 0.8) +
    theme_research(base_size = base_size)

  # Add error bars if ymin/ymax are provided
  has_ymin <- tryCatch(
    { rlang::eval_tidy(rlang::enquo(ymin), data); TRUE },
    error = function(e) FALSE
  )
  if (has_ymin) {
    p <- p + ggplot2::geom_errorbar(
      ggplot2::aes(ymin = {{ ymin }}, ymax = {{ ymax }}),
      position = ggplot2::position_dodge(width = 0.8),
      width = 0.2
    )
  }

  if (!is.null(title)) {
    p <- p + ggplot2::ggtitle(title)
  }
  if (!is.null(palette)) {
    p <- p + ggplot2::scale_fill_manual(values = palette)
  }
  p
}
