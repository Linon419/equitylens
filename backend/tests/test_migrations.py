from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migrations_have_one_expected_head() -> None:
    root = Path(__file__).resolve().parents[1]
    config = Config(root / "alembic.ini")
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == ["20260714_0005"]
