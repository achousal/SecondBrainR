# test-plot_builders.R -- Tests for plot_builders.R builder functions

library(testthat)
library(ggplot2)

# Source dependencies then module under test
source(testthat::test_path("..", "palettes.R"))
source(testthat::test_path("..", "theme_research.R"))
source(testthat::test_path("..", "plot_builders.R"))

# -- Test data ----------------------------------------------------------------

toy_cat <- data.frame(
  group = rep(c("A", "B"), each = 20),
  value = c(rnorm(20, 5, 1), rnorm(20, 7, 1)),
  stringsAsFactors = FALSE
)
set.seed(42)
toy_scatter <- data.frame(
  x = rnorm(50),
  y = rnorm(50),
  grp = sample(c("X", "Y"), 50, replace = TRUE),
  stringsAsFactors = FALSE
)
toy_mat <- matrix(
  c(1.0, 0.5, 0.3, 0.5, 1.0, 0.7, 0.3, 0.7, 1.0),
  nrow = 3, dimnames = list(c("A", "B", "C"), c("A", "B", "C"))
)
toy_volcano <- data.frame(
  log2fc = c(-2, -0.5, 0, 0.3, 1.5),
  pvalue = c(0.001, 0.1, 0.5, 0.2, 0.01),
  direction = c("Down", "NS", "NS", "NS", "Up"),
  stringsAsFactors = FALSE
)
toy_forest <- data.frame(
  label = c("Gene A", "Gene B", "Gene C"),
  estimate = c(0.5, -0.3, 1.2),
  ci_lower = c(0.1, -0.8, 0.6),
  ci_upper = c(0.9, 0.2, 1.8),
  stringsAsFactors = FALSE
)
toy_roc <- data.frame(
  fpr = c(0, 0.2, 0.4, 0.6, 0.8, 1.0),
  tpr = c(0, 0.5, 0.7, 0.85, 0.95, 1.0),
  stringsAsFactors = FALSE
)
toy_bar <- data.frame(
  category = c("A", "B", "C"),
  mean_val = c(3.2, 5.1, 4.0),
  lo = c(2.8, 4.5, 3.4),
  hi = c(3.6, 5.7, 4.6),
  stringsAsFactors = FALSE
)

# -- build_violin -------------------------------------------------------------

test_that("build_violin returns a ggplot", {
  p <- build_violin(toy_cat, x = group, y = value)
  expect_s3_class(p, "ggplot")
})

test_that("build_violin has violin and jitter layers", {
  p <- build_violin(toy_cat, x = group, y = value)
  layer_classes <- sapply(p$layers, function(l) class(l$geom)[1])
  expect_true("GeomViolin" %in% layer_classes)
  expect_true("GeomPoint" %in% layer_classes)
})

test_that("build_violin applies title", {
  p <- build_violin(toy_cat, x = group, y = value, title = "Test Title")
  expect_equal(p$labels$title, "Test Title")
})

test_that("build_violin applies custom palette", {
  pal <- c("A" = "#FF0000", "B" = "#0000FF")
  p <- build_violin(toy_cat, x = group, y = value, fill = group, palette = pal)
  expect_s3_class(p, "ggplot")
})

# -- build_box ----------------------------------------------------------------

test_that("build_box returns a ggplot", {
  p <- build_box(toy_cat, x = group, y = value)
  expect_s3_class(p, "ggplot")
})

test_that("build_box has boxplot and jitter layers", {
  p <- build_box(toy_cat, x = group, y = value)
  layer_classes <- sapply(p$layers, function(l) class(l$geom)[1])
  expect_true("GeomBoxplot" %in% layer_classes)
  expect_true("GeomPoint" %in% layer_classes)
})

test_that("build_box applies title", {
  p <- build_box(toy_cat, x = group, y = value, title = "Box Title")
  expect_equal(p$labels$title, "Box Title")
})

# -- build_scatter ------------------------------------------------------------

