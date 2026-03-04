"""Tests for the vault advisor (goal frontier channel)."""

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from engram_r.daemon_config import DaemonConfig
from engram_r.vault_advisor import (
    GoalProfile,
    PhaseTip,
    QueuePhaseState,
    SessionTip,
    Suggestion,
    VaultSnapshot,
    _find_high_demand_abstract_sources,
    advise,
    build_vault_snapshot,
    detect_gaps,
    detect_phase_tips,
    detect_session_tips,
    generate_phase_suggestions,
    generate_session_suggestions,
    generate_suggestions,
    load_cache,
    main,
    parse_goal_file,
    save_cache,
    scan_extract_scopes,
    scan_queue_phases,
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


# ---------------------------------------------------------------------------
# Pipeline Tip Channel -- Task file helpers
# ---------------------------------------------------------------------------


def _make_task_file(
    *,
    source_task: str,
    classification: str = "open",
    reduce_filled: bool = True,
    create_filled: bool = False,
    enrich_filled: bool = False,
    reflect_filled: bool = False,
    reweave_filled: bool = False,
    verify_filled: bool = False,
    is_enrichment: bool = False,
) -> str:
    """Build a per-claim task file with controlled phase fill state."""
    fm_type = "enrichment" if is_enrichment else "claim"
    claim_title = f"test claim from {source_task}"
    fm = textwrap.dedent(f"""\
        ---
        {fm_type}: "{claim_title}"
        classification: "{classification}"
        source_task: {source_task}
        ---

        # {'Enrichment' if is_enrichment else 'Claim'}: {claim_title}

    """)

    reduce_body = (
        f"Extracted from {source_task}. This is a test claim."
        if reduce_filled
        else "(to be filled by reduce phase)"
    )

    if is_enrichment:
        enrich_body = (
            "Enrichment applied successfully."
            if enrich_filled
            else "(to be filled by enrich phase)"
        )
        create_section = f"## Enrich\n{enrich_body}\n"
    else:
        create_body = (
            "Claim created in notes/."
            if create_filled
            else "(to be filled by create phase)"
        )
        create_section = f"## Create\n{create_body}\n"

    reflect_body = (
        "Connections found."
        if reflect_filled
        else "(to be filled by /reflect phase)"
    )
    reweave_body = (
        "Backward links added."
        if reweave_filled
        else "(to be filled by /reweave phase)"
    )
    verify_body = (
        "Verified OK."
        if verify_filled
        else "(to be filled by /verify phase)"
    )

    return (
        fm
        + f"## Reduce Notes\n{reduce_body}\n\n---\n\n"
        + create_section
        + f"\n## /reflect\n{reflect_body}\n"
        + f"\n## /reweave\n{reweave_body}\n"
        + f"\n## /verify\n{verify_body}\n"
    )


# ---------------------------------------------------------------------------
# TestScanQueuePhases
# ---------------------------------------------------------------------------


class TestScanQueuePhases:
    def test_empty_queue(self, tmp_path):
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)
        state = scan_queue_phases(tmp_path)
        assert state.total_tasks == 0
        assert state.sources == set()
        assert state.phase_counts == {}

    def test_no_queue_dir(self, tmp_path):
        state = scan_queue_phases(tmp_path)
        assert state.total_tasks == 0

    def test_mixed_phases_two_sources(self, tmp_path):
        """Source A has create-pending tasks, Source B has reflect-pending tasks."""
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)

        # Source A: reduce done, create pending
        (queue_dir / "source-a-001.md").write_text(
            _make_task_file(
                source_task="source-a",
                reduce_filled=True,
                create_filled=False,
            )
        )
        (queue_dir / "source-a-002.md").write_text(
            _make_task_file(
                source_task="source-a",
                reduce_filled=True,
                create_filled=False,
            )
        )

        # Source B: create done, reflect pending
        (queue_dir / "source-b-001.md").write_text(
            _make_task_file(
                source_task="source-b",
                reduce_filled=True,
                create_filled=True,
                reflect_filled=False,
            )
        )
        (queue_dir / "source-b-002.md").write_text(
            _make_task_file(
                source_task="source-b",
                reduce_filled=True,
                create_filled=True,
                reflect_filled=False,
            )
        )

        state = scan_queue_phases(tmp_path)
        assert state.total_tasks == 4
        assert state.sources == {"source-a", "source-b"}
        assert state.phase_counts.get("create", 0) == 2
        assert state.phase_counts.get("reflect", 0) == 2
        assert "source-a" in state.sources_with_pending_create
        assert "source-b" in state.sources_with_pending_reflect

    def test_enrichment_tasks_detected(self, tmp_path):
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)

        (queue_dir / "source-c-010.md").write_text(
            _make_task_file(
                source_task="source-c",
                is_enrichment=True,
                reduce_filled=True,
                enrich_filled=False,
            )
        )

        state = scan_queue_phases(tmp_path)
        assert state.total_tasks == 1
        assert state.phase_counts.get("enrich", 0) == 1
        assert "source-c" in state.sources_with_pending_enrich


