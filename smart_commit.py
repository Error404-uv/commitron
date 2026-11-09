"""Legacy source-checkout entry point; delegates to the maintained Commitron CLI."""
from pathlib import Path
import sys


# Keep ``python smart_commit.py`` working from a source checkout without
# retaining the old, unsafe implementation that could stage every file.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from commitron.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
