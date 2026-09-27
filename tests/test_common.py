import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from common import weighted_length  # noqa: E402


def test_ascii_counts_as_one():
    assert weighted_length("hello") == 5


def test_japanese_counts_as_two():
    assert weighted_length("こんにちは") == 10


def test_mixed_with_newline():
    assert weighted_length("AI活用\n3選") == 2 + 4 + 1 + 1 + 2
