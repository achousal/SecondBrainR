# EngramR: Pitch and Business Plan

## The Elevator Pitch

**EngramR turns your lab's scattered knowledge into ranked, actionable research priorities -- automatically.**

Every lab generates more observations, paper reads, and experimental results than any single person can track. The best ideas don't always win -- the loudest ones do. EngramR fixes this by building a persistent knowledge graph from your team's daily work, then generating, debating, and ranking testable hypotheses from that evidence. The result: a leaderboard of research directions ranked by evidence strength, not whoever had time to champion them at lab meeting.

---

## The Problem (What PIs Actually Deal With)

### 1. Knowledge walks out the door
A postdoc reads 200 papers during their tenure. When they leave, that context leaves with them. The next trainee starts from scratch. There is no institutional memory beyond what fits in a shared drive of PDFs.

### 2. Observations die in notebooks
A tech notices something unexpected. A grad student sees a pattern that doesn't match predictions. These are real signals, but without a system to capture and connect them, they fade by Friday. The lab loses information it already paid for.

### 3. Priority setting is ad hoc
Ten good project ideas compete for three experimental slots. Which ones have the most evidence behind them? Which ones can be tested with data you already have? Without a structured way to compare, the PI relies on intuition and whoever made the strongest case in lab meeting. This works -- until it doesn't.

### 4. Literature is consumed but not compounded
Papers are read, discussed once, and filed. The cumulative insight across 50 papers on the same topic never gets synthesized into a single, queryable resource. Every new student re-reads the same papers and draws slightly different conclusions.

### 5. Grant writing starts from scratch every time
Specific aims need evidence trails. Preliminary data needs to be connected to mechanism. Every grant cycle, the PI reconstructs this narrative manually from memory and scattered files.

---

## The Solution

EngramR is a research knowledge system that runs alongside your existing workflow. It does three things:

### Capture and Connect
- Team members contribute observations via Slack messages, paper uploads, or data uploads
- The system extracts structured claims from each source and links them to everything already in the graph
- Over time, the graph becomes a searchable, interconnected map of everything your lab knows

### Generate and Rank Hypotheses
- When evidence accumulates around a topic, the system generates testable hypotheses -- each with mechanism, predictions, and falsification criteria
- Hypotheses compete in pairwise debates scored on evidence support, testability, and novelty
- An Elo rating system produces a continuously updated leaderboard
- The system learns what makes strong hypotheses in your domain and improves across cycles

### Pre-Specify and Execute
- Top-ranked hypotheses come with pre-specified analysis plans
- Experimental results feed back into the graph, updating ratings
- The leaderboard always reflects the current state of evidence

---

## What It Looks Like in Practice

### Day 1: Onboarding (30 minutes)
Run `/onboard`. The system scans your lab's projects, datasets, and infrastructure. It creates a structured inventory of what you have and what you work on. No data migration. No reformatting. It reads what exists.

### Week 1: The graph starts growing
Papers land in the inbox. `/reduce` extracts atomic claims. `/reflect` connects them. Within a week, the system has 50-100 structured claims linked into a navigable graph. Already more organized than any shared reference manager.

### Month 1: Hypotheses emerge
Evidence density crosses thresholds. `/generate` produces testable hypotheses grounded in the accumulated claims. `/tournament` ranks them. The PI now has a leaderboard of evidence-ranked research directions. Grant aims write themselves from the top three.

### Month 3: The flywheel
Experimental results feed back. The graph is dense enough that new observations land in a web of existing connections. The tech's unexpected finding connects to the postdoc's literature note from last month. The system surfaces the connection before lab meeting. Priorities update in real time.

### Year 1: Institutional memory
A new student joins. Instead of three weeks of orientation, they browse the knowledge graph and the hypothesis leaderboard. They understand what the lab knows, what it's testing, and why -- in an afternoon. When the senior postdoc leaves, their knowledge stays.

---

## Why This Isn't Just Another Note-Taking App

| Feature | Shared Drive / Notion / Zotero | EngramR |
|---|---|---|
| Stores papers | Yes | Yes |
| Extracts structured claims | No | Yes -- atomic, linked, searchable |
| Connects observations across team members | No | Yes -- automatic graph linking |
| Generates testable hypotheses | No | Yes -- with mechanism and predictions |
| Ranks hypotheses by evidence | No | Yes -- Elo-rated pairwise debates |
| Pre-specifies analysis plans | No | Yes -- attached to each hypothesis |
| Learns what makes good hypotheses in your domain | No | Yes -- meta-review feedback loop |
| Preserves institutional memory | Barely | Yes -- structured and persistent |

---

## Cost Structure

