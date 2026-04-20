"""Helpers for creating writable temporary directories during tests."""

from pathlib import Path
import uuid


TEST_TEMP_ROOT = Path(__file__).resolve().parent.parent / 'build' / 'test-temp'


def make_tempdir() -> Path:
    """Create a temporary directory inside the repository workspace."""
    TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    tempdir = TEST_TEMP_ROOT / f'tmp-{uuid.uuid4().hex}'
    tempdir.mkdir(parents=True, exist_ok=False)
    return tempdir
