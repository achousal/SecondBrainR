# test-palettes.R -- Tests for palettes.R color definitions and helpers

library(testthat)

# Source the module under test
source(testthat::test_path("..", "palettes.R"))

# -- Semantic palette constants ------------------------------------------------

test_that("BINARY_COLORS has correct keys", {
  expect_named(BINARY_COLORS, c("Control", "Case"))
})

test_that("DIRECTION_COLORS has Up/Down/NS", {
  expect_named(DIRECTION_COLORS, c("Up", "Down", "NS"))
  expect_equal(DIRECTION_COLORS[["NS"]], "#999999")
})

test_that("SIG_COLORS has sig/not sig", {
  expect_named(SIG_COLORS, c("sig", "not sig"))
})

# -- No banned purple hues ----------------------------------------------------

# Banned purples: bright UI purples like purple1 (#9B30FF), #7B2D8E, etc.
# Allowed: Set1 muted purple #984EA3

banned_purple_pattern <- "^#(9B30FF|7B2D8E|800080|A020F0|BF40BF)"

test_that("No banned purple hues in semantic palettes", {
  all_colors <- c(
    BINARY_COLORS, DIRECTION_COLORS, SIG_COLORS
  )
  for (hex in all_colors) {
    expect_false(
      grepl(banned_purple_pattern, hex, ignore.case = TRUE),
      info = paste("Banned purple found:", hex)
    )
  }
})

# -- Lab palettes -- generic behavior -----------------------------------------

test_that("LAB_PALETTES is a list (empty when no labs configured)", {
  expect_true(is.list(LAB_PALETTES))
})

test_that("lab_palette errors on unknown lab", {
  expect_error(lab_palette("unknown"), "Unknown lab")
})

test_that("All configured lab palette values are valid hex colors", {
  if (length(LAB_PALETTES) == 0) {
    skip("No labs configured in palettes.yaml")
  }
  hex_pattern <- "^#[0-9A-Fa-f]{6}$"
  all_colors <- unlist(LAB_PALETTES)
  for (hex in all_colors) {
    expect_true(grepl(hex_pattern, hex), info = paste("Invalid hex:", hex))
  }
})
