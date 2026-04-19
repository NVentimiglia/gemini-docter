#!/usr/bin/env python3
"""Simple entry point for gemini-docter.

Usage:
    py run.py              # full analysis
    py run.py --rules      # generate rules for GEMINI.md
    py run.py --json       # output as JSON
    py run.py --install    # install hooks into ~/.gemini/settings.json
    py run.py --uninstall  # remove hooks
"""

import sys
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent))


def main() -> int:
    if "--install" in sys.argv:
        sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a not in ("--install",)]
        from install_hooks import main as install_main
        return install_main()

    if "--uninstall" in sys.argv:
        sys.argv = [sys.argv[0]] + ["--uninstall"]
        from install_hooks import main as install_main
        return install_main()

    from src.cli import main as cli_main
    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
