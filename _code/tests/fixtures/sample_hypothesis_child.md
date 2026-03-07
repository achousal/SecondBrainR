---
type: hypothesis
title: "Baseline measurement variability predicts six-month treatment response via dynamic range"
id: "hyp-20260221-002"
status: proposed
elo: 1200
matches: 0
wins: 0
losses: 0
generation: 2
parents: ["hyp-20260221-001"]
children: []
research_goal: "[[goal-early-detection]]"
tags: [hypothesis, prediction]
created: 2026-02-21
updated: 2026-02-21
evolution_mode: "grounding-enhancement"
review_scores:
  novelty: null
  correctness: null
  testability: null
  impact: null
  overall: null
review_flags: []
linked_experiments: []
linked_literature: []
---

## Statement
Higher baseline variability in repeated measurements predicts better six-month treatment response, independently of baseline severity and demographic covariates, through a dynamic range mechanism.

## Mechanism
Greater measurement variability at baseline reflects system flexibility -- systems with higher dynamic range retain capacity for treatment-induced change. This dynamic range is mediated by neural plasticity reserves.

## Literature Grounding
- Author et al. 2024: baseline variability associated with treatment response
- Author et al. 2023: dynamic range as a predictor of adaptive capacity
- [[neural-plasticity-and-dynamic-range]]

## Testable Predictions
- [ ] Baseline variability is significantly higher in responders vs non-responders
- [ ] Variability-response correlation remains after adjusting for baseline severity and age
- [ ] Neural plasticity markers correlate with baseline variability

## Proposed Experiments
Linear regression of treatment response ~ baseline variability + baseline severity + age + sex in the longitudinal cohort. Add neural plasticity biomarker panel.

## Assumptions
- Assumption 1: Repeated baseline measurements capture meaningful variability -- Status: supported
- Assumption 2: Treatment response can be quantified as a continuous outcome -- Status: supported
- Assumption 3: Neural plasticity markers are measurable in the cohort -- Status: preliminary

## Limitations & Risks
Small sample size may limit power for interaction effects. Plasticity markers may have high assay variability.

## Review History


## Evolution History
- 2026-02-21 <- [[hyp-20260221-001]] via grounding-enhancement: Added neural plasticity mechanism and third prediction