### Infrastructure Costs
- **AI compute**: Claude API usage. Typical lab: $100-300/month depending on volume of papers processed and hypotheses generated
- **Storage**: Plain markdown files. Negligible. Runs on any machine or shared drive
- **Software**: Open-source (MIT license). Zero licensing fees

### Human Costs
- **Setup**: 1 day for onboarding. No IT department needed
- **Daily use**: Zero additional meetings. Team members contribute via Slack or file drops during their normal workflow
- **Maintenance**: Self-maintaining. Health checks flag issues automatically

### Total Cost of Ownership
- **Small lab (3-5 people)**: ~$150/month in API costs
- **Medium lab (6-15 people)**: ~$300/month in API costs
- **Large lab or multi-lab**: ~$500/month in API costs

---

## Value Proposition (in PI language)

### 1. Better grant applications, faster
Specific aims backed by structured evidence trails. Preliminary data connected to mechanism. Debate transcripts document why your approach beats alternatives. The reviewer's question "why this hypothesis over alternatives?" is already answered.

### 2. Smarter resource allocation
Filter the leaderboard by "testable with data we already have." Three candidates surface with different cost profiles. The decision takes minutes, not a lab meeting. The evidence trail is there for anyone to review.

### 3. Trainee productivity from day one
New lab members browse the graph instead of re-reading 200 papers. They see what the lab knows, what it's testing, and where the gaps are. Orientation time drops from weeks to days.

### 4. Nothing is lost
The tech's unexpected finding from Tuesday connects to the grad student's dataset from March. The postdoc's literature review compounds with the PI's new direction. Every observation persists and accumulates value.

### 5. Publication opportunities surface automatically
Convergent evidence clusters flag natural paper outlines. The gap analysis shows where one more experiment would complete a story. You stop discovering publication-ready results six months late.

---

## Competitive Landscape

| Tool | What it does | What it doesn't do |
|---|---|---|
| Zotero / Mendeley | Reference management | No claim extraction, no hypothesis generation, no ranking |
| Notion / Confluence | Team wiki | No structured knowledge graph, no automated connections |
| Semantic Scholar / Elicit | Literature search + summaries | No persistent lab knowledge, no hypothesis competition |
| Lab notebooks (electronic) | Record experiments | No cross-team synthesis, no evidence ranking |
| Google's AI Co-Scientist | Hypothesis generation | Cloud-only, no persistent lab knowledge graph, no open-source |

EngramR is the only system that combines persistent knowledge accumulation with competitive hypothesis ranking in a self-improving loop -- and it's open-source, runs locally, and your data never leaves your machines.

---

## Adoption Path

EngramR is not an all-or-nothing commitment. Adoption is a gradient:

1. **Observer** -- Browse the graph and leaderboard. Zero effort, immediate context.
2. **Contributor** -- Send observations via Slack or drop papers in the inbox. Minimal effort, compounds the graph.
3. **Analyst** -- Run `/eda`, `/experiment`, feed results back. Active engagement, direct return.
4. **Director** -- Define goals, run tournaments, allocate based on the leaderboard. Strategic use.

A lab can start with one person (the PI or a motivated trainee) and expand as value becomes visible. No training sessions required. No workflow disruption.

---

## Scaling: Multi-Lab Federation

Each lab runs its own EngramR instance. Federation bridges connect them selectively:
- Lab A's methodological insight links to Lab B's independent finding
- Collaboration opportunities surface from evidence overlap, not social networking
- Data stays local. Only claims and hypothesis metadata cross boundaries
- PIs decide what to share. Nothing is automatic

This inverts the collaboration model: instead of deciding to collaborate and then looking for overlap, the system surfaces the overlap first.

---

## Risk Mitigation

| Risk                                      | Mitigation                                                                                                            |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| AI hallucination in hypothesis generation | Every claim traces to a source document. Provenance chain is auditable. Fabricated citations are mechanically blocked |
| Data privacy                              | Runs locally. No cloud dependency. PII auto-redaction in EDA. Data never leaves lab machines                          |
| Vendor lock-in                            | Open-source (MIT). Plain markdown files. Zero proprietary formats.                                                    |
| Adoption fatigue                          | Gradient adoption. Start with one person. No meetings. No training. Value visible within one week                     |
| PI time investment                        | The system does the synthesis. The PI makes decisions. Net time savings from week one                                 |

---

## Ask

We are looking for:
1. **Pilot labs** willing to run EngramR for 3 months and provide structured feedback
2. **PIs** interested in co-developing domain-specific profiles for their field
3. **Institutional partners** exploring AI-augmented research infrastructure

The system is live, open-source, and running in production. The question isn't whether it works -- it's which labs want to compound their knowledge first.

---

## Contact

GitHub: [achousal/EngramR](https://github.com/achousal/EngramR)
License: MIT