# ---------------------------------------------------------------------------
# TestDetectPhaseTips
# ---------------------------------------------------------------------------


class TestDetectPhaseTips:
    def test_reduce_before_reflect(self):
        """2 sources, one create-pending + one reflect-pending -> tip."""
        state = QueuePhaseState(
            total_tasks=4,
            sources={"source-a", "source-b"},
            phase_counts={"create": 2, "reflect": 2},
            sources_with_pending_create={"source-a"},
            sources_with_pending_reflect={"source-b", "source-a"},
        )
        tips = detect_phase_tips(state)
        tip_ids = [t.tip_id for t in tips]
        assert "reduce_before_reflect" in tip_ids

    def test_enrich_only_triggers_reduce_before_reflect(self):
        """Enrich pending (no create) + reflect ready -> tip with 'enrich' label."""
        state = QueuePhaseState(
            total_tasks=6,
            sources={"source-a", "source-b", "source-c"},
            phase_counts={"enrich": 2, "reflect": 4},
            sources_with_pending_create=set(),
            sources_with_pending_enrich={"source-c"},
            sources_with_pending_reflect={"source-a", "source-b"},
        )
        tips = detect_phase_tips(state)
        tip_ids = [t.tip_id for t in tips]
        assert "reduce_before_reflect" in tip_ids
        # Message should say "enrich" not "reduce/create"
        tip = next(t for t in tips if t.tip_id == "reduce_before_reflect")
        assert "enrich" in tip.message
        assert "reduce/create" not in tip.message

    def test_batch_reflect_ready(self):
        """2 sources, all reflect-pending, none create/enrich-pending."""
        state = QueuePhaseState(
            total_tasks=4,
            sources={"source-a", "source-b"},
            phase_counts={"reflect": 4},
            sources_with_pending_create=set(),
            sources_with_pending_enrich=set(),
            sources_with_pending_reflect={"source-a", "source-b"},
        )
        tips = detect_phase_tips(state)
        tip_ids = [t.tip_id for t in tips]
        assert "batch_reflect_ready" in tip_ids
        assert "reduce_before_reflect" not in tip_ids

    def test_batch_reflect_blocked_by_enrich(self):
        """Enrich pending blocks batch_reflect_ready."""
        state = QueuePhaseState(
            total_tasks=4,
            sources={"source-a", "source-b"},
            phase_counts={"enrich": 1, "reflect": 3},
            sources_with_pending_create=set(),
            sources_with_pending_enrich={"source-b"},
            sources_with_pending_reflect={"source-a", "source-b"},
        )
        tips = detect_phase_tips(state)
        tip_ids = [t.tip_id for t in tips]
        assert "batch_reflect_ready" not in tip_ids
        assert "reduce_before_reflect" in tip_ids

    def test_reweave_after_reflect(self):
        """Coexisting reflect and reweave pending -> tip."""
        state = QueuePhaseState(
            total_tasks=4,
            sources={"source-a"},
            phase_counts={"reflect": 2, "reweave": 2},
            sources_with_pending_create=set(),
            sources_with_pending_reflect={"source-a"},
            sources_with_pending_reweave={"source-a"},
        )
        tips = detect_phase_tips(state)
        tip_ids = [t.tip_id for t in tips]
        assert "reweave_after_reflect" in tip_ids

    def test_no_tips_single_source_reflect(self):
        """Only 1 source with reflect-pending -> no cross-source tips."""
        state = QueuePhaseState(
            total_tasks=2,
            sources={"source-a"},
            phase_counts={"reflect": 2},
            sources_with_pending_create=set(),
            sources_with_pending_reflect={"source-a"},
        )
        tips = detect_phase_tips(state)
        tip_ids = [t.tip_id for t in tips]
        # batch_reflect_ready requires 2+ sources
        assert "batch_reflect_ready" not in tip_ids
        assert "reduce_before_reflect" not in tip_ids

    def test_no_tips_all_complete(self):
        """All tasks fully processed -> no tips."""
        state = QueuePhaseState(
            total_tasks=4,
            sources={"source-a", "source-b"},
            phase_counts={},
            sources_with_pending_create=set(),
            sources_with_pending_reflect=set(),
        )
        tips = detect_phase_tips(state)
        assert tips == []


# ---------------------------------------------------------------------------
# TestPhaseTipsIntegration
# ---------------------------------------------------------------------------


