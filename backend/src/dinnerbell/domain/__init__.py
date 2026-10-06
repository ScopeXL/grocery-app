"""Pure quantity math (PLAN §8, ADR 0007): standard library only, no I/O, no clock.

Quantities are ``fractions.Fraction`` and money is integer cents; floats are refused. ``now`` is
always passed in and timezone-aware. ``tests/test_purity.py`` enforces this.
"""
