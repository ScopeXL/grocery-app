"""Talking to Kroger's public APIs (docs/PLAN.md §7).

`client.KrogerApi` is the one interface the app uses. `live.LiveKroger` calls the real API;
`fake.FakeKroger` serves synthetic data for development, tests, e2e runs and screenshots.
"""
