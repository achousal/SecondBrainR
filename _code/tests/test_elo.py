"""Tests for Elo rating calculations."""

from engram_r.elo import (
    EloResult,
    apply_empirical_elo,
    compute_elo,
    expected_score,
    generate_matchups,
)


class TestExpectedScore:
    def test_equal_elo(self):
        assert expected_score(1200, 1200) == 0.5

    def test_higher_elo_favored(self):
        assert expected_score(1400, 1200) > 0.5

    def test_lower_elo_disadvantaged(self):
        assert expected_score(1000, 1200) < 0.5

    def test_symmetry(self):
        s_a = expected_score(1300, 1100)
        s_b = expected_score(1100, 1300)
        assert abs(s_a + s_b - 1.0) < 1e-10

    def test_large_gap(self):
        # 400-point gap -> ~91% expected
        score = expected_score(1600, 1200)
        assert 0.90 < score < 0.92


class TestComputeElo:
    def test_returns_elo_result(self):
        result = compute_elo(1200, 1200)
        assert isinstance(result, EloResult)

    def test_equal_elo_match(self):
        result = compute_elo(1200, 1200, k=32)
        assert result.winner_delta == 16.0
        assert result.loser_delta == -16.0
        assert result.winner_new == 1216.0
        assert result.loser_new == 1184.0

    def test_rating_sum_preserved(self):
        result = compute_elo(1400, 1100, k=32)
        total_before = 1400 + 1100
        total_after = result.winner_new + result.loser_new
        assert abs(total_before - total_after) < 1e-10

    def test_upset_larger_delta(self):
        # Underdog wins -> bigger swing
        upset = compute_elo(1000, 1400, k=32)
        expected_win = compute_elo(1400, 1000, k=32)
        assert upset.winner_delta > expected_win.winner_delta

    def test_custom_k_factor(self):
        result_k16 = compute_elo(1200, 1200, k=16)
        result_k32 = compute_elo(1200, 1200, k=32)
        assert result_k16.winner_delta == 8.0
        assert result_k32.winner_delta == 16.0


class TestGenerateMatchups:
    def _make_hyps(self, n, elo=1200, matches=0):
        return [
            {"id": f"hyp-{i:03d}", "elo": elo, "matches": matches}
            for i in range(n)
        ]

    def test_empty_list(self):
        assert generate_matchups([], 5) == []

    def test_single_hypothesis(self):
        assert generate_matchups(self._make_hyps(1), 5) == []

    def test_returns_requested_count(self):
        hyps = self._make_hyps(10)
        matchups = generate_matchups(hyps, 5, seed=42)
        assert len(matchups) == 5

    def test_no_self_matches(self):
        hyps = self._make_hyps(5)
        matchups = generate_matchups(hyps, 10, seed=42)
        for a, b in matchups:
            assert a != b

    def test_no_duplicate_pairs(self):
        hyps = self._make_hyps(6)
        matchups = generate_matchups(hyps, 15, seed=42)
        pairs = [tuple(sorted(p)) for p in matchups]
        assert len(pairs) == len(set(pairs))

    def test_max_possible_matches(self):
        hyps = self._make_hyps(4)
        # Max unique pairs for 4 items = 6
        matchups = generate_matchups(hyps, 100, seed=42)
        assert len(matchups) <= 6

    def test_deterministic_with_seed(self):
        hyps = self._make_hyps(8)
        m1 = generate_matchups(hyps, 5, seed=123)
        m2 = generate_matchups(hyps, 5, seed=123)
        assert m1 == m2

    def test_prioritizes_under_matched(self):
        hyps = [
            {"id": "new-1", "elo": 1200, "matches": 0},
            {"id": "new-2", "elo": 1200, "matches": 0},
            {"id": "old-1", "elo": 1200, "matches": 10},
            {"id": "old-2", "elo": 1200, "matches": 10},
        ]
        matchups = generate_matchups(hyps, 2, seed=42)
        # At least one match should involve an under-matched hypothesis
        all_ids = {h for pair in matchups for h in pair}
        assert "new-1" in all_ids or "new-2" in all_ids


class TestApplyEmpiricalElo:
    def test_win_raises_elo(self):
        new_elo, delta = apply_empirical_elo(1200.0, won=True, k=16.0)
        assert delta > 0
        assert new_elo > 1200.0

    def test_loss_lowers_elo(self):
        new_elo, delta = apply_empirical_elo(1200.0, won=False, k=16.0)
        assert delta < 0
        assert new_elo < 1200.0

    def test_equal_elo_win_delta_is_half_k(self):
        # At equal Elo, expected = 0.5, so delta = k * (1.0 - 0.5) = k/2
        _, delta = apply_empirical_elo(1200.0, won=True, k=16.0, opponent_elo=1200.0)
        assert abs(delta - 8.0) < 1e-10

    def test_high_elo_loss_larger_swing(self):
        # High-rated hypothesis losing to reality -> larger penalty
        _, delta_high = apply_empirical_elo(1400.0, won=False, k=16.0)
        _, delta_equal = apply_empirical_elo(1200.0, won=False, k=16.0)
        assert abs(delta_high) > abs(delta_equal)
