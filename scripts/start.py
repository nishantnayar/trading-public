"""Start the Quantis local stack in one terminal with interleaved,
prefixed logs.

Services:
    api      FastAPI      http://127.0.0.1:8000/docs
    ui       Next.js      http://localhost:3000
    prefect  Prefect      http://127.0.0.1:4201   (isolated PREFECT_HOME)

Ctrl+C stops everything. Postgres is expected to be running as a
system service.

Run:  uv run python scripts/start.py
      uv run python scripts/start.py --only api ui
      uv run python scripts/start.py --skip prefect
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IS_WINDOWS = os.name == "nt"
NPM = "npm.cmd" if IS_WINDOWS else "npm"

API_PORT = 8000
UI_PORT = 3000
PREFECT_PORT = 4201

# Honour the NO_COLOR convention (no-color.org). Forcing colour
# anyway is not just rude: node warns "'NO_COLOR' is ignored due
# to 'FORCE_COLOR' being set" once per process, so overriding it
# produced four warning lines on every startup.
COLOR = not os.environ.get("NO_COLOR")
RESET = "\033[0m" if COLOR else ""


def paint(code: str) -> str:
    return code if COLOR else ""


# Child processes emit UTF-8 (Next.js prints a triangle logo and
# check marks), but the pipe was decoded with the Windows locale
# codepage, so those arrived as mojibake. Decoding as UTF-8 fixes
# the garbling; folding to ASCII is still required because this
# console is cp1252 and raises UnicodeEncodeError on the real
# glyphs rather than printing them. Keys are written as escapes so
# this file stays pure ASCII end to end.
GLYPHS = str.maketrans(
    {
        "\u2713": "OK",  # check mark
        "\u2714": "OK",  # heavy check mark
        "\u2717": "x",  # ballot x
        "\u2718": "x",  # heavy ballot x
        "\u00d7": "x",  # multiplication sign
        "\u25b2": "",  # up triangle (Next.js logo)
        "\u25bc": "",  # down triangle
        "\u25cf": "*",  # black circle
        "\u25cb": "o",  # white circle
        "\u2022": "-",  # bullet
        "\u25a0": "#",  # black square
        "\u25b6": ">",  # right triangle
        "\u2192": "->",  # rightwards arrow
        "\u2190": "<-",  # leftwards arrow
        "\u2014": "--",  # em dash
        "\u2013": "-",  # en dash
        "\u2026": "...",  # ellipsis
        "\u26a0": "!",  # warning sign
        "\u2019": "'",  # curly quotes
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",  # non-breaking space
    }
)


def to_ascii(text: str) -> str:
    """Fold a log line to plain ASCII, dropping unmapped glyphs."""
    return text.translate(GLYPHS).encode("ascii", "ignore").decode("ascii")


@dataclass
class Service:
    name: str
    command: list[str]
    color: str
    port: int
    cwd: Path = REPO
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""


def services() -> list[Service]:
    prefect_home = REPO / ".prefect"
    return [
        Service(
            name="api",
            command=[
                "uv", "run", "uvicorn", "quantis.api.main:app",
                "--host", "127.0.0.1", "--port", str(API_PORT),
                # Scope the watcher to source. The default watches
                # the whole repo, which means .venv, node_modules,
                # .next and mlruns - so writing a model artifact
                # during training would restart the API mid-request.
                "--reload", "--reload-dir", str(REPO / "src"),
            ],
            color=paint("\033[36m"),  # cyan
            port=API_PORT,
            url=f"http://127.0.0.1:{API_PORT}/docs",
        ),
        Service(
            name="ui",
            command=[NPM, "run", "dev", "--", "--port", str(UI_PORT)],
            color=paint("\033[35m"),  # magenta
            port=UI_PORT,
            cwd=REPO / "frontend",
            url=f"http://localhost:{UI_PORT}",
        ),
        Service(
            name="prefect",
            command=["uv", "run", "prefect", "server", "start"],
            color=paint("\033[33m"),  # yellow
            port=PREFECT_PORT,
            env={
                "PREFECT_HOME": str(prefect_home),
                "PREFECT_SERVER_API_HOST": "127.0.0.1",
                "PREFECT_SERVER_API_PORT": str(PREFECT_PORT),
                "PREFECT_API_URL": f"http://127.0.0.1:{PREFECT_PORT}/api",
            },
            url=f"http://127.0.0.1:{PREFECT_PORT}",
        ),
    ]


def port_owner(port: int) -> int | None:
    """PID listening on `port`, or None. Windows-only; best-effort."""
    if not IS_WINDOWS:
        return None
    result = subprocess.run(
        ["netstat", "-ano", "-p", "TCP"],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in result.stdout.splitlines():
        parts = line.split()
        if (
            len(parts) >= 5
            and parts[3] == "LISTENING"
            and parts[1].endswith(f":{port}")
        ):
            return int(parts[4])
    return None


def preflight(selected: list[Service]) -> tuple[list[str], list[str]]:
    """Checks run before spawning anything.

    Returns (blockers, warnings). Blockers make startup
    impossible - a taken port means the service cannot bind - so
    we abort instead of emitting a confusing crash log.
    """
    blockers: list[str] = []
    problems: list[str] = []
    names = {service.name for service in selected}

    # A stale listener yields an opaque "WinError 10013" /
    # "EADDRINUSE", so name it here.
    for service in selected:
        with socket.socket() as probe:
            probe.settimeout(0.4)
            if probe.connect_ex(("127.0.0.1", service.port)) != 0:
                continue
        pid = port_owner(service.port)
        owner = (
            f" by PID {pid} - stop it with: "
            f"taskkill /PID {pid} /T /F" if pid else ""
        )
        blockers.append(
            f"port {service.port} ('{service.name}') is already "
            f"in use{owner}"
        )

    if "ui" in names:
        if not (REPO / "frontend" / "node_modules").exists():
            problems.append(
                "frontend/node_modules missing - run: "
                "npm install (in frontend/)"
            )
        env_local = REPO / "frontend" / ".env.local"
        if not env_local.exists():
            env_local.write_text(
                f"NEXT_PUBLIC_API_URL=http://127.0.0.1:{API_PORT}\n"
            )
            print(f"wrote {env_local.relative_to(REPO)}")

    if "prefect" in names:
        (REPO / ".prefect").mkdir(exist_ok=True)

    if "api" in names:
        try:
            import psycopg

            from quantis.config import get_settings

            settings = get_settings()
            if not settings.has_db_password:
                problems.append(
                    "PGPASSWORD not set in .env - API queries will "
                    "return 503"
                )
            else:
                dsn = (
                    f"host={settings.pghost} port={settings.pgport} "
                    f"dbname={settings.pgdatabase} user={settings.pguser} "
                    f"password={settings.pgpassword}"
                )
                with psycopg.connect(dsn, connect_timeout=5):
                    pass
        except Exception as exc:  # noqa: BLE001
            problems.append(
                f"Postgres unreachable ({type(exc).__name__}) - "
                "is the service running?"
            )

    return blockers, problems


def pump(service: Service, process: subprocess.Popen) -> None:
    """Forward one child's output, prefixed for interleaved logs."""
    prefix = f"{service.color}[{service.name:>7}]{RESET} "
    assert process.stdout is not None
    for line in process.stdout:
        text = to_ascii(line).rstrip()
        # Prefect's banner and npm's script echo are padded with
        # blank lines, which turn into a dozen content-free
        # "[prefect]" rows. Drop them.
        if not text:
            continue
        sys.stdout.write(prefix + text + "\n")
        sys.stdout.flush()


