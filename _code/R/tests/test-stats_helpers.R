# test-stats_helpers.R -- Tests for stats_helpers.R decision tree and formatters

library(testthat)

# Source the module under test
source(testthat::test_path("..", "stats_helpers.R"))

# -- select_test decision tree -------------------------------------------------

test_that("two_group selects welch_t when n>=30 and normal", {
  expect_equal(select_test("two_group", n_per_group = 50, normal = TRUE), "welch_t")
  expect_equal(select_test("two_group", n_per_group = 30, normal = TRUE), "welch_t")
})

test_that("two_group selects mann_whitney when not normal or small n", {
  expect_equal(select_test("two_group", n_per_group = 50, normal = FALSE), "mann_whitney")
  expect_equal(select_test("two_group", n_per_group = 10, normal = TRUE), "mann_whitney")
  expect_equal(select_test("two_group", n_per_group = 10, normal = FALSE), "mann_whitney")
})

test_that("two_group requires n_per_group", {
  expect_error(select_test("two_group"), "n_per_group required")
})

test_that("multi_group always selects kruskal_wallis", {
  expect_equal(select_test("multi_group"), "kruskal_wallis")
})

test_that("paired selects based on normality", {
  expect_equal(select_test("paired", normal = TRUE), "paired_t")
  expect_equal(select_test("paired", normal = FALSE), "wilcoxon_signed_rank")
})

test_that("correlation defaults to spearman", {
  expect_equal(select_test("correlation"), "spearman")
  expect_equal(select_test("correlation", method = "spearman"), "spearman")
})

test_that("correlation selects pearson only when normal and requested", {
  expect_equal(
    select_test("correlation", method = "pearson", normal = TRUE),
    "pearson"
  )
  expect_equal(
    select_test("correlation", method = "pearson", normal = FALSE),
    "spearman"
  )
})

test_that("proportion selects based on expected cell count", {
  expect_equal(select_test("proportion", min_expected = 10), "chi_square")
  expect_equal(select_test("proportion", min_expected = 3), "fisher_exact")
})

test_that("unknown design errors", {
  expect_error(select_test("unknown"), "Unknown design")
})

# -- Formatters ----------------------------------------------------------------

test_that("format_pval formats correctly", {
  expect_equal(format_pval(0.042), "p = 0.042")
  expect_equal(format_pval(0.0001), "p < 0.001")
  expect_equal(format_pval(0.001), "p = 0.001")
  expect_equal(format_pval(0.999), "p = 0.999")
  expect_equal(format_pval(NA), "p = NA")
})

test_that("pval_stars returns correct symbols", {
  expect_equal(pval_stars(0.0001), "***")
  expect_equal(pval_stars(0.005), "**")
  expect_equal(pval_stars(0.03), "*")
  expect_equal(pval_stars(0.1), "ns")
  expect_equal(pval_stars(NA), "ns")
})

test_that("format_correlation produces expected string", {
  result <- format_correlation(0.42, 0.003, 50)
  expect_match(result, "r = 0.42")
  expect_match(result, "p = 0.003")
  expect_match(result, "n = 50")
})

test_that("format_correlation handles small p-values", {
  result <- format_correlation(-0.85, 0.00001, 100)
  expect_match(result, "r = -0.85")
  expect_match(result, "p < 0.001")
  expect_match(result, "n = 100")
})

# -- Test runners (basic smoke tests) -----------------------------------------

test_that("run_two_group mann_whitney returns expected structure", {
  set.seed(42)
  x <- rnorm(30, mean = 5)
  y <- rnorm(30, mean = 7)
  result <- run_two_group(x, y, test = "mann_whitney")
  expect_true(is.list(result))
  expect_equal(result$test, "mann_whitney")
  expect_true(is.numeric(result$p.value))
  expect_true(result$p.value >= 0 && result$p.value <= 1)
})

test_that("run_two_group welch_t returns expected structure", {
  set.seed(42)
  x <- rnorm(30, mean = 5)
  y <- rnorm(30, mean = 7)
  result <- run_two_group(x, y, test = "welch_t")
  expect_equal(result$test, "welch_t")
  expect_true(is.numeric(result$p.value))
})

test_that("run_paired returns expected structure", {
  set.seed(42)
  x <- rnorm(20, mean = 5)
  y <- x + rnorm(20, mean = 1)
  result <- run_paired(x, y, test = "wilcoxon_signed_rank")
  expect_equal(result$test, "wilcoxon_signed_rank")
  expect_true(is.numeric(result$p.value))
})

test_that("run_paired errors on unequal lengths", {
  expect_error(run_paired(1:5, 1:3), "equal-length")
})

test_that("run_correlation returns expected structure", {
  set.seed(42)
  x <- rnorm(50)
  y <- x + rnorm(50, sd = 0.5)
  result <- run_correlation(x, y, method = "spearman")
  expect_equal(result$test, "spearman")
  expect_true(is.numeric(result$estimate))
  expect_equal(result$n, 50)
})
