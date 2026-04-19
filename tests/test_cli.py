"""Integration and CLI tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli import main


class TestCliHelp:
    def test_help_exits_zero(self):
        try:
            main(["--help"])
        except SystemExit as exc:
            assert exc.code == 0


class TestCliStatus:
    def test_status_command_runs(self, capsys):
        result = main(["status"])
        assert result == 0
        out = capsys.readouterr().out
        assert "gemini-docter status" in out
        assert "Providers:" in out
