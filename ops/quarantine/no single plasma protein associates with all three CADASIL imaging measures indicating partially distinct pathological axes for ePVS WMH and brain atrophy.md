---
description: "No single plasma protein in the CADASIL SomaScan dataset associates with all three imaging measures (ePVS, WMH, brain parenchymal fraction), indicating that these measures capture partially distinct pathological processes despite their co-occurrence in SVD."
type: "claim"
confidence: "supported"
source: "[[2024-karvelas-enlarged-perivascular-spaces-are-associated-with-white-matter-injury-cognition]]"
source_class: "published"
verified_by: "agent"
created: "2026-03-04"
---

After examining protein associations with ePVS volume, WMH volume, and brain parenchymal fraction separately, Karvelas et al. report that no single plasma protein was associated with all three imaging measures simultaneously. [[CXCL8-IL-8 is a hub protein in the CADASIL ePVS network and independently associates with white matter hyperintensity volume]] associated with ePVS and WMH but not brain parenchymal fraction. CCL2 associated with ePVS, brain parenchymal fraction, and cognition but was not reported as a WMH predictor. This protein-level dissociation among the three imaging measures argues that ePVS, WMH, and brain parenchymal fraction are not redundant structural readouts of a single process but rather capture partially distinct pathological axes in CADASIL.

This finding has direct consequences for trial endpoint design and biomarker panel construction. If ePVS, WMH, and atrophy were driven by a common upstream mechanism, any one of them would suffice as a trial outcome measure and a single biomarker would track all three. The dissociation implies instead that a comprehensive imaging endpoint battery should include all three measures, and that plasma biomarker panels intended to monitor multiple pathological axes must include proteins from distinct pathway clusters rather than focusing on a single inflammatory hub.

Mechanistically, the dissociation is plausible: ePVS enlargement may primarily reflect perivascular fluid dynamics and immune trafficking (early/ongoing inflammation), WMH may reflect ischemic and demyelinating injury to white matter (intermediate-stage damage), and brain parenchymal fraction may reflect irreversible neuronal and axonal loss (late-stage atrophy). These stages may have different rate-limiting molecular drivers, explaining why their protein correlates do not fully overlap.

This is also relevant to the methodological structure of the [[cadasil-translational-characterization]] multi-modal integration plan: the analytic framework should treat ePVS, WMH, and brain parenchymal fraction as complementary rather than redundant outcomes, and biomarker associations should be modeled separately for each imaging endpoint.

---

Source: [[2024-karvelas-enlarged-perivascular-spaces-are-associated-with-white-matter-injury-cognition]]

Relevant Notes:
- [[ePVS volumes in CADASIL associate with WMH burden and cognitive severity within patients but do not differ from controls at the group level]] -- the foundational imaging result that establishes ePVS as a within-CADASIL severity marker correlated with WMH and CDR; the protein dissociation claim here refines that finding by showing the WMH-ePVS association does not generalize to a single shared molecular driver with brain atrophy
- [[cadasil-translational-characterization]] -- methodological implication: treat ePVS, WMH, and brain parenchymal fraction as non-redundant endpoints in the imaging battery; model protein associations separately for each
- [[multi-modal integration of txage simoa and cognitive scores requires a pre-specified analytic plan to avoid circular analysis]] -- this dissociation finding reinforces the need to pre-specify which imaging outcome each biomarker is expected to track before running associations
- [[ePVS-outcome associations in CADASIL are disease-state-specific as demonstrated by significant interaction terms with WMH CDR-SoB and MMSE]] -- the disease-state-specific interaction terms (WMH, CDR-SoB, MMSE) span the same three outcome domains where protein associations dissociate; the imaging-level disease-specificity and the protein-level dissociation are complementary observations from the same dataset
- [[ePVS-associated plasma proteins in CADASIL enrich for leukocyte migration and inflammation pathways while negatively associated proteins enrich for lipid metabolism]] -- the pathway enrichment signal belongs specifically to the ePVS axis; the absence of a common protein across all three imaging measures means the leukocyte migration enrichment cannot be extended to WMH or atrophy without independent validation
- [[CXCL8-IL-8 is a hub protein in the CADASIL ePVS network and independently associates with white matter hyperintensity volume]] -- CXCL8 illustrates the dissociation by tracking ePVS and WMH but not brain parenchymal fraction; it is concrete molecular evidence for the ePVS-WMH shared axis that does not extend to atrophy
- [[CCL2-MCP-1 is a hub protein in the CADASIL ePVS network and independently associates with brain atrophy MMSE and executive function]] -- CCL2 illustrates the dissociation from the opposite direction: it is an ePVS hub protein that tracks atrophy and cognition rather than WMH, confirming the ePVS-atrophy axis has a distinct molecular driver from the ePVS-WMH axis
- [[semiautomated ePVS quantification combined with SomaScan proteomics demonstrates technical feasibility of multi-modal imaging-proteomics studies in CADASIL]] -- the multi-modal design that enabled this dissociation to be detected; simultaneous ePVS, WMH, and brain parenchymal fraction quantification in the same cohort with the same proteomic data is the prerequisite for comparing protein associations across imaging axes
- [[absence of mean ePVS difference between CADASIL and controls despite within-disease associations raises unresolved question of disease-accelerated aging versus NOTCH3-specific pathomechanism]] -- the protein dissociation adds interpretive nuance to the aging question: if distinct protein profiles drive each imaging axis, the NOTCH3-specific pathomechanism hypothesis must specify which axis is NOTCH3-dependent versus which may reflect general vascular aging