class TestPhaseTipsIntegration:
    def _make_vault_with_queue(self, tmp_path, create_pending=True, reflect_pending=True):
        """Build a vault with goals and queue task files at mixed phases."""
        # Goals (for goal_frontier channel)
        goals_dir = tmp_path / "_research" / "goals"
        goals_dir.mkdir(parents=True)
        (goals_dir / "test-goal.md").write_text(_MINIMAL_GOAL)

        ops = tmp_path / "ops"
        ops.mkdir(exist_ok=True)
        (ops / "daemon-config.yaml").write_text("goals_priority:\n  - test-goal\n")

        queue_dir = ops / "queue"
        queue_dir.mkdir(exist_ok=True)

        if create_pending:
            (queue_dir / "src-a-001.md").write_text(
                _make_task_file(
                    source_task="source-a",
                    reduce_filled=True,
                    create_filled=False,
                )
            )

        if reflect_pending:
            (queue_dir / "src-b-001.md").write_text(
                _make_task_file(
                    source_task="source-b",
                    reduce_filled=True,
                    create_filled=True,
                    reflect_filled=False,
                )
            )
            (queue_dir / "src-c-001.md").write_text(
                _make_task_file(
                    source_task="source-c",
                    reduce_filled=True,
                    create_filled=True,
                    reflect_filled=False,
                )
            )

        return tmp_path

    def test_phase_tips_in_advise(self, tmp_path):
        vault = self._make_vault_with_queue(tmp_path)
        suggestions, cached = advise(
            vault,
            context="ralph",
            no_cache=True,
            include_phase_tips=True,
        )
        channels = [s.channel for s in suggestions]
        assert "phase_tip" in channels

    def test_phase_tip_priority(self, tmp_path):
        """Phase tips sort before goal suggestions (priority 0 < goal rank*10)."""
        vault = self._make_vault_with_queue(tmp_path)
        suggestions, _ = advise(
            vault,
            context="ralph",
            no_cache=True,
            include_phase_tips=True,
            max_suggestions=10,
        )
        phase = [s for s in suggestions if s.channel == "phase_tip"]
        goal = [s for s in suggestions if s.channel == "goal_frontier"]
        if phase and goal:
            assert max(s.priority for s in phase) <= min(
                s.priority for s in goal
            )

    def test_no_phase_tips_without_flag(self, tmp_path):
        vault = self._make_vault_with_queue(tmp_path)
        suggestions, _ = advise(
            vault,
            context="literature",
            no_cache=True,
            include_phase_tips=False,
        )
        channels = [s.channel for s in suggestions]
        assert "phase_tip" not in channels

    def test_cli_ralph_context(self, tmp_path, capsys):
        """--context ralph auto-enables phase tips."""
        vault = self._make_vault_with_queue(tmp_path)
        exit_code = main([str(vault), "--context", "ralph", "--no-cache"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        channels = [s["channel"] for s in data["suggestions"]]
        assert "phase_tip" in channels

    def test_cli_explicit_phase_tips_flag(self, tmp_path, capsys):
        """--include-phase-tips flag works with any context."""
        vault = self._make_vault_with_queue(tmp_path)
        main([
            str(vault),
            "--context", "literature",
            "--include-phase-tips",
            "--no-cache",
        ])
        data = json.loads(capsys.readouterr().out)
        channels = [s["channel"] for s in data["suggestions"]]
        assert "phase_tip" in channels


# ---------------------------------------------------------------------------
# Scope field tests
# ---------------------------------------------------------------------------


class TestScanExtractScopes:
    """Tests for scan_extract_scopes()."""

    def test_empty_queue(self, tmp_path: Path):
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)
        assert scan_extract_scopes(tmp_path) == {}

    def test_no_dir(self, tmp_path: Path):
        assert scan_extract_scopes(tmp_path) == {}

    def test_extract_with_scope(self, tmp_path: Path):
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)
        (queue_dir / "paper-a.md").write_text(textwrap.dedent("""\
            ---
            id: "paper-a"
            type: extract
            scope: "methods_only"
            ---
            # Extract claims
        """))
        result = scan_extract_scopes(tmp_path)
        assert result == {"paper-a": "methods_only"}

    def test_default_scope(self, tmp_path: Path):
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)
        (queue_dir / "paper-b.md").write_text(textwrap.dedent("""\
            ---
            id: "paper-b"
            type: extract
            ---
            # Extract claims
        """))
        result = scan_extract_scopes(tmp_path)
        assert result == {"paper-b": "full"}

    def test_ignores_non_extract(self, tmp_path: Path):
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)
        (queue_dir / "claim-001.md").write_text(textwrap.dedent("""\
            ---
            id: "claim-001"
            type: claim
            source_task: "paper-a"
            ---
            # Claim
        """))
        result = scan_extract_scopes(tmp_path)
        assert result == {}

    def test_invalid_scope(self, tmp_path: Path):
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)
        (queue_dir / "paper-c.md").write_text(textwrap.dedent("""\
            ---
            id: "paper-c"
            type: extract
            scope: "bogus_value"
            ---
            # Extract
        """))
        result = scan_extract_scopes(tmp_path)
        assert result == {}

    def test_id_fallback_to_stem(self, tmp_path: Path):
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)
        (queue_dir / "paper-d.md").write_text(textwrap.dedent("""\
            ---
            type: extract
            scope: "full"
            ---
            # Extract
        """))
        result = scan_extract_scopes(tmp_path)
        assert result == {"paper-d": "full"}


