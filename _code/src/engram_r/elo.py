"""Elo rating calculations for hypothesis tournament ranking.

Pure math module -- no I/O, no side effects.
Reference: standard Elo system with K-factor control.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class EloResult:
    """Result of an Elo rating update."""

    winner_new: float
    loser_new: float
    winner_delta: float
    loser_delta: float


def expected_score(elo_a: float, elo_b: float) -> float:
    """Compute expected score for player A against player B.

    Returns probability in [0, 1] that A wins.
    """
    return 1.0 / (1.0 + math.pow(10, (elo_b - elo_a) / 400.0))


def compute_elo(winner_elo: float, loser_elo: float, k: float = 32.0) -> EloResult:
    """Compute new Elo ratings after a match.

    Args:
        winner_elo: Current Elo of the winner.
        loser_elo: Current Elo of the loser.
        k: K-factor controlling rating volatility.

    Returns:
        EloResult with new ratings and deltas.
    """
    expected_winner = expected_score(winner_elo, loser_elo)
    expected_loser = expected_score(loser_elo, winner_elo)

    delta_winner = k * (1.0 - expected_winner)
    delta_loser = k * (0.0 - expected_loser)

    return EloResult(
        winner_new=winner_elo + delta_winner,
        loser_new=loser_elo + delta_loser,
        winner_delta=delta_winner,
        loser_delta=delta_loser,
    )


def generate_matchups(
    hypotheses: list[dict],
    n_matches: int,
    *,
    seed: int | None = None,
) -> list[tuple[str, str]]:
    """Generate smart pairings for tournament matches.

    Prioritizes:
    1. Hypotheses with fewer matches played (fairness).
    2. Hypotheses with similar Elo ratings (informative matches).

    Args:
        hypotheses: List of dicts with keys 'id', 'elo', 'matches'.
        n_matches: Number of match pairings to generate.
        seed: Random seed for reproducibility.

    Returns:
        List of (id_a, id_b) tuples.
    """
    if len(hypotheses) < 2:
        return []

    rng = random.Random(seed)
    n_matches = min(n_matches, len(hypotheses) * (len(hypotheses) - 1) // 2)

    # Sort by matches played (ascending) to prioritize under-matched
    sorted_hyps = sorted(hypotheses, key=lambda h: h["matches"])

    matchups: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for _ in range(n_matches * 3):  # oversample, then trim
        if len(matchups) >= n_matches:
            break

        # Pick first from under-matched pool (top half of sorted)
        pool_size = max(2, len(sorted_hyps) // 2)
        a = rng.choice(sorted_hyps[:pool_size])

        # Find closest Elo opponent
        candidates = [h for h in sorted_hyps if h["id"] != a["id"]]
        if not candidates:
            continue

        candidates.sort(key=lambda h: abs(h["elo"] - a["elo"]))
        # Pick from top 3 closest with some randomness
        top_k = min(3, len(candidates))
        b = rng.choice(candidates[:top_k])

        pair = tuple(sorted([a["id"], b["id"]]))
        if pair not in seen:
            seen.add(pair)
            matchups.append((a["id"], b["id"]))

    return matchups[:n_matches]


def apply_empirical_elo(
    hypothesis_elo: float,
    won: bool,
    k: float = 16.0,
    opponent_elo: float = 1200.0,
) -> tuple[float, float]:
    """Compute Elo adjustment from an empirical experiment outcome.

    The hypothesis "plays against reality" (a virtual opponent at
    opponent_elo). Sum preservation is intentionally NOT maintained
    because empirical evidence injects external information into the
    rating system.

    Args:
        hypothesis_elo: Current Elo of the hypothesis.
        won: True if the hypothesis was empirically supported (positive),
             False if it was refuted (negative/null).
        k: K-factor for empirical updates (default 16, half of tournament K).
        opponent_elo: Elo of the virtual opponent ("reality").

    Returns:
        (new_elo, delta) tuple.
    """
    expected = expected_score(hypothesis_elo, opponent_elo)
    actual = 1.0 if won else 0.0
    delta = k * (actual - expected)
    return hypothesis_elo + delta, delta
