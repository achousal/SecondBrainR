# Quarantine Manifest

## Incident: Model-Memory Fabrication in /reduce

**Date:** 2026-03-04
**Root cause:** /reduce processed stub sources (title + URL, no abstract/methods) and synthesized detailed content from model training knowledge instead of refusing. The extraction-pressure instructions ("zero extraction = BUG") actively encouraged fabrication when sources were thin.
**Fix applied:** Stub source hard stop + source fidelity constraint added to /reduce SKILL.md. Source fidelity guardrail added to CLAUDE.md.

---

## Affected Sources

### Torres-Espin 2024 (stub) -- 15 claim notes + 1 literature note
- Source: `_research/literature/2024-torres-espin-sexually-dimorphic-differences-in-angiogenesis-markers-are-associated-with-brain-aging.md`
- Problem: Source was title + URL only. /reduce fabricated specific effect sizes, cohort details, PCA results, and methodology from model memory.

### Keller 2024 (stub) -- 14 claim notes
- Source: `[[2024-jn-plasma-proteomics-of-genetic-brain-arteriosclerosis-and-dementia]]`
- Problem: Source was title + URL only. /reduce fabricated SomaScan platform details, LOO-CV results, validation cohort specifics.

### French 2025 (stub) -- 5 claim notes
- Source: `[[2025-sr-cognitive-impairment-and-p-tau217-are-high-in-a]]`
- Problem: Source was title + URL only. /reduce fabricated AUC values, prevalence percentages, cardiovascular cohort details.

### Karvelas 2024 (stub) -- 8 claim notes
- Source: `[[2024-karvelas-enlarged-perivascular-spaces-are-associated-with-white-matter-injury-cognition]]`
- Problem: Source was title + URL only. /reduce fabricated ePVS quantification details, protein network results, interaction models.
- Note: A real abstract exists in the literature note, but the extract task pointed to the stub, not the literature note. Provenance chain is broken.

---

## Quarantined Files (42 claim notes + 1 literature note)

### Torres-Espin 2024 (15 claims)
- angiogenesis marker levels differ by sex and these sex differences predict distinct brain aging trajectories in humans.md
- aberrant angiogenesis and vascular health are two orthogonal principal components of circulating angiogenesis markers in aging.md
- PlGF-VEGFA heterodimers dampen angiogenic activation relative to VEGFA homodimers potentially triggering reactive aberrant angiogenesis.md
- external validation in MarkVCID cohort confirms sex-dependent aberrant angiogenesis associations with executive function.md
- bFGF shows an age-dependent directional shift in vascular risk factor association around age 75 independent of sex.md
- women show greater age-associated increases in aberrant angiogenesis than men suggesting sex-specific vascular aging trajectories.md
- small effect sizes for individual angiogenesis-brain associations suggest multivariate composites outperform single markers.md
- VEGFR1 positively associates with cardiovascular and cerebrovascular disease burden specifically in men.md
- plasma angiogenesis markers provide cognitive impairment information independent of AD neuropathological biomarkers.md
- MSD V-Plex electrochemiluminescence measures both sVEGFR1 and membrane-bound VEGFR1 without distinguishing isoforms.md
- bFGF positively associates with executive function and grey matter volume in both sexes and attenuates astrocyte activation by reducing GFAP expression.md
- amyloid-negative MCI shows higher aberrant angiogenesis than amyloid-positive MCI suggesting vascular cognitive impairment independent of amyloid pathology.md
- grey matter volume mediates 48 percent of the aberrant angiogenesis effect on executive function in women but not men.md
- VEGFR1 undergoes age-related alternative splicing producing sVEGFR1 that sequesters VEGFA as a decoy receptor in brain aging.md
- angiogenesis marker associations with brain structure and cognition are sexually dimorphic with directionality reversing around age 75 in women.md

### Torres-Espin 2024 (1 literature note)
- _research/literature/2024-torres-espin-sexually-dimorphic-differences-in-angiogenesis-markers-are-associated-with-brain-aging.md

