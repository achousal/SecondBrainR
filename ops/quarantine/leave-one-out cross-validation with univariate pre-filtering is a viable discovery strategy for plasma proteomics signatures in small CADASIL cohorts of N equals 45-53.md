---
description: "LOO cross-validation generates N partitions per fold; within each fold, approximately 1300 proteins survive univariate t-test pre-filtering (alpha=0.05), managing the p>>n problem without eliminating all signal in N=45-53 CADASIL samples."
type: claim
source: "[[2024-jn-plasma-proteomics-of-genetic-brain-arteriosclerosis-and-dementia]]"
confidence: supported
source_class: preprint
verified_by: agent
verified_who: null
verified_date: null
created: "2026-03-04"
topics:
  - "[[cadasil-translational-characterization]]"
---

Plasma proteomics with SomaScan 7k generates ~7000 features. When the sample size is 45-53, the ratio of features to samples (p/n ~130-155) makes conventional train-test split cross-validation unstable — any single holdout set is too small to estimate generalization error reliably. Leave-one-out cross-validation addresses this by maximizing training set size: each LOO fold excludes exactly one sample and trains on N-1, generating N classifiers that are each evaluated on the held-out sample.

The pre-filtering step is a practical necessity. Without it, 7000 features fed into six different ML algorithms would produce unstable results dominated by noise. Within each LOO fold, a simple univariate t-test (alpha=0.05, no multiple testing correction) reduces the ~7000 aptamers to approximately 1300 candidates. This is a filter, not a selection: it removes the proteins that show no association with the outcome at all, without committing to any specific subset. The downstream multi-algorithm consensus selection (described in [[multi-algorithm consensus feature selection requiring proteins to appear in at least two of six algorithms across LOO folds provides more stable plasma proteomics signatures than single-algorithm selection in small cohorts]]) then operates within this reduced set.

Critically, the alpha=0.05 pre-filter is not corrected for multiple testing at this step — it is intentionally permissive to avoid filtering out true signal before the consensus step gets to evaluate it. The multiple-testing discipline is applied downstream via the consensus requirement.

This LOO + pre-filter + consensus pipeline is a transferable template for any SomaScan or proteomics discovery study with similar N constraints. For the VascBrain SomaScan dataset, which has comparable sample sizes in CADASIL subgroups, this analytical architecture directly addresses the p>>n challenge without requiring additional samples.

---

Source: [[2024-jn-plasma-proteomics-of-genetic-brain-arteriosclerosis-and-dementia]]

Relevant Notes:
- [[multi-algorithm consensus feature selection requiring proteins to appear in at least two of six algorithms across LOO folds provides more stable plasma proteomics signatures than single-algorithm selection in small cohorts]] — the consensus step that operates within this LOO framework
- [[plasma proteomics using SomaScan 7k identifies two distinct molecular signatures for early-stage and late-stage CADASIL reflecting stage-specific pathological mechanisms]] — the finding this analytical pipeline produced

Topics:
- [[cadasil-translational-characterization]]