def stop(process: subprocess.Popen) -> None:
    """Kill a child and its descendants.

    `npm run dev` spawns node as a grandchild, so terminating
    only the direct child leaves the dev server holding the
    port. taskkill /T covers the whole tree.
    """
    if process.poll() is not None:
        return
    if IS_WINDOWS:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start the Quantis local stack."
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="SVC",
        help="run only these services",
    )
    parser.add_argument(
        "--skip",
        nargs="+",
        metavar="SVC",
        default=[],
        help="skip these",
    )
    args = parser.parse_args(argv)

    selected = services()
    if args.only:
        selected = [s for s in selected if s.name in args.only]
    selected = [s for s in selected if s.name not in args.skip]

    if not selected:
        print("no services selected", file=sys.stderr)
        return 2

    blockers, warnings = preflight(selected)
    for warning in warnings:
        print(f"  warning: {warning}", file=sys.stderr)
    if blockers:
        for blocker in blockers:
            print(f"  ERROR: {blocker}", file=sys.stderr)
        return 1

    running: list[tuple[Service, subprocess.Popen]] = []
    try:
        for service in selected:
            env = {**os.environ, "PYTHONUNBUFFERED": "1", **service.env}
            if COLOR:
                env["FORCE_COLOR"] = "1"
                env.pop("NO_COLOR", None)
            else:
                # Both variables present is what triggers node's
                # warning - and a pre-existing FORCE_COLOR=0
                # counts as "set", so it must go too.
                env.pop("FORCE_COLOR", None)
            process = subprocess.Popen(
                service.command,
                cwd=service.cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                # Without an explicit encoding this defaults to
                # the locale codepage, so node's UTF-8 output
                # arrived mangled. `replace` keeps a stray
                # malformed byte from killing the reader thread
                # mid-log.
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            running.append((service, process))
            threading.Thread(
                target=pump, args=(service, process), daemon=True
            ).start()

        print("\nQuantis stack:")
        for service in selected:
            if service.url:
                print(f"  {service.name:>7}  {service.url}")
        print("\nCtrl+C to stop all.\n")

        while running:
            for service, process in running:
                code = process.poll()
                if code is not None:
                    print(
                        f"\n[{service.name}] exited with code "
                        f"{code} - stopping stack."
                    )
                    return code or 1
            try:
                running[0][1].wait(timeout=1)
            except subprocess.TimeoutExpired:
                continue
    except KeyboardInterrupt:
        print("\nstopping...")
    finally:
        for _, process in reversed(running):
            stop(process)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
