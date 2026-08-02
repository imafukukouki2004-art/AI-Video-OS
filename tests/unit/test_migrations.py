"""Alembic migration chain tests."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_single_postgresql_foundation_head() -> None:
    root = Path(__file__).resolve().parents[2]
    config = Config(root / "alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["20260802_0001"]
    assert script.get_base() == "20260802_0001"
