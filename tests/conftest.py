"""Suite-wide pytest configuration."""

import pytest

from gleplot.compiler import find_gle


def pytest_collection_modifyitems(config, items):
    """Skip every ``@pytest.mark.gle`` test when the GLE binary is missing.

    The marker is the single way to say "this test shells out to GLE": it
    labels the test and, here, keeps a machine without GLE green. Tests must
    not carry their own availability check.
    """
    if find_gle() is not None:
        return
    skip = pytest.mark.skip(reason="GLE binary not available")
    for item in items:
        if "gle" in item.keywords:
            item.add_marker(skip)
