# test-theme_research.R -- Tests for theme_research.R theme and sizes

library(testthat)
library(ggplot2)

# Source the module under test
source(testthat::test_path("..", "theme_research.R"))

# -- theme_research() ---------------------------------------------------------

test_that("theme_research returns a ggplot2 theme object", {
  th <- theme_research()
  expect_s3_class(th, "theme")
})

test_that("theme_research has bold title", {
  th <- theme_research()
  expect_equal(th$plot.title$face, "bold")
})

test_that("theme_research has grey90 strip background by default", {
  th <- theme_research()
  expect_equal(th$strip.background$fill, "grey90")
})

test_that("theme_research has bold strip text", {
  th <- theme_research()
  expect_equal(th$strip.text$face, "bold")
})

test_that("theme_research has bottom legend by default", {
  th <- theme_research()
  expect_equal(th$legend.position, "bottom")
})

test_that("theme_research strip_color parameter works", {
  th <- theme_research(strip_color = "lightblue")
  expect_equal(th$strip.background$fill, "lightblue")
})

test_that("theme_research legend_position parameter works", {
  th <- theme_research(legend_position = "right")
  expect_equal(th$legend.position, "right")
})

test_that("theme_research accepts custom base_size", {
  th <- theme_research(base_size = 18)
  expect_s3_class(th, "theme")
})

# -- FIGURE_SIZES --------------------------------------------------------------

test_that("FIGURE_SIZES is a named list", {
  expect_true(is.list(FIGURE_SIZES))
  expect_true(length(FIGURE_SIZES) > 0)
})

test_that("FIGURE_SIZES contains expected plot types", {
  expected <- c(
    "box_grouped", "box_single", "violin_grouped", "violin_single",
    "scatter_multi", "scatter_single", "scatter_bivar",
    "heatmap", "forest", "volcano", "roc", "bar"
  )
  for (key in expected) {
    expect_true(key %in% names(FIGURE_SIZES), info = paste("Missing:", key))
  }
})

test_that("Each FIGURE_SIZE has width and height", {
  for (name in names(FIGURE_SIZES)) {
    size <- FIGURE_SIZES[[name]]
    expect_true("width" %in% names(size), info = paste(name, "missing width"))
    expect_true("height" %in% names(size), info = paste(name, "missing height"))
    expect_true(size["width"] > 0, info = paste(name, "width <= 0"))
    expect_true(size["height"] > 0, info = paste(name, "height <= 0"))
  }
})

# -- get_figure_size() ---------------------------------------------------------

test_that("get_figure_size returns correct size", {
  size <- get_figure_size("roc")
  expect_equal(size[["width"]], 7)
  expect_equal(size[["height"]], 7)
})

test_that("get_figure_size errors on unknown type", {
  expect_error(get_figure_size("nonexistent"), "Unknown plot type")
})