class TestSuggestionScope:
    """Tests for scope field on Suggestion dataclass."""

    def test_default_scope(self):
        s = Suggestion(
            channel="test", query="q", rationale="r",
            priority=1, goal_ref="g",
        )
        assert s.scope == "full"

    def test_explicit_scope(self):
        s = Suggestion(
            channel="test", query="q", rationale="r",
            priority=1, goal_ref="g", scope="methods_only",
        )
        assert s.scope == "methods_only"

    def test_cache_roundtrip_with_scope(self, tmp_path: Path):
        cache_path = tmp_path / "cache.json"
        suggestions = [
            Suggestion(
                channel="c", query="q", rationale="r",
                priority=1, goal_ref="g", scope="methods_only",
            ),
        ]
        save_cache(cache_path, suggestions, "key", "reduce", 5)
        data = json.loads(cache_path.read_text())
        assert data["suggestions"][0]["scope"] == "methods_only"

    def test_backward_compat_old_cache_without_scope(self, tmp_path: Path):
        """Old cache files without scope should still load; scope defaults."""
        cache_path = tmp_path / "cache.json"
        data = {
            "session_key": "k",
            "context": "reduce",
            "max_suggestions": 5,
            "suggestions": [
                {
                    "channel": "c",
                    "query": "q",
                    "rationale": "r",
                    "priority": 1,
                    "goal_ref": "g",
                },
            ],
        }
        cache_path.write_text(json.dumps(data))
        loaded = load_cache(cache_path)
        assert loaded is not None
        # Old caches lack scope key -- callers must handle default
        assert "scope" not in loaded["suggestions"][0]


# ---------------------------------------------------------------------------
# Session Tip Channel
# ---------------------------------------------------------------------------


class TestBuildVaultSnapshot:
    def test_correct_counts(self, tmp_path: Path):
        """Counts .md files in the right directories."""
        (tmp_path / "notes").mkdir()
        (tmp_path / "notes" / "a.md").write_text("x")
        (tmp_path / "notes" / "b.md").write_text("x")
        (tmp_path / "notes" / ".hidden.md").write_text("x")
        (tmp_path / "inbox").mkdir()
        (tmp_path / "inbox" / "item.md").write_text("x")
        (tmp_path / "ops" / "observations").mkdir(parents=True)
        (tmp_path / "ops" / "tensions").mkdir(parents=True)
        (tmp_path / "ops" / "queue").mkdir(parents=True)
        (tmp_path / "_research" / "hypotheses").mkdir(parents=True)

        snap = build_vault_snapshot(tmp_path)
        assert snap.claim_count == 2
        assert snap.inbox_count == 1
        assert snap.observation_count == 0
        assert snap.tension_count == 0
        assert snap.queue_pending == 0
        assert snap.hypothesis_count == 0

    def test_missing_dirs(self, tmp_path: Path):
        """Missing directories produce zero counts, no error."""
        snap = build_vault_snapshot(tmp_path)
        assert snap.claim_count == 0
        assert snap.inbox_count == 0
        assert snap.has_recent_reduce is False

    def test_recent_reduce_detected(self, tmp_path: Path):
        """A recently-modified queue file sets has_recent_reduce."""
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)
        (queue_dir / "task.md").write_text("x")
        # File just created -> mtime is within 24h
        snap = build_vault_snapshot(tmp_path)
        assert snap.has_recent_reduce is True

    def test_abstract_only_source_count(self, tmp_path: Path):
        """Counts abstract-only sources in inbox/."""
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        # Abstract-only (should count)
        (inbox / "abstract.md").write_text(
            '---\nsource_type: "import"\n'
            'source_url: "https://doi.org/10.1234/test"\n'
            'content_depth: "abstract"\n---\n\n# Title\n'
        )
        # Raw stub without content_depth (should NOT count)
        (inbox / "stub.md").write_text(
            '---\nsource_type: "import"\n'
            'source_url: "https://doi.org/10.1234/test"\n---\n\n# Title\n'
        )
        # Full text (should NOT count)
        (inbox / "full.md").write_text(
            '---\nsource_type: "import"\n'
            'content_depth: "full_text"\n---\n\n# Title\n'
        )
        snap = build_vault_snapshot(tmp_path)
        assert snap.abstract_only_source_count == 1

    def test_abstract_only_source_count_empty_inbox(self, tmp_path: Path):
        """Empty inbox gives zero abstract_only_source_count."""
        (tmp_path / "inbox").mkdir()
        snap = build_vault_snapshot(tmp_path)
        assert snap.abstract_only_source_count == 0

    def test_raw_stubs_not_counted_as_abstract_only(self, tmp_path: Path):
        """Stubs with no content_depth field do not count as abstract_only."""
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        (inbox / "stub.md").write_text(
            '---\nsource_type: "import"\n'
            'source_url: "https://doi.org/10.1234/test"\n---\n\n# Title\n'
        )
        snap = build_vault_snapshot(tmp_path)
        assert snap.abstract_only_source_count == 0


