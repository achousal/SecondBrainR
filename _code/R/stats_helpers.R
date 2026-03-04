# stats_helpers.R -- Statistical test selection and formatting helpers
#
# Provides a decision tree for test selection, runners, and consistent
# formatting of p-values, correlation results, and significance annotations.
# Mirrors the Python plot_stats module.

# -- Test selection decision tree ----------------------------------------------

#' Select the appropriate statistical test based on design and data properties
#'
#' Implements a standard decision tree:
#' - two_group (unpaired): Welch t-test (n>=30, normal) or Mann-Whitney U
#' - multi_group (3+): Kruskal-Wallis + Dunn post-hoc (BH correction)
#' - paired: paired t-test (normal) or Wilcoxon signed-rank
#' - correlation: Spearman (default) or Pearson (if requested + normal)
#' - proportion: Fisher exact (expected<5) or Chi-square
#'
#' @param design Character: "two_group", "multi_group", "paired",
#'   "correlation", "proportion".
#' @param n_per_group Integer: sample size per group (used for two_group).
#' @param normal Logical: whether data passes normality check (default FALSE).
#' @param method Character: for correlation, "spearman" (default) or "pearson".
#' @param min_expected Numeric: minimum expected cell count for proportion
#'   tests (default 5).
#' @return Character string naming the recommended test.
#' @export
select_test <- function(design,
                        n_per_group = NULL,
                        normal = FALSE,
                        method = "spearman",
                        min_expected = 5) {
  design <- tolower(design)
  switch(design,
    two_group = {
      if (is.null(n_per_group)) {
        stop("n_per_group required for two_group design")
      }
      if (n_per_group >= 30 && normal) {
        "welch_t"
      } else {
        "mann_whitney"
      }
    },
    multi_group = "kruskal_wallis",
    paired = {
      if (normal) "paired_t" else "wilcoxon_signed_rank"
    },
    correlation = {
      method <- tolower(method)
      if (method == "pearson" && normal) "pearson" else "spearman"
    },
    proportion = {
      if (min_expected < 5) "fisher_exact" else "chi_square"
    },
    stop("Unknown design: '", design, "'. Choose from: ",
         "two_group, multi_group, paired, correlation, proportion")
  )
}

# -- Test runners --------------------------------------------------------------

#' Run a two-group comparison test
#'
#' @param x Numeric vector (group 1).
#' @param y Numeric vector (group 2).
#' @param test Character: "welch_t" or "mann_whitney".
#' @return A list with test, statistic, p.value, method.
#' @export
run_two_group <- function(x, y, test = "mann_whitney") {
  result <- switch(test,
    welch_t = {
      tt <- stats::t.test(x, y, var.equal = FALSE)
      list(
        test = "welch_t",
        statistic = tt$statistic,
        p.value = tt$p.value,
        method = tt$method
      )
    },
    mann_whitney = {
      wt <- stats::wilcox.test(x, y, exact = FALSE)
      list(
        test = "mann_whitney",
        statistic = wt$statistic,
        p.value = wt$p.value,
        method = wt$method
      )
    },
    stop("Unknown test: '", test, "'")
  )
  result
}

#' Run a paired comparison test
#'
#' @param x Numeric vector (condition 1).
#' @param y Numeric vector (condition 2, same length as x).
#' @param test Character: "paired_t" or "wilcoxon_signed_rank".
#' @return A list with test, statistic, p.value, method.
#' @export
run_paired <- function(x, y, test = "wilcoxon_signed_rank") {
  if (length(x) != length(y)) {
    stop("Paired test requires equal-length vectors")
  }
  result <- switch(test,
    paired_t = {
      tt <- stats::t.test(x, y, paired = TRUE)
      list(
        test = "paired_t",
        statistic = tt$statistic,
        p.value = tt$p.value,
        method = tt$method
      )
    },
    wilcoxon_signed_rank = {
      wt <- stats::wilcox.test(x, y, paired = TRUE, exact = FALSE)
      list(
        test = "wilcoxon_signed_rank",
        statistic = wt$statistic,
        p.value = wt$p.value,
        method = wt$method
      )
    },
    stop("Unknown test: '", test, "'")
  )
  result
}

#' Run a correlation test
#'
#' @param x Numeric vector.
#' @param y Numeric vector.
#' @param method Character: "spearman" (default) or "pearson".
#' @return A list with test, estimate (r), p.value, n, method.
#' @export
run_correlation <- function(x, y, method = "spearman") {
  ct <- stats::cor.test(x, y, method = method)
  list(
    test = method,
    estimate = ct$estimate,
    p.value = ct$p.value,
    n = length(x),
    method = ct$method
  )
}

# -- Formatters ----------------------------------------------------------------

#' Format a p-value for display
#'
#' Uses "p < 0.001" for very small values, otherwise 3 decimal places.
#'
#' @param p Numeric p-value.
#' @param threshold Threshold below which to report "p < threshold"
#'   (default 0.001).
#' @return Character string.
#' @export
format_pval <- function(p, threshold = 0.001) {
  if (is.na(p)) return("p = NA")
  if (p < threshold) {
    paste0("p < ", threshold)
  } else {
    sprintf("p = %.3f", p)
  }
}

#' Convert p-value to significance stars
#'
#' @param p Numeric p-value.
#' @return Character: "***" (p<0.001), "**" (p<0.01), "*" (p<0.05), "ns".
#' @export
pval_stars <- function(p) {
  if (is.na(p)) return("ns")
  if (p < 0.001) return("***")
  if (p < 0.01)  return("**")
  if (p < 0.05)  return("*")
  "ns"
}

#' Format a correlation result for annotation
#'
#' @param r Numeric correlation coefficient.
#' @param p Numeric p-value.
#' @param n Integer sample size.
#' @return Character: "r = X.XX, p = Y.YYY, n = Z"
#'   or "r = X.XX, p < 0.001, n = Z".
#' @export
format_correlation <- function(r, p, n) {
  paste0("r = ", sprintf("%.2f", r), ", ", format_pval(p), ", n = ", n)
}

#' Save p-values as a sidecar text file alongside a figure
#'
#' @param path Character path to the figure file.
#' @param pvalues Named numeric vector or data.frame of p-values.
#' @return Invisible path to the sidecar file.
#' @export
save_pvalues <- function(path, pvalues) {
  sidecar <- sub("\\.[^.]+$", "_pvalues.txt", path)
  if (is.data.frame(pvalues)) {
    utils::write.table(pvalues, sidecar, sep = "\t", row.names = FALSE,
                       quote = FALSE)
  } else {
    lines <- paste(names(pvalues), format_pval(pvalues), sep = "\t")
    writeLines(lines, sidecar)
  }
  message("Saved p-values: ", sidecar)
  invisible(sidecar)
}
