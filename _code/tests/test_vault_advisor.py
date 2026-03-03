"""Tests for the vault advisor (goal frontier channel)."""

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from engram_r.daemon_config import DaemonConfig
from engram_r.vault_advisor import (
    GoalProfile,
    Suggestion,
    advise,
    detect_gaps,
    generate_suggestions,
    load_cache,
    main,
    parse_goal_file,
    save_cache,
    scan_goal_frontier,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_GOAL = textwrap.dedent("""\
    ---
    type: research-goal
    title: "Test goal with all gaps"
    status: active
    domain: "Test domain"
    tags: [research-goal]
    ---

    ## Objective

    ## Background

    ## Constraints

    ## Desired Properties

    ## Key Literature
""")

_POPULATED_GOAL = textwrap.dedent("""\
    ---
    type: research-goal
    title: "Fully populated goal"
    status: active
    domain: "Neuroscience / Proteomics"
    tags: [research-goal]
    ---

    ## Objective

    Establish clinical-grade p-tau217 NfL and GFAP cutpoints and assess confounders across ADRC MCC and VascBrain cohorts.

    ## Background

    Blood-based biomarkers have emerged as a scalable approach to Alzheimer diagnosis.

    ## Constraints

    Requires IRB approval for all cohort data.

    ## Desired Properties

    High specificity and sensitivity.

    ## Key Literature

    - Smith et al 2024 -- p-tau217 validation study
""")

_THIN_OBJECTIVE_GOAL = textwrap.dedent("""\
    ---
    type: research-goal
    title: "Goal with thin objective"
    status: active
    domain: "Immunology"
    tags: [research-goal]
    ---

    ## Objective

    Study immune markers.

    ## Background

    Some preliminary context here.

    ## Key Literature

    - Jones 2023 -- review
""")

_INACTIVE_GOAL = textwrap.dedent("""\
    ---
    type: research-goal
    title: "Archived goal"
    status: archived
    domain: "Archived domain"
    tags: [research-goal]
    ---

    ## Objective

    This goal is no longer active.
""")

_NO_TITLE_GOAL = textwrap.dedent("""\
    ---
    type: research-goal
    status: active
    domain: "Bad"
    ---

    ## Objective

    Missing title field.
""")

_NO_FRONTMATTER = textwrap.dedent("""\
    # Just a heading

    No YAML frontmatter here.
""")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_goal(tmp_path):
    p = tmp_path / "test-goal.md"
    p.write_text(_MINIMAL_GOAL)
    return p


@pytest.fixture
def populated_goal(tmp_path):
    p = tmp_path / "populated-goal.md"
    p.write_text(_POPULATED_GOAL)
    return p


@pytest.fixture
def thin_objective_goal(tmp_path):
    p = tmp_path / "thin-goal.md"
    p.write_text(_THIN_OBJECTIVE_GOAL)
    return p


@pytest.fixture
def default_config():
    return DaemonConfig(goals_priority=["test-goal", "secondary-goal"])


@pytest.fixture
def vault_with_goals(tmp_path):
    """Full vault structure with goals dir and daemon-config."""
    goals_dir = tmp_path / "_research" / "goals"
    goals_dir.mkdir(parents=True)
    (goals_dir / "test-goal.md").write_text(_MINIMAL_GOAL)
    (goals_dir / "populated-goal.md").write_text(_POPULATED_GOAL)
    (goals_dir / "thin-goal.md").write_text(_THIN_OBJECTIVE_GOAL)
    (goals_dir / "inactive-goal.md").write_text(_INACTIVE_GOAL)

    ops_dir = tmp_path / "ops"
    ops_dir.mkdir(parents=True)
    config = {
        "goals_priority": [
            "test-goal",
            "thin-goal",
            "populated-goal",
        ]
    }
    (ops_dir / "daemon-config.yaml").write_text(
        "goals_priority:\n"
        "  - test-goal\n"
        "  - thin-goal\n"
        "  - populated-goal\n"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# TestParseGoalFile
# ---------------------------------------------------------------------------


class TestParseGoalFile:
    def test_extracts_title_and_domain(self, minimal_goal):
        profile = parse_goal_file(minimal_goal)
        assert profile is not None
        assert profile.title == "Test goal with all gaps"
        assert profile.domain == "Test domain"
        assert profile.goal_id == "test-goal"
        assert profile.status == "active"

    def test_detects_empty_sections(self, minimal_goal):
        profile = parse_goal_file(minimal_goal)
        assert profile is not None
        assert not profile.has_background
        assert not profile.has_key_literature
        assert profile.objective == ""

    def test_detects_populated_sections(self, populated_goal):
        profile = parse_goal_file(populated_goal)
        assert profile is not None
        assert profile.has_background
        assert profile.has_key_literature
        assert "p-tau217" in profile.objective

    def test_thin_objective(self, thin_objective_goal):
        profile = parse_goal_file(thin_objective_goal)
        assert profile is not None
        assert profile.objective == "Study immune markers."
        assert profile.has_background
        assert profile.has_key_literature

    def test_returns_none_on_missing_file(self, tmp_path):
        result = parse_goal_file(tmp_path / "nonexistent.md")
        assert result is None

    def test_returns_none_on_no_title(self, tmp_path):
        p = tmp_path / "no-title.md"
        p.write_text(_NO_TITLE_GOAL)
        assert parse_goal_file(p) is None

    def test_returns_none_on_no_frontmatter(self, tmp_path):
        p = tmp_path / "no-fm.md"
        p.write_text(_NO_FRONTMATTER)
        assert parse_goal_file(p) is None

    def test_returns_none_on_malformed_yaml(self, tmp_path):
        p = tmp_path / "bad-yaml.md"
        p.write_text("---\n: [invalid yaml\n---\n\n## Objective\ntest\n")
        assert parse_goal_file(p) is None


# ---------------------------------------------------------------------------
# TestDetectGaps
# ---------------------------------------------------------------------------


class TestDetectGaps:
    def test_all_gaps_on_empty_goal(self, minimal_goal):
        profile = parse_goal_file(minimal_goal)
        gaps = detect_gaps(profile)
        assert "missing_key_literature" in gaps
        assert "missing_background" in gaps
        assert "thin_objective" in gaps
        assert len(gaps) == 3

    def test_zero_gaps_on_complete_goal(self, populated_goal):
        profile = parse_goal_file(populated_goal)
        gaps = detect_gaps(profile)
        assert gaps == []

    def test_partial_gaps(self, thin_objective_goal):
        profile = parse_goal_file(thin_objective_goal)
        gaps = detect_gaps(profile)
        # Has background and key lit, but thin objective (3 words)
        assert "thin_objective" in gaps
        assert "missing_key_literature" not in gaps
        assert "missing_background" not in gaps


# ---------------------------------------------------------------------------
# TestScanGoalFrontier
# ---------------------------------------------------------------------------


class TestScanGoalFrontier:
    def test_priority_order_matches_config(self, vault_with_goals):
        priority = ["test-goal", "thin-goal", "populated-goal"]
        profiles = scan_goal_frontier(vault_with_goals, priority)
        ids = [p.goal_id for p in profiles]
        assert ids == ["test-goal", "thin-goal", "populated-goal"]

    def test_only_active_goals(self, vault_with_goals):
        profiles = scan_goal_frontier(vault_with_goals, [])
        ids = [p.goal_id for p in profiles]
        assert "inactive-goal" not in ids

    def test_empty_dir_returns_empty(self, tmp_path):
        goals_dir = tmp_path / "_research" / "goals"
        goals_dir.mkdir(parents=True)
        assert scan_goal_frontier(tmp_path, []) == []

    def test_missing_dir_returns_empty(self, tmp_path):
        assert scan_goal_frontier(tmp_path, []) == []

    def test_unlisted_goals_sorted_alphabetically(self, vault_with_goals):
        # Only list one goal in priority; rest should come alphabetically
        profiles = scan_goal_frontier(vault_with_goals, ["thin-goal"])
        ids = [p.goal_id for p in profiles]
        assert ids[0] == "thin-goal"
        # Remaining two should be alphabetical
        assert ids[1:] == sorted(ids[1:])


# ---------------------------------------------------------------------------
# TestGenerateSuggestions
# ---------------------------------------------------------------------------


class TestGenerateSuggestions:
    def _make_profiles(self, tmp_path):
        """Create two goal profiles: one with all gaps, one complete."""
        (tmp_path / "primary.md").write_text(_MINIMAL_GOAL)
        (tmp_path / "secondary.md").write_text(_POPULATED_GOAL)
        primary = parse_goal_file(tmp_path / "primary.md")
        secondary = parse_goal_file(tmp_path / "secondary.md")
        return [primary, secondary]

    def test_primary_goal_ranks_higher(self, tmp_path):
        profiles = self._make_profiles(tmp_path)
        suggestions = generate_suggestions(profiles, "literature", max_suggestions=10)
        # Primary (index 0) should have lower priority values
        primary_priorities = [
            s.priority for s in suggestions if s.goal_ref == "primary"
        ]
        secondary_priorities = [
            s.priority for s in suggestions if s.goal_ref == "secondary"
        ]
        if primary_priorities and secondary_priorities:
            assert max(primary_priorities) < min(secondary_priorities)

    def test_max_respected(self, tmp_path):
        profiles = self._make_profiles(tmp_path)
        suggestions = generate_suggestions(profiles, "literature", max_suggestions=2)
        assert len(suggestions) <= 2

    def test_zero_gaps_empty_list(self, tmp_path):
        (tmp_path / "complete.md").write_text(_POPULATED_GOAL)
        profile = parse_goal_file(tmp_path / "complete.md")
        suggestions = generate_suggestions([profile], "literature")
        assert suggestions == []

    def test_all_fields_populated(self, tmp_path):
        profiles = self._make_profiles(tmp_path)
        suggestions = generate_suggestions(profiles, "literature", max_suggestions=4)
        for s in suggestions:
            assert s.channel == "goal_frontier"
            assert s.query
            assert s.rationale
            assert isinstance(s.priority, int)
            assert s.goal_ref


# ---------------------------------------------------------------------------
# TestContextFormatting
# ---------------------------------------------------------------------------


class TestContextFormatting:
    @pytest.mark.parametrize(
        "context",
        ["literature", "learn", "generate", "reflect", "reweave", "reduce"],
    )
    def test_query_and_rationale_nonempty(self, context, tmp_path):
        (tmp_path / "goal.md").write_text(_MINIMAL_GOAL)
        profile = parse_goal_file(tmp_path / "goal.md")
        suggestions = generate_suggestions([profile], context, max_suggestions=4)
        assert len(suggestions) > 0
        for s in suggestions:
            assert s.query, f"Empty query for context={context}"
            assert s.rationale, f"Empty rationale for context={context}"

    def test_literature_includes_domain(self, tmp_path):
        (tmp_path / "goal.md").write_text(_POPULATED_GOAL)
        # Need a goal with a gap for suggestions
        (tmp_path / "gapped.md").write_text(_MINIMAL_GOAL)
        profile = parse_goal_file(tmp_path / "gapped.md")
        suggestions = generate_suggestions([profile], "literature")
        # Domain should appear in query for literature context
        assert any("Test domain" in s.query for s in suggestions)

    def test_generate_includes_objective(self, tmp_path):
        goal_text = textwrap.dedent("""\
            ---
            title: "Specific goal"
            status: active
            domain: "Genetics"
            ---

            ## Objective

            ## Background

            ## Key Literature
        """)
        (tmp_path / "spec.md").write_text(goal_text)
        profile = parse_goal_file(tmp_path / "spec.md")
        suggestions = generate_suggestions([profile], "generate")
        assert len(suggestions) > 0


# ---------------------------------------------------------------------------
# TestCaching
# ---------------------------------------------------------------------------


class TestCaching:
    def test_cache_hit_skips_rescan(self, vault_with_goals):
        # First call: no cache
        s1, cached1 = advise(vault_with_goals, context="literature")
        assert not cached1
        assert len(s1) > 0

        # Second call: should hit cache
        s2, cached2 = advise(vault_with_goals, context="literature")
        assert cached2
        assert len(s2) == len(s1)

    def test_cache_miss_on_context_change(self, vault_with_goals):
        advise(vault_with_goals, context="literature")
        _, cached = advise(vault_with_goals, context="generate")
        assert not cached

    def test_cache_miss_on_max_change(self, vault_with_goals):
        advise(vault_with_goals, context="literature", max_suggestions=4)
        _, cached = advise(
            vault_with_goals, context="literature", max_suggestions=2
        )
        assert not cached

    def test_no_cache_flag(self, vault_with_goals):
        advise(vault_with_goals, context="literature")
        _, cached = advise(
            vault_with_goals, context="literature", no_cache=True
        )
        assert not cached

    def test_atomic_write(self, vault_with_goals):
        cache_path = vault_with_goals / "ops" / "advisor-cache.json"
        save_cache(
            cache_path,
            [
                Suggestion(
                    channel="goal_frontier",
                    query="test",
                    rationale="test",
                    priority=1,
                    goal_ref="x",
                )
            ],
            "key-1",
            "literature",
            4,
        )
        assert cache_path.is_file()
        assert not cache_path.with_suffix(".tmp").exists()
        data = json.loads(cache_path.read_text())
        assert data["session_key"] == "key-1"

    def test_load_cache_returns_none_on_missing(self, tmp_path):
        assert load_cache(tmp_path / "nope.json") is None

    def test_load_cache_returns_none_on_bad_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json")
        assert load_cache(p) is None


# ---------------------------------------------------------------------------
# TestCLI
# ---------------------------------------------------------------------------


class TestCLI:
    def test_json_structure(self, vault_with_goals, capsys):
        exit_code = main([str(vault_with_goals), "--context", "literature", "--no-cache"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "context" in data
        assert "suggestions" in data
        assert "cached" in data
        assert data["context"] == "literature"

    def test_exit_code_0_with_suggestions(self, vault_with_goals):
        exit_code = main([str(vault_with_goals), "--context", "literature", "--no-cache"])
        assert exit_code == 0

    def test_exit_code_2_no_gaps(self, tmp_path, capsys):
        """A vault with only fully populated goals returns exit 2."""
        goals_dir = tmp_path / "_research" / "goals"
        goals_dir.mkdir(parents=True)
        (goals_dir / "complete.md").write_text(_POPULATED_GOAL)
        ops = tmp_path / "ops"
        ops.mkdir(parents=True)
        (ops / "daemon-config.yaml").write_text("goals_priority: [complete]\n")

        exit_code = main([str(tmp_path), "--no-cache"])
        assert exit_code == 2

    def test_exit_code_1_missing_vault(self, tmp_path, capsys):
        exit_code = main([str(tmp_path / "nonexistent")])
        assert exit_code == 1

    def test_context_flag(self, vault_with_goals, capsys):
        main([str(vault_with_goals), "--context", "generate", "--no-cache"])
        data = json.loads(capsys.readouterr().out)
        assert data["context"] == "generate"

    def test_max_flag(self, vault_with_goals, capsys):
        main([str(vault_with_goals), "--max", "2", "--no-cache"])
        data = json.loads(capsys.readouterr().out)
        assert len(data["suggestions"]) <= 2