### Keller 2024 (14 claims)
- CADASIL disease progression involves a cell-type shift from endothelial and fibroblast dysfunction in early stages to astrocyte and oligodendrocyte involvement in late stages.md
- complement dysregulation and lipid-peroxisome metabolism are the dominant pathway signals in late-stage CADASIL plasma proteomics.md
- early CADASIL signature failure in external cohort validation while late-stage succeeds suggests early disease has greater inter-individual heterogeneity that undermines plasma proteomics generalizability.md
- stage-specific plasma protein signatures in CADASIL imply that therapeutic targets differ by disease stage and that a single treatment strategy applied across disease stages is unlikely to be optimal.md
- leave-one-out cross-validation with univariate pre-filtering is a viable discovery strategy for plasma proteomics signatures in small CADASIL cohorts of N equals 45-53.md
- multi-algorithm consensus feature selection requiring proteins to appear in at least two of six algorithms across LOO folds provides more stable plasma proteomics signatures than single-algorithm selection in small cohorts.md
- brain tissue transcriptomics partially validates CADASIL plasma proteomics signatures but concordance is incomplete because end-stage tissue may not reflect biomarker dynamics at plasma collection time.md
- TARDBP inclusion in the late-stage CADASIL plasma proteomics signature suggests TDP-43 proteinopathy mechanisms overlap with CADASIL pathology.md
- the late-stage CADASIL plasma proteomics signature generalizes to an external Colombian validation cohort while the early-stage signature shows only marginal external validity.md
- plasma ENPP2 shows a neuroprotective pattern in CADASIL correlating negatively with functional decline and positively with global cognition suggesting it marks preserved neurological capacity.md
- plasma fibronectin FN1 elevation in CADASIL correlates with brain atrophy and functional decline making it a candidate disease-progression biomarker.md
- TGF-beta1 is the primary upstream regulator of both early and late CADASIL plasma protein signatures linking vascular senescence and fibrosis to NOTCH3-driven pathology.md
- heme biosynthesis and glutathione metabolism disruption are the dominant pathway signals in early-stage CADASIL plasma proteomics.md
- plasma proteomics using SomaScan 7k identifies two distinct molecular signatures for early-stage and late-stage CADASIL reflecting stage-specific pathological mechanisms.md

### French 2025 (5 claims)
- 29 percent of asymptomatic cardiovascular patients have undiagnosed cognitive impairment exceeding general population prevalence and revealing a systematic screening gap.md
- cardiovascular patients represent an underscreened population for AD pathology and cognitive impairment warranting systematic biomarker assessment in cardiovascular care settings.md
- amyloid-beta 42-40 ratio fails to associate with cognitive performance in cardiovascular patients while p-tau217 succeeds demonstrating a dissociation between amyloid and tau biomarker utility in vascular populations.md
- 55 percent of asymptomatic cardiovascular patients show elevated p-tau217 indicating high prevalence of occult tau pathology in a non-AD clinical population.md
- p-tau217 achieves AUC 0.94 for detecting cognitive impairment in asymptomatic cardiovascular patients.md

### Karvelas 2024 (8 claims)
- absence of mean ePVS difference between CADASIL and controls despite within-disease associations raises unresolved question of disease-accelerated aging versus NOTCH3-specific pathomechanism.md
- semiautomated ePVS quantification combined with SomaScan proteomics demonstrates technical feasibility of multi-modal imaging-proteomics studies in CADASIL.md
- no single plasma protein associates with all three CADASIL imaging measures indicating partially distinct pathological axes for ePVS WMH and brain atrophy.md
- CCL2-MCP-1 is a hub protein in the CADASIL ePVS network and independently associates with brain atrophy MMSE and executive function.md
- CXCL8-IL-8 is a hub protein in the CADASIL ePVS network and independently associates with white matter hyperintensity volume.md
- ePVS-associated plasma proteins in CADASIL enrich for leukocyte migration and inflammation pathways while negatively associated proteins enrich for lipid metabolism.md
- ePVS-outcome associations in CADASIL are disease-state-specific as demonstrated by significant interaction terms with WMH CDR-SoB and MMSE.md
- ePVS volumes in CADASIL associate with WMH burden and cognitive severity within patients but do not differ from controls at the group level.md

---

## Secondary Contamination (3 legitimate notes -- body text cleaned, not quarantined)

These notes have valid primary sources but were enriched during reflect/reweave with content referencing fabricated French 2025 claims. Contaminated paragraphs removed.

- memory clinic cohort validation of plasma p-tau217 confirms generalizability beyond research cohort settings.md
- p-tau217 superiority over other plasma biomarkers for amyloid classification persists in cohorts enriched for prediabetes hypertension and kidney disease.md
- plasma p-tau217 achieves AUC 94-97 percent for amyloid PET classification in a community cohort enriched for vascular and metabolic comorbidities.md

---

## Recovery Path

1. Get real abstracts via /literature search or stub enrichment
2. Re-seed enriched sources with /seed then /ralph
3. Re-extracted claims will have proper provenance
4. Claims with correct titles/descriptions may be recoverable -- compare quarantined notes against re-extracted ones
