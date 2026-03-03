# Engram Reactor

## The problem is not ideas. It is visibility.

Every lab meeting, we discuss many promising directions. How do we decide which ones to pursue, and based on what evidence? Without a system to track and compare them, the evidence sits fragmented -- so no one can reliably see the full picture.

When I joined the lab, it took me three weeks just to understand what each team member was working on and where the group was heading. That context lived in people's heads -- in scattered conversations, slides, in the PI's intuition. There was no single place to look. A postdoc reads a paper that contradicts an assumption but files it under "interesting" and moves on. A technician notices something unexpected but has no time to chase it down. These insights are real, but without a system to persist them, they fade.

The ideas that do surface face a harder problem: our lab has finite bench hours, finite instrument budget, finite analyst bandwidth. Ten good ideas compete for three experimental slots. The ones that get pursued are not always the ones best supported by evidence -- they are the ones someone had time to champion.

The gap is not analytical skill or scientific creativity. It is the infrastructure to accumulate evidence and convert it into prioritized action.

> **Note:** This scenario uses a biomedical lab as an example; EngramR works with any research domain.

---

Two capabilities make this possible: a [knowledge architecture](https://github.com/agenticnotetaking/arscontexta) that turns observations into a persistent graph of structured claims, and a [co-scientist engine](https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/) that generates, debates, and ranks testable predictions from that evidence. A knowledge graph without hypothesis generation is a well-organized archive; a hypothesis engine without structured evidence is speculation. The combination shifts the bottleneck from human attention to evidence quality.

## A morning

**9:02am** -- The tech notices something unexpected in her experiment. She sends a Slack message.

> "Seeing unexpected protein accumulation in the treated group at 24h. Wasn't part of the original hypothesis."

She goes back to her bench.

**9:03am** -- The reactor extracts a structured claim, tags it, and searches the knowledge graph. Three connections surface: a grad student's dataset from March that showed the same pattern emerging, a paper the postdoc read last week about a related mechanism, and an existing hypothesis that predicted this involvement -- but through a different mechanism. The claim is linked to all three. A tension is flagged: the data supports the prediction but not the proposed mechanism.

**9:40am** -- The postdoc gets a Slack notification: a new observation was linked to a literature note he submitted last week. He did not know anyone in the lab was generating data in this area. He taps through, reads the tension flag, and sends a follow-up.

> "Her data fits the alternative pathway better. If that's the mechanism, we should see it in the longitudinal dataset we already have."

**9:45am** -- The reactor links the postdoc's claim to the growing cluster. Evidence density crosses the threshold. The system generates an evolved version of the hypothesis -- same core prediction, updated mechanism based on the converging evidence. The evolved hypothesis comes with a pre-specified analysis plan and statistical tests.

**10:00am** -- The evolved hypothesis enters the tournament and debates the original head-to-head on specificity, evidence support, and testability. It wins -- three independent data sources where the original had one. Elo updates. Debate transcript stored.

**11:15am** -- The postdoc executes the analysis. He does not start from scratch -- the hypothesis note contains the test, the parameters, and suggested experiments. Results: two of three predictions confirmed. One is inconclusive. The system logs the experiment, links results to predictions, flags the gap for the next debate cycle.

**11:30am** -- The graph updates. The hypothesis holds its rank but carries a documented weakness. Next round, that weakness is fair game.

One morning. Two people sent messages while doing their actual work. The reactor connected their observations, evolved a hypothesis, debated it, ranked it, and pre-specified the analysis. By late morning, results were in and feeding back into the system. Nobody stopped what they were doing.

## An anomaly

A grad student uploads her dataset for exploratory analysis. The system generates a report -- plots in the lab's standard style, summary statistics, all processed locally. One finding stands out: a pattern in her data that does not match any existing hypothesis in the graph.

She asks: "What could explain this?"

The reactor searches the knowledge graph. It finds six related claims from literature and prior observations, identifies two possible mechanisms, and generates a hypothesis from the anomaly -- complete with predictions, a validation plan using data already on the server, and falsification criteria. The hypothesis enters the tournament that week.

The anomaly that would have been a footnote in her thesis is now a ranked project proposal with structured evidence behind it.

## Administration

**Writing aims from evidence.** The PI needs specific aims for a new grant. She defines a research goal in the reactor. Six hypotheses generate from the existing graph. A tournament runs to rank them. Three survive -- each with mechanism, predictions, and preliminary data already identified from the lab's own datasets. The debate transcripts document why these beat the alternatives.

**Allocating resources.** The lab has a slot for a new project. The PI filters the leaderboard by hypotheses testable with existing data. Three candidates surface with different cost profiles: one needs only the longitudinal dataset from January, another needs survey data already on the server, a third would require a new cohort. The decision takes minutes. The evidence trail is there for anyone to review.

**New direction.** The PI reads a paper that opens unexplored territory. She defines a new goal. The graph already has twelve relevant claims and two projects with transferable data. Three seed hypotheses generate from what the lab already knows. The new direction starts with context, not from zero.

## Across labs

One reactor per lab is valuable. Multiple reactors compound.

Two labs in adjacent areas each run their own instance, generating and ranking hypotheses against their own data. The knowledge graphs bridge selectively -- Lab A's methodological observation connects to Lab B's independent finding from a different dataset. Neither lab would have seen it alone.

This inverts the traditional collaboration model. Instead of two PIs deciding to collaborate and then looking for scientific overlap, the system surfaces the overlap first. The PIs decide whether to cross the bridge.

---

The reactor is running. The question is which ideas to put into it.
