# test-plot_helpers.R -- Tests for plot_helpers.R axis helpers and save_plot

library(testthat)
library(ggplot2)

# Source dependencies then module under test
source(testthat::test_path("..", "palettes.R"))
source(testthat::test_path("..", "theme_research.R"))
source(testthat::test_path("..", "plot_helpers.R"))

# -- scale_y_auto -------------------------------------------------------------

test_that("scale_y_auto returns a Scale object", {
  s <- scale_y_auto()
  expect_s3_class(s, "Scale")
})

test_that("scale_y_auto uses tight expansion", {
  s <- scale_y_auto()
  expand <- s$expand
  expect_equal(expand, ggplot2::expansion(mult = c(0.02, 0.05)))
})

# -- scale_y_zero -------------------------------------------------------------

test_that("scale_y_zero returns a Scale object", {
  s <- scale_y_zero()
  expect_s3_class(s, "Scale")
})

test_that("scale_y_zero forces zero lower limit", {
  s <- scale_y_zero()
  # limits is a function or vector; check the first element is 0
  lims <- s$limits
  expect_equal(lims[1], 0)
})

test_that("scale_y_zero uses default expansion for violin", {
  s <- scale_y_zero()
  expect_equal(s$expand, ggplot2::expansion(mult = c(0.05, 0.25)))
})

test_that("scale_y_zero accepts custom expansion", {
  s <- scale_y_zero(expand_mult = c(0, 0.10))
  expect_equal(s$expand, ggplot2::expansion(mult = c(0, 0.10)))
})

# -- save_plot ----------------------------------------------------------------

test_that("save_plot creates a file", {
  tmp <- tempfile(fileext = ".pdf")
  on.exit(unlink(tmp), add = TRUE)

  p <- ggplot(data.frame(x = 1:5, y = 1:5), aes(x, y)) + geom_point()
  expect_message(save_plot(p, tmp), "Saved plot")
  expect_true(file.exists(tmp))
})

test_that("save_plot creates output directory if needed", {
  tmp_dir <- file.path(tempdir(), "test_save_plot_subdir")
  on.exit(unlink(tmp_dir, recursive = TRUE), add = TRUE)

  path <- file.path(tmp_dir, "fig.pdf")
  p <- ggplot(data.frame(x = 1:5, y = 1:5), aes(x, y)) + geom_point()
  save_plot(p, path)
  expect_true(file.exists(path))
})

test_that("save_plot writes PNG when fmt = png", {
  tmp <- tempfile(fileext = ".png")
  on.exit(unlink(tmp), add = TRUE)

  p <- ggplot(data.frame(x = 1:5, y = 1:5), aes(x, y)) + geom_point()
  save_plot(p, tmp, fmt = "png")
  expect_true(file.exists(tmp))
})

test_that("save_plot infers format from extension when fmt = NULL", {
  tmp <- tempfile(fileext = ".svg")
  on.exit(unlink(tmp), add = TRUE)

  p <- ggplot(data.frame(x = 1:5, y = 1:5), aes(x, y)) + geom_point()
  save_plot(p, tmp, fmt = NULL)
  expect_true(file.exists(tmp))
})

test_that("save_plot writes sidecar p-values from named vector", {
  tmp <- tempfile(fileext = ".pdf")
  sidecar <- sub("\\.pdf$", "_pvalues.txt", tmp)
  on.exit(unlink(c(tmp, sidecar)), add = TRUE)

  p <- ggplot(data.frame(x = 1:5, y = 1:5), aes(x, y)) + geom_point()
  pvals <- c("Gene A" = 0.03, "Gene B" = 0.0001)
  expect_message(save_plot(p, tmp, pvalues = pvals), "Saved p-values")
  expect_true(file.exists(sidecar))

  content <- readLines(sidecar)
  expect_equal(length(content), 2)
  expect_true(grepl("Gene A", content[1]))
  expect_true(grepl("Gene B", content[2]))
  expect_true(grepl("p < 0.001", content[2]))
})

test_that("save_plot writes sidecar p-values from data.frame", {
  tmp <- tempfile(fileext = ".pdf")
  sidecar <- sub("\\.pdf$", "_pvalues.txt", tmp)
  on.exit(unlink(c(tmp, sidecar)), add = TRUE)

  p <- ggplot(data.frame(x = 1:5, y = 1:5), aes(x, y)) + geom_point()
  pvals_df <- data.frame(comparison = c("A vs B"), pvalue = 0.04)
  save_plot(p, tmp, pvalues = pvals_df)
  expect_true(file.exists(sidecar))

  content <- readLines(sidecar)
  expect_true(any(grepl("A vs B", content)))
})

test_that("save_plot does not write sidecar when pvalues is NULL", {
  tmp <- tempfile(fileext = ".pdf")
  sidecar <- sub("\\.pdf$", "_pvalues.txt", tmp)
  on.exit(unlink(c(tmp, sidecar)), add = TRUE)

  p <- ggplot(data.frame(x = 1:5, y = 1:5), aes(x, y)) + geom_point()
  save_plot(p, tmp)
  expect_false(file.exists(sidecar))
})
