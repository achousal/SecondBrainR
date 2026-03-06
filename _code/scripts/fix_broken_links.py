"""Fix broken wiki links in notes/ by replacing paraphrased titles with actual filenames."""

import os
import re
import glob


REPLACEMENTS = {
    # Diacritic-stripped source links
    "2024-kivisakk-clinical-evaluation-of-a-novel-plasma-ptau217-electrochemiluminescence-immunoassay":
        "2024-kivisäkk-clinical-evaluation-of-a-novel-plasma-ptau217-electrochemiluminescence-immunoassay",
    "2025-martinez-dubarbie-diagnostic-performance-of-plasma-p-tau217-in-a-memory-clinic-cohort":
        "2025-martínez-dubarbie-diagnostic-performance-of-plasma-p-tau217-in-a-memory-clinic-cohort",
    # Title paraphrases -> correct filenames
    "combined PBMC proteomics and scRNA-seq can map plasma protein biomarker signals to their immune cell subtype of origin at the transcript level":
        "combined PBMC proteomics and scRNA-seq can map plasma protein biomarkers to their cellular sources enabling mechanistic interpretation of diagnostic signatures",
    "gonads are the dominant but not sole determinant of sex-dimorphic neuroactive steroid levels in brain and plasma":
        "gonads are the dominant but not sole determinant of sex-dimorphic neuroactive steroid levels in the brain",
    "irf4 and irf5 show higher binding to demethylated h3k4 and h3k27 respectively in female versus male ischemic microglia linking histone mark sex differences to inflammatory transcription factor activity":
        "irf4 and irf5 show higher binding to demethylated h3k4 and h3k27 sites in female microglia linking x-escapee demethylase activity to sex-biased inflammatory transcription",
    "longitudinal plasma biomarker trajectories differ across dementia groups suggesting disease-specific progression signatures are detectable in blood":
        "longitudinal plasma biomarker trajectories differ across dementia subtypes and may provide better discrimination than single-timepoint measurements",
    "no single plasma biomarker achieves universal specificity for AD amyloid pathology when tested across multiple dementia subtypes":
        "no single plasma biomarker achieves universal specificity for alzheimer disease across all dementia differential diagnoses",
    "plasma GFAP is elevated in MCI+AD and LBD but not in FTD or PSP providing a differential diagnostic biomarker signature across dementia subtypes":
        "plasma GFAP is elevated in MCI+AD and LBD but not in FTD or vascular dementia suggesting partial pathway specificity for astrocytic reactivity",
    "plasma p-tau181 is elevated in MCI and AD versus controls FTD and PSP but discriminates poorly between MCI+AD and LBD":
        "plasma p-tau181 is elevated in MCI and AD versus controls FTD and vascular dementia but not in lewy body dementia indicating partial diagnostic specificity",
    "plasma p-tau181 is inaccurate for detecting amyloid pathology in lewy body dementia undermining its use as an amyloid screen in mixed dementia populations":
        "plasma p-tau181 is inaccurate for detecting amyloid pathology in lewy body dementia due to confounding tau co-pathology",
    "rna-seq of flow-sorted microglia from aged mice post-mcao enables cell-type-specific identification of sex-differential x-escapee gene expression in the ischemic neuroinflammatory context":
        "rna-seq of flow-sorted microglia from aged mice post-mcao enables unbiased transcriptomic comparison of sex-specific neuroinflammatory programs",
    "sex chromosome complement exerts tissue-specific influences on neuroactive steroid levels including testosterone independent of gonadal status in the FCG mouse model":
        "sex chromosome complement exerts tissue-specific influences on neuroactive steroid concentrations that interact with gonadal hormone milieu",
    "sex chromosome contributions to musculoskeletal phenotype are minor soon after sexual maturation but become apparent as animals approach peak bone mass":
        "sex chromosome contributions to musculoskeletal phenotype are minor soon after sexual maturity but emerge with aging toward peak bone mass in FCG mice",
    "sex differences in kdm5c and kdm6a expression are conserved across mouse fcg model and human post-mortem stroke brain confirming cross-species relevance of x-escapee immune mechanisms":
        "sex differences in kdm5c and kdm6a expression are conserved between mouse and human brain tissue supporting translational relevance of x-escapee mechanisms",
    "the kdm-histone-irf pathway mediates sex differences in cerebral ischemia through x-escapee demethylase regulation of inflammatory transcription factor binding at h3k4 and h3k27":
        "the kdm-histone-irf pathway mediates sex differences in cerebral ischemic outcomes through differential epigenetic regulation of inflammatory gene networks",
    "x-escapee gene dosage provides a mechanism for sex differences in ischemic neuroinflammation that persists independently of gonadal hormones and after reproductive senescence":
        "x-escapee gene dosage provides a mechanism for sex differences in ischemic brain injury that is independent of acute hormonal effects",
    "x-escapee histone demethylases kdm5c and kdm6a are expressed at higher levels in female versus male ischemic microglia providing a chromosomal mechanism for sex-differential neuroinflammation":
        "x-escapee histone demethylases kdm5c and kdm6a are expressed at higher levels in female microglia and astrocytes than in male counterparts in both mouse and human brain",
}


def main():
    # Verify all replacement targets exist
    missing = []
    for broken, correct in REPLACEMENTS.items():
        found = False
        for d in ["notes", "_research/literature"]:
            if os.path.exists(os.path.join(d, correct + ".md")):
                found = True
                break
        if not found:
            missing.append(correct)

    if missing:
        print("ERROR: These replacement targets do not exist:")
        for m in missing:
            print(f"  {m}")
        return

    fixed_count = 0
    files_modified = set()

    for filepath in glob.glob("notes/*.md"):
        with open(filepath, "r") as f:
            content = f.read()

        new_content = content
        for broken, correct in REPLACEMENTS.items():
            # Replace [[broken]]
            old = "[[" + broken + "]]"
            new = "[[" + correct + "]]"
            if old in new_content:
                new_content = new_content.replace(old, new)
                fixed_count += 1
                files_modified.add(os.path.basename(filepath))

            # Handle pipe-aliased versions [[broken|display]]
            pattern = r"\[\[" + re.escape(broken) + r"\|([^\]]*?)\]\]"
            matches = re.findall(pattern, new_content)
            if matches:
                for m in matches:
                    old_link = "[[" + broken + "|" + m + "]]"
                    new_link = "[[" + correct + "|" + m + "]]"
                    new_content = new_content.replace(old_link, new_link)
                    fixed_count += 1
                    files_modified.add(os.path.basename(filepath))

        if new_content != content:
            with open(filepath, "w") as f:
                f.write(new_content)

    print(f"Fixed {fixed_count} broken link instances across {len(files_modified)} files")
    print()
    print("Modified files:")
    for f in sorted(files_modified):
        print(f"  {f}")


if __name__ == "__main__":
    main()
