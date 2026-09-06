"""Register cron deployments on a process work pool and poll it.

Requires the Prefect API (scripts/start.py's prefect service on :4201). This process
creates the pool, applies deployments, then starts a process worker so the Work Pools
page shows an active worker.

    uv run python -m quantis.orchestration.serve

Or from the launcher (Prefect server + this runner together):

    uv run python scripts/start.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from loguru import logger
from prefect.exceptions import ObjectAlreadyExists
from prefect.flows import EntrypointType
from prefect.utilities.asyncutils import sync_compatible

from quantis.config import _REPO_ROOT, get_settings
from quantis.orchestration.flows import (
    ingest_incremental,
    weekly_rebalance,
    weekly_research,
)


def pin_quantis_prefect_env() -> str:
    """Force this process onto Quantis' Prefect server, not the default :4200."""
    settings = get_settings()
    home = _REPO_ROOT / ".prefect"
    home.mkdir(exist_ok=True)
    os.environ["PREFECT_HOME"] = str(home)
    os.environ["PREFECT_API_URL"] = settings.prefect_api_url
    os.environ.setdefault(
        "PYTHONWARNINGS",
        "ignore::RuntimeWarning:runpy,ignore::DeprecationWarning:prefect.engine",
    )
    return settings.prefect_api_url


def wait_for_prefect(timeout: float = 60.0) -> None:
    """Block until the local Prefect API answers, so apply() does not race startup."""
    url = os.environ.get("PREFECT_API_URL") or get_settings().prefect_api_url
    health = url.rstrip("/") + "/health"
    deadline = time.monotonic() + timeout
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=2) as resp:
                if 200 <= resp.status < 300:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
        time.sleep(1)
    raise RuntimeError(
        f"Prefect API not reachable at {health}: {last}. "
        "Start the server first: uv run python scripts/start.py --only prefect"
    )


@sync_compatible
async def ensure_work_pool(name: str) -> str:
    """Create the local process pool if missing. Idempotent."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolCreate

    async with get_client() as client:
        try:
            await client.create_work_pool(
                WorkPoolCreate(
                    name=name,
                    type="process",
                    description="Quantis local process pool (ingest, research, rebalance).",
                )
            )
            logger.info("created work pool {}", name)
        except ObjectAlreadyExists:
            logger.info("work pool {} already exists", name)
    return name


def _prefect_cli() -> str:
    name = "prefect.exe" if os.name == "nt" else "prefect"
    return str(Path(sys.executable).with_name(name))


def apply_deployments(pool: str) -> None:
    """Point the three cron jobs at `pool` so a process worker can pick them up.

    Kwargs are passed explicitly (not via `**dict`) so the type checker can match
    `to_deployment`'s overloads. `.apply()` and the `.flow_name`/`.name` attributes come
    from Prefect's `sync_compatible` runner API, which the stubs type as async — the
    ignores below are that framework-boundary gap, not a real coroutine.
    """
    job_variables = {"working_dir": str(_REPO_ROOT)}
    ingest = ingest_incremental.to_deployment(
        name="daily-ingest",
        cron="15 17 * * 1-5",
        tags=["quantis", "ingest"],
        description="Incremental daily bars (last stored date minus 10-day overlap).",
        work_pool_name=pool,
        entrypoint_type=EntrypointType.MODULE_PATH,
        job_variables=job_variables,
    )
    research = weekly_research.to_deployment(
        name="weekly-research",
        cron="0 8 * * 6",
        tags=["quantis", "research"],
        description="Rebuild features, retrain LightGBM, publish scores/weights.",
        work_pool_name=pool,
        entrypoint_type=EntrypointType.MODULE_PATH,
        job_variables=job_variables,
    )
    rebalance = weekly_rebalance.to_deployment(
        name="weekly-rebalance",
        cron="40 9 * * 1",
        tags=["quantis", "rebalance"],
        description="Simulated (default) or alpaca-paper rebalance to published weights.",
        work_pool_name=pool,
        entrypoint_type=EntrypointType.MODULE_PATH,
        job_variables=job_variables,
    )
    for deployment in (ingest, research, rebalance):
        deployment.apply()  # type: ignore[attr-defined]
        logger.info(
            "applied {}/{} on pool {}",
            deployment.flow_name,  # type: ignore[attr-defined]
            deployment.name,  # type: ignore[attr-defined]
            pool,
        )


def start_worker(pool: str) -> int:
    """Poll the pool. --install-policy never avoids an interactive prompt."""
    cmd = [
        _prefect_cli(),
        "worker",
        "start",
        "--pool",
        pool,
        "--type",
        "process",
        "--name",
        "quantis",
        "--install-policy",
        "never",
    ]
    logger.info("starting process worker on pool {}", pool)
    return subprocess.call(cmd)


def main() -> None:
    api_url = pin_quantis_prefect_env()
    pool = get_settings().prefect_work_pool
    logger.info("registering deployments at {} on pool {}", api_url, pool)
    wait_for_prefect()
    ensure_work_pool(pool)  # type: ignore[unused-coroutine]  # @sync_compatible runs sync here
    apply_deployments(pool)
    raise SystemExit(start_worker(pool))


if __name__ == "__main__":
    main()
