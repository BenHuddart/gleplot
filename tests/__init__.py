"""gleplot test suite.

``unit/`` asserts on the object model and emitted script text, ``parser/`` on
parsing, recovery and the writer/parser fixed point, and ``integration/`` on
what GLE actually renders. Tests that shell out to GLE carry
``@pytest.mark.gle`` and are skipped when the binary is missing (see
``conftest.py``).
"""
