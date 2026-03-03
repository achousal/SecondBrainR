# Methodology

## Scientific Method Mapping

Each co-scientist skill maps to a step in the scientific method. Together they form a complete research loop that self-improves through feedback.

| Skill | Scientific Method Step | Reasoning Type |
|---|---|---|
| `/research` | Research design / Supervision | Meta-cognition: selects which method step to apply next |
| `/generate` | Hypothesis formation | Abductive inference: best explanation from available evidence |
| `/reflect` | Peer review / Verification | Deductive + critical: tests internal consistency and evidence fit |
| `/tournament` | Competitive falsification | Adversarial: pairwise comparison forces relative ranking |
| `/evolve` | Theory refinement | Synthesis: combines strengths, addresses weaknesses |
| `/landscape` | Literature review / Gap analysis | Inductive: pattern recognition across the hypothesis space |
| `/meta-review` | Second-order learning | Meta-analysis: extracts patterns from the review process itself |
| `/literature` | Evidence gathering | Empirical: systematic search for published findings |
| `/experiment` | Experimental design + logging | Empirical: structured recording of tests and results |
| `/eda` | Exploratory analysis | Inductive: data-driven pattern discovery |
| `/plot` | Visualization / Communication | Descriptive: visual representation of data and results |
| `/project` | Project management | Organizational: tracks research context and infrastructure |

## The Self-Improving Loop

See [[architecture]] for the full loop diagram.

1. **Generate**: create hypotheses grounded in literature and prior feedback.
2. **Reflect**: critically evaluate each hypothesis across multiple dimensions.
3. **Tournament**: rank hypotheses through competitive pairwise debate (Elo system).
4. **Meta-review**: synthesize patterns from debates and reviews into actionable recommendations.
5. **Feedback**: meta-review output is injected into the next generation/evolution cycle.

This loop improves quality across cycles without model fine-tuning. The improvement mechanism is prompt injection via vault state: meta-review notes persist in the vault and are read by subsequent skill invocations.

## Why This Works

- **No fine-tuning needed**: quality improves through better prompts, not parameter updates.
- **Transparent**: every decision, score, and recommendation is recorded in the vault as a structured note.
- **Auditable**: the full chain of reasoning (generation -> review -> debate -> meta-review) is traceable through vault links.
- **User-controlled**: the human researcher drives each step and can override any automated judgment.

## Knowledge Processing Pipeline

Alongside the co-scientist loop, I maintain a general knowledge processing pipeline:

1. **Capture** -- raw material enters inbox/ with zero friction
2. **Reduce** -- extract atomic claims from sources, each titled as a prose proposition
3. **Reflect** -- find connections between claims, update topic maps
4. **Reweave** -- revisit old claims with new context, update backward connections
5. **Verify** -- quality-check descriptions, schema, links

### Principles
- Prose-as-title: every claim is a proposition
- Wiki links: connections as graph edges
- Topic maps: attention management hubs
- Capture fast, process slow
- Fresh context per phase for quality-critical work

---

Topics:
- [[identity]]
- [[goals]]
