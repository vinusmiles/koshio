import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def test_migrations_build_the_full_schema(tmp_path):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'm.db'}"}
    for cmd in (["upgrade", "head"], ["check"]):
        r = subprocess.run([sys.executable, "-m", "alembic", *cmd], cwd=BACKEND, env=env,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr + r.stdout
