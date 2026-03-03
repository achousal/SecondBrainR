# export_predictions.R
#
# Template showing how R pipelines produce JSON for the biomarker dashboard.
# This is documentation, not a runtime dependency.
#
# The dashboard expects a JSON file with this structure:
# {
#   "modelId": "model_name",
#   "runId": "run_identifier",
#   "patients": [
#     {
#       "patientId": "P001",
#       "probability": 0.87,
#       "classification": "AD Positive",
#       "baseValue": 0.35,
#       "shapValues": [
#         { "feature": "ptau217", "value": 2.34, "shapValue": 0.28 },
#         ...
#       ]
#     }
#   ]
# }

#' Export predictions to dashboard-compatible JSON
#'
#' @param predictions A data.frame with columns: patient_id, probability, classification
#' @param shap_matrix A matrix of SHAP values (patients x features)
#' @param feature_values A data.frame of feature values (same dims as shap_matrix)
#' @param base_value Numeric scalar, the base value (expected value) from the model
#' @param model_id Character, model identifier
#' @param run_id Character, run/batch identifier
#' @param output_path Character, path for output JSON file
#' @return Invisible NULL; writes JSON to output_path
export_predictions <- function(predictions,
                                shap_matrix,
                                feature_values,
                                base_value,
                                model_id,
                                run_id,
                                output_path) {
  stopifnot(
    is.data.frame(predictions),
    "patient_id" %in% names(predictions),
    "probability" %in% names(predictions),
    "classification" %in% names(predictions),
    nrow(predictions) == nrow(shap_matrix),
    ncol(shap_matrix) == ncol(feature_values)
  )

  features <- colnames(shap_matrix)

  patients <- lapply(seq_len(nrow(predictions)), function(i) {
    shap_entries <- lapply(seq_along(features), function(j) {
      list(
        feature = features[j],
        value = as.numeric(feature_values[i, j]),
        shapValue = as.numeric(shap_matrix[i, j])
      )
    })

    list(
      patientId = as.character(predictions$patient_id[i]),
      probability = as.numeric(predictions$probability[i]),
      classification = as.character(predictions$classification[i]),
      baseValue = base_value,
      shapValues = shap_entries
    )
  })

  payload <- list(
    modelId = model_id,
    runId = run_id,
    patients = patients
  )

  json_text <- jsonlite::toJSON(payload, auto_unbox = TRUE, pretty = TRUE)
  writeLines(json_text, output_path)
  message("Exported predictions for ", length(patients), " patients to ", output_path)
  invisible(NULL)
}

# -- Example usage --
# predictions <- data.frame(
#   patient_id = c("P001", "P002"),
#   probability = c(0.87, 0.15),
#   classification = c("AD Positive", "AD Negative")
# )
# shap_matrix <- matrix(
#   c(0.28, 0.15, 0.06, -0.02,
#     -0.12, -0.05, -0.02, 0.03),
#   nrow = 2, byrow = TRUE,
#   dimnames = list(NULL, c("ptau217", "ab42_ab40", "gfap", "nfl"))
# )
# feature_values <- data.frame(
#   ptau217 = c(2.34, 0.31),
#   ab42_ab40 = c(0.062, 0.081),
#   gfap = c(142, 89),
#   nfl = c(8.2, 22.5)
# )
# export_predictions(predictions, shap_matrix, feature_values,
#                    base_value = 0.35, model_id = "ad_v2",
#                    run_id = "run_20260215",
#                    output_path = "predictions.json")