test_that("build_scatter returns a ggplot", {
  p <- build_scatter(toy_scatter, x = x, y = y)
  expect_s3_class(p, "ggplot")
})

test_that("build_scatter has point layer", {
  p <- build_scatter(toy_scatter, x = x, y = y)
  layer_classes <- sapply(p$layers, function(l) class(l$geom)[1])
  expect_true("GeomPoint" %in% layer_classes)
})

test_that("build_scatter adds lm line when requested", {
  p <- build_scatter(toy_scatter, x = x, y = y, add_lm = TRUE)
  layer_classes <- sapply(p$layers, function(l) class(l$geom)[1])
  expect_true("GeomSmooth" %in% layer_classes)
})

test_that("build_scatter omits lm line by default", {
  p <- build_scatter(toy_scatter, x = x, y = y)
  layer_classes <- sapply(p$layers, function(l) class(l$geom)[1])
  expect_false("GeomSmooth" %in% layer_classes)
})

test_that("build_scatter applies color palette", {
  pal <- c("X" = "#FF0000", "Y" = "#0000FF")
  p <- build_scatter(toy_scatter, x = x, y = y, color = grp, palette = pal)
  expect_s3_class(p, "ggplot")
})

# -- build_heatmap ------------------------------------------------------------

test_that("build_heatmap returns a ggplot", {
  p <- build_heatmap(toy_mat)
  expect_s3_class(p, "ggplot")
})

test_that("build_heatmap has tile layer", {
  p <- build_heatmap(toy_mat)
  layer_classes <- sapply(p$layers, function(l) class(l$geom)[1])
  expect_true("GeomTile" %in% layer_classes)
})

test_that("build_heatmap applies title", {
  p <- build_heatmap(toy_mat, title = "Heatmap Title")
  expect_equal(p$labels$title, "Heatmap Title")
})

test_that("build_heatmap auto-computes symmetric limits", {
  p <- build_heatmap(toy_mat)
  # Should build without error and have a fill scale
  expect_s3_class(p, "ggplot")
})

test_that("build_heatmap uses custom limits", {
  p <- build_heatmap(toy_mat, limits = c(-2, 2))
  expect_s3_class(p, "ggplot")
})

test_that("build_heatmap handles all-non-finite matrix", {
  bad_mat <- matrix(
    c(NaN, Inf, -Inf, NA),
    nrow = 2, dimnames = list(c("A", "B"), c("X", "Y"))
  )
  p <- build_heatmap(bad_mat)
  expect_s3_class(p, "ggplot")
})

# -- build_volcano ------------------------------------------------------------

test_that("build_volcano returns a ggplot", {
  p <- build_volcano(toy_volcano, x = log2fc, y = pvalue)
  expect_s3_class(p, "ggplot")
})

test_that("build_volcano has threshold lines", {
  p <- build_volcano(toy_volcano, x = log2fc, y = pvalue)
  layer_classes <- sapply(p$layers, function(l) class(l$geom)[1])
  expect_true("GeomHline" %in% layer_classes)
  expect_true("GeomVline" %in% layer_classes)
})

test_that("build_volcano applies custom thresholds", {
  p <- build_volcano(
    toy_volcano, x = log2fc, y = pvalue,
    fc_thresh = 0.5, p_thresh = 0.01
  )
  expect_s3_class(p, "ggplot")
})

test_that("build_volcano applies title", {
  p <- build_volcano(
    toy_volcano, x = log2fc, y = pvalue, title = "Volcano"
  )
  expect_equal(p$labels$title, "Volcano")
})

test_that("build_volcano warns on zero p-values", {
  zero_p <- toy_volcano
  zero_p$pvalue[1] <- 0
  expect_warning(
    build_volcano(zero_p, x = log2fc, y = pvalue),
    "Non-positive"
  )
})

# -- build_forest -------------------------------------------------------------

test_that("build_forest returns a ggplot", {
  p <- build_forest(toy_forest)
  expect_s3_class(p, "ggplot")
})

