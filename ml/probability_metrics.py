"""Metrics for a validated, frozen ordered-trifecta probability table."""
import math


def score(table: dict[str, float], outcome: str) -> dict:
    ordered = sorted(table, key=lambda key: (-table[key], key))
    rank = ordered.index(outcome) + 1
    return {
        'rank': rank,
        'reciprocal_rank': 1 / rank,
        'log_loss': -math.log(max(table[outcome], 1e-15)),
        'brier_sum': sum((probability - int(key == outcome)) ** 2 for key, probability in table.items()),
        **{f'top{k}': int(rank <= k) for k in (1, 3, 5, 10)},
    }