class TestDetectSessionTips:
    def test_reduce_inbox_fires(self):
        snap = VaultSnapshot(inbox_count=5, has_recent_reduce=False)
        tips = detect_session_tips(snap)
        assert any(t.tip_id == "reduce_inbox" for t in tips)

    def test_reduce_inbox_suppressed_by_recent_reduce(self):
        snap = VaultSnapshot(inbox_count=5, has_recent_reduce=True)
        tips = detect_session_tips(snap)
        assert not any(t.tip_id == "reduce_inbox" for t in tips)

    def test_unblock_queue_fires(self):
        snap = VaultSnapshot(queue_pending=3)
        tips = detect_session_tips(snap)
        assert any(t.tip_id == "unblock_queue" for t in tips)

    def test_generate_hypotheses_fires(self):
        snap = VaultSnapshot(claim_count=25, hypothesis_count=0)
        tips = detect_session_tips(snap)
        assert any(t.tip_id == "generate_hypotheses" for t in tips)

    def test_generate_hypotheses_not_when_hypotheses_exist(self):
        snap = VaultSnapshot(claim_count=25, hypothesis_count=3)
        tips = detect_session_tips(snap)
        assert not any(t.tip_id == "generate_hypotheses" for t in tips)

    def test_rethink_observations_fires(self):
        snap = VaultSnapshot(observation_count=12)
        tips = detect_session_tips(snap)
        assert any(t.tip_id == "rethink_observations" for t in tips)

    def test_rethink_tensions_fires(self):
        snap = VaultSnapshot(tension_count=6)
        tips = detect_session_tips(snap)
        assert any(t.tip_id == "rethink_tensions" for t in tips)

    def test_full_text_upgrade_fires(self):
        snap = VaultSnapshot(abstract_only_source_count=3)
        tips = detect_session_tips(snap)
        assert any(t.tip_id == "full_text_upgrade" for t in tips)

    def test_full_text_upgrade_zero_does_not_fire(self):
        snap = VaultSnapshot(abstract_only_source_count=0)
        tips = detect_session_tips(snap)
        assert not any(t.tip_id == "full_text_upgrade" for t in tips)

    def test_full_text_upgrade_message_format(self):
        snap = VaultSnapshot(abstract_only_source_count=5)
        tips = detect_session_tips(snap)
        upgrade_tips = [t for t in tips if t.tip_id == "full_text_upgrade"]
        assert len(upgrade_tips) == 1
        assert "5" in upgrade_tips[0].message
        assert "abstract-only" in upgrade_tips[0].message
        assert upgrade_tips[0].priority == 2

    def test_full_text_upgrade_priority_lower_than_reduce(self):
        snap = VaultSnapshot(
            abstract_only_source_count=3, inbox_count=5,
            has_recent_reduce=False,
        )
        tips = detect_session_tips(snap)
        upgrade = [t for t in tips if t.tip_id == "full_text_upgrade"]
        reduce = [t for t in tips if t.tip_id == "reduce_inbox"]
        assert upgrade and reduce
        assert upgrade[0].priority > reduce[0].priority

    def test_enrich_stubs_tip_no_longer_exists(self):
        snap = VaultSnapshot(abstract_only_source_count=3)
        tips = detect_session_tips(snap)
        assert not any(t.tip_id == "enrich_stubs" for t in tips)

    def test_abstract_only_source_count_in_snapshot(self):
        snap = VaultSnapshot()
        assert snap.abstract_only_source_count == 0

    def test_no_tips_on_healthy_vault(self):
        snap = VaultSnapshot(
            claim_count=30, hypothesis_count=5, inbox_count=0,
            queue_pending=0, observation_count=2, tension_count=1,
        )
        tips = detect_session_tips(snap)
        assert tips == []

    def test_sorted_by_priority(self):
        snap = VaultSnapshot(
            inbox_count=5, has_recent_reduce=False,
            observation_count=15, tension_count=7,
        )
        tips = detect_session_tips(snap)
        priorities = [t.priority for t in tips]
        assert priorities == sorted(priorities)

    def test_queue_blocked_count_in_snapshot(self):
        snap = VaultSnapshot()
        assert snap.queue_blocked_count == 0

    def test_queue_blocked_fires(self):
        snap = VaultSnapshot(queue_blocked_count=3)
        tips = detect_session_tips(snap)
        assert any(t.tip_id == "queue_blocked" for t in tips)

    def test_queue_blocked_zero_does_not_fire(self):
        snap = VaultSnapshot(queue_blocked_count=0)
        tips = detect_session_tips(snap)
        assert not any(t.tip_id == "queue_blocked" for t in tips)

    def test_queue_blocked_message_format(self):
        snap = VaultSnapshot(queue_blocked_count=5)
        tips = detect_session_tips(snap)
        blocked_tips = [t for t in tips if t.tip_id == "queue_blocked"]
        assert len(blocked_tips) == 1
        assert blocked_tips[0].message.startswith("/literature")
        assert "5" in blocked_tips[0].message

    def test_all_tip_messages_are_well_formed(self):
        snap = VaultSnapshot(
            inbox_count=3, has_recent_reduce=False,
            queue_pending=5, queue_blocked_count=2,
            claim_count=25, hypothesis_count=0,
            observation_count=15, tension_count=7,
            abstract_only_source_count=2,
            high_demand_abstract_sources=[("paper-x", 4)],
        )
        tips = detect_session_tips(snap)
        assert len(tips) > 0
        for tip in tips:
            # Every tip message must be non-empty and contain content
            assert len(tip.message) > 10, (
                f"Tip '{tip.tip_id}' message too short: {tip.message}"
            )
            assert tip.rationale, (
                f"Tip '{tip.tip_id}' missing rationale"
            )


