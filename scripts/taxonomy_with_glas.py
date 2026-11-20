"""Run the OpenAI taxonomy benchmark with a BWS-injected API key."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "src" / "taxonomy-bench"
MANIFEST = ROOT / "config" / "glas.benchmark.local.json"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ("run", "matrix"):
        print("Supply an OpenAI run or matrix command", file=sys.stderr)
        return 2
    if "--provider" not in args or args[args.index("--provider") + 1:args.index("--provider") + 2] != ["openai"]:
        print("This GLAS consumer is limited to --provider openai", file=sys.stderr)
        return 2
    if not MANIFEST.is_file():
        print(f"Create the BWS reference manifest at {MANIFEST}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    for name in ("BWS_ACCESS_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        env.pop(name, None)
    sources = []
    if os.environ.get("GLAS_ROOT"):
        sources.append(str(Path(os.environ["GLAS_ROOT"]) / "src"))
    if env.get("PYTHONPATH"):
        sources.append(env["PYTHONPATH"])
    if sources:
        env["PYTHONPATH"] = os.pathsep.join(sources)
    glas_python = os.environ.get("GLAS_PYTHON", sys.executable)
    return subprocess.call(
        [
            glas_python, "-m", "glas", "run", "--manifest", str(MANIFEST), "--",
            sys.executable, str(BENCHMARK / "taxonomy_bench.py"), *args,
        ],
        cwd=BENCHMARK,
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