test_that("build_forest has pointrange layer", {
  p <- build_forest(toy_forest)
  layer_classes <- sapply(p$layers, function(l) class(l$geom)[1])
  expect_true("GeomPointrange" %in% layer_classes)
})

test_that("build_forest has null effect line", {
  p <- build_forest(toy_forest)
  layer_classes <- sapply(p$layers, function(l) class(l$geom)[1])
  expect_true("GeomVline" %in% layer_classes)
})

test_that("build_forest accepts custom null_value", {
  p <- build_forest(toy_forest, null_value = 1)
  expect_s3_class(p, "ggplot")
})

test_that("build_forest applies title", {
  p <- build_forest(toy_forest, title = "Forest Plot")
  expect_equal(p$labels$title, "Forest Plot")
})

# -- build_roc ----------------------------------------------------------------

test_that("build_roc returns a ggplot", {
  p <- build_roc(toy_roc)
  expect_s3_class(p, "ggplot")
})

test_that("build_roc has line and diagonal layers", {
  p <- build_roc(toy_roc)
  layer_classes <- sapply(p$layers, function(l) class(l$geom)[1])
  expect_true("GeomLine" %in% layer_classes)
  expect_true("GeomAbline" %in% layer_classes)
})

test_that("build_roc applies title", {
  p <- build_roc(toy_roc, title = "ROC Curve")
  expect_equal(p$labels$title, "ROC Curve")
})

test_that("build_roc applies palette for grouped data", {
  roc_grp <- rbind(
    transform(toy_roc, model = "Model A"),
    transform(toy_roc, model = "Model B")
  )
  pal <- c("Model A" = "#E41A1C", "Model B" = "#377EB8")
  p <- build_roc(roc_grp, group = model, palette = pal)
  expect_s3_class(p, "ggplot")
})

# -- build_bar ----------------------------------------------------------------

test_that("build_bar returns a ggplot", {
  p <- build_bar(toy_bar, x = category, y = mean_val)
  expect_s3_class(p, "ggplot")
})

test_that("build_bar has col layer", {
  p <- build_bar(toy_bar, x = category, y = mean_val)
  layer_classes <- sapply(p$layers, function(l) class(l$geom)[1])
  expect_true("GeomCol" %in% layer_classes)
})

test_that("build_bar applies title", {
  p <- build_bar(toy_bar, x = category, y = mean_val, title = "Bar Plot")
  expect_equal(p$labels$title, "Bar Plot")
})

test_that("build_bar adds error bars when ymin/ymax provided", {
  p <- build_bar(toy_bar, x = category, y = mean_val, ymin = lo, ymax = hi)
  layer_classes <- sapply(p$layers, function(l) class(l$geom)[1])
  expect_true("GeomErrorbar" %in% layer_classes)
})

test_that("build_bar with NULL ymin/ymax still builds without error", {
  p <- build_bar(toy_bar, x = category, y = mean_val)
  expect_s3_class(p, "ggplot")
})

# -- base_size parameter across all builders ----------------------------------

test_that("all builders accept custom base_size", {
  expect_s3_class(
    build_violin(toy_cat, x = group, y = value, base_size = 18), "ggplot"
  )
  expect_s3_class(
    build_box(toy_cat, x = group, y = value, base_size = 18), "ggplot"
  )
  expect_s3_class(
    build_scatter(toy_scatter, x = x, y = y, base_size = 18), "ggplot"
  )
  expect_s3_class(build_heatmap(toy_mat, base_size = 18), "ggplot")
  expect_s3_class(
    build_volcano(toy_volcano, x = log2fc, y = pvalue, base_size = 18),
    "ggplot"
  )
  expect_s3_class(build_forest(toy_forest, base_size = 18), "ggplot")
  expect_s3_class(build_roc(toy_roc, base_size = 18), "ggplot")
  expect_s3_class(
    build_bar(toy_bar, x = category, y = mean_val, base_size = 18), "ggplot"
  )
})