class TestSessionTipsIntegration:
    def _make_vault_with_inbox(self, tmp_path: Path) -> Path:
        """Build a vault with inbox items and goals (for multi-channel test)."""
        goals_dir = tmp_path / "_research" / "goals"
        goals_dir.mkdir(parents=True)
        (goals_dir / "test-goal.md").write_text(_MINIMAL_GOAL)

        ops = tmp_path / "ops"
        ops.mkdir(exist_ok=True)
        (ops / "daemon-config.yaml").write_text("goals_priority:\n  - test-goal\n")

        (tmp_path / "inbox").mkdir(exist_ok=True)
        (tmp_path / "inbox" / "paper.md").write_text("x")
        (tmp_path / "notes").mkdir(exist_ok=True)
        (tmp_path / "ops" / "observations").mkdir(exist_ok=True)
        (tmp_path / "ops" / "tensions").mkdir(exist_ok=True)
        (tmp_path / "_research" / "hypotheses").mkdir(exist_ok=True)
        return tmp_path

    def test_session_tips_in_advise(self, tmp_path: Path):
        vault = self._make_vault_with_inbox(tmp_path)
        suggestions, _ = advise(
            vault, context="literature", no_cache=True,
            include_session_tips=True,
        )
        channels = [s.channel for s in suggestions]
        assert "session_tip" in channels

    def test_no_session_tips_without_flag(self, tmp_path: Path):
        vault = self._make_vault_with_inbox(tmp_path)
        suggestions, _ = advise(
            vault, context="literature", no_cache=True,
            include_session_tips=False,
        )
        channels = [s.channel for s in suggestions]
        assert "session_tip" not in channels

    def test_cli_include_session_tips(self, tmp_path: Path, capsys):
        vault = self._make_vault_with_inbox(tmp_path)
        main([
            str(vault), "--context", "literature",
            "--include-session-tips", "--no-cache",
        ])
        data = json.loads(capsys.readouterr().out)
        channels = [s["channel"] for s in data["suggestions"]]
        assert "session_tip" in channels

    def test_cli_all_tips(self, tmp_path: Path, capsys):
        vault = self._make_vault_with_inbox(tmp_path)
        exit_code = main([str(vault), "--all-tips", "--no-cache"])
        data = json.loads(capsys.readouterr().out)
        assert "all_session_tips" in data
        assert len(data["all_session_tips"]) >= 1
        assert exit_code == 0

    def test_cli_all_tips_empty(self, tmp_path: Path, capsys):
        """--all-tips on a healthy vault returns exit 2."""
        # Minimal vault with no inbox, no queue, etc.
        (tmp_path / "notes").mkdir()
        (tmp_path / "inbox").mkdir()
        (tmp_path / "ops" / "observations").mkdir(parents=True)
        (tmp_path / "ops" / "tensions").mkdir(parents=True)
        (tmp_path / "ops" / "queue").mkdir(parents=True)
        (tmp_path / "_research" / "hypotheses").mkdir(parents=True)

        exit_code = main([str(tmp_path), "--all-tips"])
        data = json.loads(capsys.readouterr().out)
        assert data["all_session_tips"] == []
        assert exit_code == 2


