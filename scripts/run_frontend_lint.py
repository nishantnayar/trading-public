"""Run frontend ESLint without requiring node/npm to be on PATH (Git GUI commits)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
ESLINT_JS = FRONTEND / "node_modules" / "eslint" / "bin" / "eslint.js"
NODE_CANDIDATES = (
    Path(r"C:\Program Files\nodejs\node.exe"),
    Path(r"C:\Program Files (x86)\nodejs\node.exe"),
    Path("/usr/bin/node"),
    Path("/usr/local/bin/node"),
)


def _node() -> Path | None:
    found = shutil.which("node") or shutil.which("node.exe")
    for candidate in (Path(found) if found else None, *NODE_CANDIDATES):
        if candidate is not None and candidate.exists():
            return candidate
    return None


def main() -> int:
    if not ESLINT_JS.exists():
        print("frontend/node_modules missing — run: cd frontend && npm install", file=sys.stderr)
        return 1
    node = _node()
    if node is None:
        print("node not found — install Node.js 22+", file=sys.stderr)
        return 1
    return subprocess.call([str(node), str(ESLINT_JS)], cwd=FRONTEND)


if __name__ == "__main__":
    raise SystemExit(main())
