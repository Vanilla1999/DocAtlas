# Complete pytest marker inventory and test tiers

The complete pytest marker inventory is `integration`, `advanced`, `live`, and `live_network`. The test suite markers are `integration`, `advanced`, `live`, and `live_network`. Core tests without those optional markers remain in the default suite.

Run the fail-closed offline suite with `DOCMANCER_OFFLINE=1 pytest tests/ -m "not advanced and not live and not live_network"`. Use `-m integration` only for the explicitly registered integration quality checks; live network tests additionally require `DOCMANCER_RUN_LIVE_TESTS=1`.