# ---------------------------------------------------------------------------
# High-demand abstract source detection
# ---------------------------------------------------------------------------


def _make_lit_note(path: Path, stem: str, content_depth: str = "abstract"):
    """Helper: create a literature note with given content_depth."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{stem}"\n'
        f'content_depth: "{content_depth}"\n---\n\n# {stem}\n'
    )


def _make_claim(path: Path, source_stem: str):
    """Helper: create a claim note citing source_stem via wiki-link."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ndescription: "test claim"\n'
        f'source: "[[{source_stem}]]"\n---\n\nContent.\n'
    )


class TestHighDemandAbstractSources:
    def test_no_lit_dir(self, tmp_path: Path):
        """Returns empty when _research/literature/ does not exist."""
        result = _find_high_demand_abstract_sources(tmp_path)
        assert result == []

    def test_no_abstract_sources(self, tmp_path: Path):
        """Returns empty when no abstract-only literature notes exist."""
        lit_dir = tmp_path / "_research" / "literature"
        lit_dir.mkdir(parents=True)
        _make_lit_note(lit_dir / "paper-a.md", "paper-a", "full_text")
        (tmp_path / "notes").mkdir()
        result = _find_high_demand_abstract_sources(tmp_path)
        assert result == []

    def test_below_threshold(self, tmp_path: Path):
        """Source with fewer than 3 citations is excluded."""
        lit_dir = tmp_path / "_research" / "literature"
        _make_lit_note(lit_dir / "paper-a.md", "paper-a")
        notes_dir = tmp_path / "notes"
        _make_claim(notes_dir / "c1.md", "paper-a")
        _make_claim(notes_dir / "c2.md", "paper-a")
        result = _find_high_demand_abstract_sources(tmp_path)
        assert result == []

    def test_at_threshold(self, tmp_path: Path):
        """Source with exactly 3 citations is included."""
        lit_dir = tmp_path / "_research" / "literature"
        _make_lit_note(lit_dir / "paper-a.md", "paper-a")
        notes_dir = tmp_path / "notes"
        for i in range(3):
            _make_claim(notes_dir / f"c{i}.md", "paper-a")
        result = _find_high_demand_abstract_sources(tmp_path)
        assert result == [("paper-a", 3)]

    def test_multiple_sources_sorted(self, tmp_path: Path):
        """Multiple sources are sorted by cite count descending."""
        lit_dir = tmp_path / "_research" / "literature"
        _make_lit_note(lit_dir / "paper-a.md", "paper-a")
        _make_lit_note(lit_dir / "paper-b.md", "paper-b")
        notes_dir = tmp_path / "notes"
        # paper-a: 3 cites
        for i in range(3):
            _make_claim(notes_dir / f"a{i}.md", "paper-a")
        # paper-b: 5 cites
        for i in range(5):
            _make_claim(notes_dir / f"b{i}.md", "paper-b")
        result = _find_high_demand_abstract_sources(tmp_path)
        assert len(result) == 2
        assert result[0] == ("paper-b", 5)
        assert result[1] == ("paper-a", 3)

    def test_full_text_excluded(self, tmp_path: Path):
        """Full-text sources are not counted even if heavily cited."""
        lit_dir = tmp_path / "_research" / "literature"
        _make_lit_note(lit_dir / "paper-a.md", "paper-a", "full_text")
        notes_dir = tmp_path / "notes"
        for i in range(5):
            _make_claim(notes_dir / f"c{i}.md", "paper-a")
        result = _find_high_demand_abstract_sources(tmp_path)
        assert result == []

    def test_index_file_skipped(self, tmp_path: Path):
        """Files starting with _ (like _index.md) are skipped."""
        lit_dir = tmp_path / "_research" / "literature"
        lit_dir.mkdir(parents=True)
        (lit_dir / "_index.md").write_text(
            '---\ncontent_depth: "abstract"\n---\n'
        )
        (tmp_path / "notes").mkdir()
        result = _find_high_demand_abstract_sources(tmp_path)
        assert result == []

    def test_no_notes_dir(self, tmp_path: Path):
        """Returns empty when notes/ does not exist."""
        lit_dir = tmp_path / "_research" / "literature"
        _make_lit_note(lit_dir / "paper-a.md", "paper-a")
        result = _find_high_demand_abstract_sources(tmp_path)
        assert result == []


