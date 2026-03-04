---
description: "Keller 2024 uses six feature selection algorithms (RFE-LR L1-L2, rLDA, Random Forests, Boruta, MRMR) with a consensus threshold of minimum 2 agreement across LOO folds to recover stable CADASIL signatures from SomaScan 7k data."
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

Feature selection in high-dimensional proteomics data is inherently unstable in small cohorts: different algorithms emphasize different statistical properties, and any single algorithm applied to a small dataset will identify a signature that is partially an artifact of that algorithm's assumptions. The Keller 2024 approach addresses this directly through consensus.

The study uses six algorithms representing fundamentally different selection principles: RFE-Logistic Regression with L1 penalty (sparsity-based), RFE-Logistic Regression with L2 penalty (ridge-based), regularized Linear Discriminant Analysis (dimensionality reduction), Random Forests (ensemble tree-based), Boruta (shadow-variable permutation), and Minimum Redundancy Maximum Relevance (MRMR, information-theoretic). A protein must appear in the output of at least two of these six algorithms — across leave-one-out cross-validation folds — to be included in the final signature.

This is a deliberate stability design. No single algorithm is trusted to identify the true signal; only proteins that appear robustly across multiple algorithmic lenses are retained. In a SomaScan 7k dataset with ~7000 aptamers and N=45-53 samples, this acts as both a regularization mechanism and a false-positive filter.

The connection to [[machine learning feature selection from unbiased proteomic data identifies AD biomarker candidates that supervised hypothesis-driven approaches miss]] is direct: this paper applies the same unbiased discovery paradigm to a different disease (monogenic vascular dementia vs. SLE/AD). But the added value here is the specific six-algorithm consensus architecture — a transferable design pattern for any proteomic discovery study with similar constraints (high-dimensional data, small N, heterogeneous outcomes). The pattern is generalizable to VascBrain SomaScan analyses.

---

Source: [[2024-jn-plasma-proteomics-of-genetic-brain-arteriosclerosis-and-dementia]]

Relevant Notes:
- [[machine learning feature selection from unbiased proteomic data identifies AD biomarker candidates that supervised hypothesis-driven approaches miss]] — this claim extends that pattern with a specific implementation (six-algorithm consensus) and a new disease context
- [[leave-one-out cross-validation with univariate pre-filtering is a viable discovery strategy for plasma proteomics signatures in small CADASIL cohorts of N equals 45-53]] — the CV framework within which this consensus selection operates

Topics:
- [[cadasil-translational-characterization]]
