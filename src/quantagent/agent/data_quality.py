"""Pure data-quality checks. Deliberately dependency-free (no DB/exchange/ml
imports) so they're trivial to unit test in isolation, and so a future check
can be added here without dragging in heavier modules. These produce
WARNINGS, not halts -- the decision to actually stop trading stays entirely
in risk/rules.py, which doesn't know or care about data quality, only about
money. Keeping that boundary means a data-quality bug can never accidentally
suppress a real risk halt, or vice versa."""


def check_universe_coverage(universe: list[str], scored_symbols: list[str],
                            min_coverage: float = 0.5) -> list[str]:
    """Flags symbols that were in today's universe but never got a usable,
    complete feature row -- and flags it loudly if that's most of the
    universe, since that usually means an exchange/feed problem rather than
    a few quiet symbols."""
    warnings = []
    missing = sorted(set(universe) - set(scored_symbols))
    if missing:
        warnings.append(
            f"{len(missing)}/{len(universe)} universe symbol(s) had no usable "
            f"feature row today and were skipped: {', '.join(missing)}"
        )
    coverage = len(scored_symbols) / len(universe) if universe else 0
    if universe and coverage < min_coverage:
        warnings.append(
            f"Only {coverage:.0%} of the universe was scorable today -- "
            f"this is unusually low and worth checking the exchange/feed."
        )
    return warnings
