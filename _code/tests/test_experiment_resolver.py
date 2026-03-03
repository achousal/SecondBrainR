"""Tests for experiment_resolver -- empirical Elo adjustments and status transitions."""

import pytest

from engram_r.experiment_resolver import (
    OUTCOME_MAP,
    EmpiricalUpdate,
    apply_empirical_update,
    compute_empirical_update,
)
from engram_r.hypothesis_parser import (
    EMPIRICALLY_RESOLVED_STATUSES,
    ensure_section,
    filter_tournament_eligible,
    parse_hypothesis_note,
)


def _hyp_note(status: str = "reviewed", elo: int = 1275) -> str:
    return (
        "---\n"
        "type: hypothesis\n"
        f"title: \"Test hypothesis\"\n"
        f"id: H-TEST-001\n"
        f"status: {status}\n"
        f"elo: {elo}\n"
        "matches: 5\n"
        "wins: 3\n"
        "losses: 2\n"
        "generation: 2\n"
        "research_goal: \"[[goal-test]]\"\n"
        "tags: [hypothesis]\n"
        "created: 2026-02-22\n"
        "updated: 2026-02-23\n"
        "linked_experiments: []\n"
        "---\n\n"
        "## Core Claim\n\n"
        "Test hypothesis claim.\n\n"
        "## Assumptions\n\n"
        "- Assumption 1\n"
    )


def _exp_note(outcome: str = "negative", exp_id: str = "EXP-002") -> str:
    return (
        "---\n"
        "type: experiment\n"
        f"title: \"Test experiment\"\n"
        f"id: {exp_id}\n"
        f"outcome: \"{outcome}\"\n"
        f"status: completed\n"
        "linked_hypotheses: [\"[[H-TEST-001]]\"]\n"
        "created: 2026-02-23\n"
        "---\n\n"
        "## Results\n\n"
        "Gate 4 STOP.\n"
    )


class TestComputeEmpiricalUpdate:
    def test_negative_outcome_lowers_elo(self):
        update = compute_empirical_update(_hyp_note(), _exp_note("negative"))
        assert update is not None
        assert update.new_elo < 1275
        assert update.delta < 0
        assert update.new_status == "tested-negative"

    def test_null_outcome_lowers_elo(self):
        update = compute_empirical_update(_hyp_note(), _exp_note("null"))
        assert update is not None
        assert update.new_elo < 1275
        assert update.new_status == "tested-negative"

    def test_positive_outcome_raises_elo(self):
        update = compute_empirical_update(_hyp_note(), _exp_note("positive"))
        assert update is not None
        assert update.new_elo > 1275
        assert update.delta > 0
        assert update.new_status == "tested-positive"

    def test_partial_outcome_no_elo_change(self):
        update = compute_empirical_update(_hyp_note(), _exp_note("partial"))
        assert update is not None
        assert update.delta == 0.0
        assert update.new_elo == 1275
        assert update.new_status == "tested-partial"

    def test_blocked_outcome_no_elo_change(self):
        update = compute_empirical_update(_hyp_note(), _exp_note("blocked"))
        assert update is not None
        assert update.delta == 0.0
        assert update.new_status == "analytically-blocked"

    def test_already_resolved_returns_none(self):
        result = compute_empirical_update(
            _hyp_note(status="tested-negative"), _exp_note("negative")
        )
        assert result is None

    def test_no_outcome_returns_none(self):
        exp_no_outcome = (
            "---\n"
            "type: experiment\n"
            "title: \"No outcome\"\n"
            "status: designed\n"
            "---\n\n"
            "## Objective\n\nTBD\n"
        )
        result = compute_empirical_update(_hyp_note(), exp_no_outcome)
        assert result is None

    def test_completed_null_maps_to_tested_negative(self):
        update = compute_empirical_update(_hyp_note(), _exp_note("completed-null"))
        assert update is not None
        assert update.new_status == "tested-negative"
        assert update.delta < 0

    def test_reason_contains_experiment_id(self):
        update = compute_empirical_update(
            _hyp_note(), _exp_note("negative", exp_id="EXP-042")
        )
        assert update is not None
        assert "EXP-042" in update.reason