class TestHighDemandSessionTips:
    """Tests for full_text_upgrade_demand and abstract_accumulation_warning."""

    def test_demand_tip_fires(self):
        snap = VaultSnapshot(
            high_demand_abstract_sources=[("paper-a", 5), ("paper-b", 3)]
        )
        tips = detect_session_tips(snap)
        assert any(t.tip_id == "full_text_upgrade_demand" for t in tips)

    def test_demand_tip_does_not_fire_empty(self):
        snap = VaultSnapshot(high_demand_abstract_sources=[])
        tips = detect_session_tips(snap)
        assert not any(t.tip_id == "full_text_upgrade_demand" for t in tips)

    def test_demand_tip_priority_higher_than_generic(self):
        """Demand tip (priority 1) beats generic upgrade tip (priority 2)."""
        snap = VaultSnapshot(
            abstract_only_source_count=3,
            high_demand_abstract_sources=[("paper-a", 4)],
        )
        tips = detect_session_tips(snap)
        demand = [t for t in tips if t.tip_id == "full_text_upgrade_demand"]
        generic = [t for t in tips if t.tip_id == "full_text_upgrade"]
        assert demand and generic
        assert demand[0].priority < generic[0].priority

    def test_demand_tip_message_includes_source_names(self):
        snap = VaultSnapshot(
            high_demand_abstract_sources=[("paper-a", 5), ("paper-b", 3)]
        )
        tips = detect_session_tips(snap)
        demand = [t for t in tips if t.tip_id == "full_text_upgrade_demand"]
        assert len(demand) == 1
        assert "[[paper-a]]" in demand[0].message
        assert "[[paper-b]]" in demand[0].message
        assert "5 claims" in demand[0].message

    def test_demand_tip_top3_only(self):
        """Only top 3 sources appear in message even if more qualify."""
        sources = [
            ("p1", 10), ("p2", 8), ("p3", 6), ("p4", 4),
        ]
        snap = VaultSnapshot(high_demand_abstract_sources=sources)
        tips = detect_session_tips(snap)
        demand = [t for t in tips if t.tip_id == "full_text_upgrade_demand"]
        assert "[[p4]]" not in demand[0].message

    def test_accumulation_warning_fires(self):
        snap = VaultSnapshot(
            abstract_only_source_count=5, has_recent_reduce=False,
        )
        tips = detect_session_tips(snap)
        assert any(
            t.tip_id == "abstract_accumulation_warning" for t in tips
        )

    def test_accumulation_warning_suppressed_by_recent_reduce(self):
        snap = VaultSnapshot(
            abstract_only_source_count=7, has_recent_reduce=True,
        )
        tips = detect_session_tips(snap)
        assert not any(
            t.tip_id == "abstract_accumulation_warning" for t in tips
        )

    def test_accumulation_warning_below_threshold(self):
        snap = VaultSnapshot(
            abstract_only_source_count=4, has_recent_reduce=False,
        )
        tips = detect_session_tips(snap)
        assert not any(
            t.tip_id == "abstract_accumulation_warning" for t in tips
        )

    def test_accumulation_warning_message_format(self):
        snap = VaultSnapshot(
            abstract_only_source_count=8, has_recent_reduce=False,
        )
        tips = detect_session_tips(snap)
        warn = [
            t for t in tips
            if t.tip_id == "abstract_accumulation_warning"
        ]
        assert len(warn) == 1
        assert "8" in warn[0].message
        assert warn[0].priority == 1


class TestHighDemandSnapshotIntegration:
    """Integration: build_vault_snapshot populates high_demand_abstract_sources."""

    def test_snapshot_includes_high_demand(self, tmp_path: Path):
        lit_dir = tmp_path / "_research" / "literature"
        _make_lit_note(lit_dir / "paper-a.md", "paper-a")
        notes_dir = tmp_path / "notes"
        for i in range(4):
            _make_claim(notes_dir / f"c{i}.md", "paper-a")
        # Create minimal dirs to avoid errors
        (tmp_path / "inbox").mkdir(exist_ok=True)
        (tmp_path / "ops" / "observations").mkdir(parents=True)
        (tmp_path / "ops" / "tensions").mkdir(parents=True)
        (tmp_path / "ops" / "queue").mkdir(parents=True)
        (tmp_path / "_research" / "hypotheses").mkdir(parents=True)

        snap = build_vault_snapshot(tmp_path)
        assert len(snap.high_demand_abstract_sources) == 1
        assert snap.high_demand_abstract_sources[0] == ("paper-a", 4)

    def test_snapshot_empty_when_no_high_demand(self, tmp_path: Path):
        (tmp_path / "notes").mkdir()
        (tmp_path / "inbox").mkdir()
        (tmp_path / "ops" / "observations").mkdir(parents=True)
        (tmp_path / "ops" / "tensions").mkdir(parents=True)
        (tmp_path / "ops" / "queue").mkdir(parents=True)
        (tmp_path / "_research" / "hypotheses").mkdir(parents=True)

        snap = build_vault_snapshot(tmp_path)
        assert snap.high_demand_abstract_sources == []