class TestApplyEmpiricalUpdate:
    def test_frontmatter_updated(self):
        update = EmpiricalUpdate(
            hypothesis_id="H-TEST-001",
            old_elo=1275,
            new_elo=1263.5,
            delta=-11.5,
            new_status="tested-negative",
            reason="Experiment EXP-002: hypothesis refuted",
        )
        result = apply_empirical_update(_hyp_note(), update, "[[EXP-002]]")
        parsed = parse_hypothesis_note(result)
        assert parsed.status == "tested-negative"
        assert parsed.elo == 1263.5
        assert parsed.frontmatter["empirical_outcome"] == "tested-negative"
        assert parsed.frontmatter["empirical_experiment"] == "[[EXP-002]]"

    def test_empirical_section_created(self):
        update = EmpiricalUpdate(
            hypothesis_id="H-TEST-001",
            old_elo=1275,
            new_elo=1263.5,
            delta=-11.5,
            new_status="tested-negative",
            reason="Experiment EXP-002: hypothesis refuted",
        )
        result = apply_empirical_update(_hyp_note(), update, "[[EXP-002]]")
        assert "## Empirical Evidence" in result
        assert "1275 -> 1263.5" in result
        assert "[[EXP-002]]" in result

    def test_empirical_section_preserved_if_exists(self):
        hyp_with_section = _hyp_note() + "\n## Empirical Evidence\n\nExisting entry.\n"
        update = EmpiricalUpdate(
            hypothesis_id="H-TEST-001",
            old_elo=1275,
            new_elo=1263.5,
            delta=-11.5,
            new_status="tested-negative",
            reason="Experiment EXP-002: hypothesis refuted",
        )
        result = apply_empirical_update(hyp_with_section, update)
        # Should have both old and new content
        assert "Existing entry." in result
        assert "1275 -> 1263.5" in result
        # Should only have one ## Empirical Evidence heading
        assert result.count("## Empirical Evidence") == 1


class TestEnsureSection:
    def test_creates_missing_section(self):
        content = "---\ntype: hypothesis\n---\n\n## Core Claim\n\nSome text.\n"
        result = ensure_section(content, "Empirical Evidence")
        assert "## Empirical Evidence" in result

    def test_noop_when_exists(self):
        content = "---\ntype: hypothesis\n---\n\n## Empirical Evidence\n\nExisting.\n"
        result = ensure_section(content, "Empirical Evidence")
        assert result == content

    def test_inserts_after_specified_section(self):
        content = (
            "---\ntype: hypothesis\n---\n\n"
            "## Core Claim\n\nClaim text.\n\n"
            "## Assumptions\n\nAssumption text.\n"
        )
        result = ensure_section(content, "Empirical Evidence", after_section="Core Claim")
        # New section should appear between Core Claim and Assumptions
        core_pos = result.index("## Core Claim")
        emp_pos = result.index("## Empirical Evidence")
        assump_pos = result.index("## Assumptions")
        assert core_pos < emp_pos < assump_pos


class TestFilterTournamentEligible:
    def test_excludes_tested_negative(self):
        hyps = [
            parse_hypothesis_note(_hyp_note(status="reviewed")),
            parse_hypothesis_note(_hyp_note(status="tested-negative")),
        ]
        eligible = filter_tournament_eligible(hyps)
        assert len(eligible) == 1
        assert eligible[0].status == "reviewed"

    def test_excludes_all_resolved_statuses(self):
        hyps = [
            parse_hypothesis_note(_hyp_note(status=s))
            for s in EMPIRICALLY_RESOLVED_STATUSES
        ]
        eligible = filter_tournament_eligible(hyps)
        assert len(eligible) == 0

    def test_preserves_active_hypotheses(self):
        hyps = [
            parse_hypothesis_note(_hyp_note(status="proposed")),
            parse_hypothesis_note(_hyp_note(status="reviewed")),
            parse_hypothesis_note(_hyp_note(status="priority-test")),
        ]
        eligible = filter_tournament_eligible(hyps)
        assert len(eligible) == 3

    def test_empty_list(self):
        assert filter_tournament_eligible([]) == []
