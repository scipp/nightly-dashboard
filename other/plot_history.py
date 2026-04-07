import argparse
import csv
import logging
import os
from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pytz
import requests

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

GITLAB_API_URL = "https://git.esss.dk/api/v4"
PROJECT_ID = 301  # dmsc-nightly
TIMEZONE = pytz.timezone("Europe/Copenhagen")
TOKEN = os.getenv("GITLAB_PRIVATE_TOKEN")

INSTRUMENTS = [
    "beer",
    "bifrost",
    "dream",
    "estia",
    "loki",
    "nmx",
    "odin",
    "tbl",
]

CACHE_FIELDS = [
    "date_local",
    "year",
    "month",
    "pipeline_id",
    "total_tests",
    "num_instruments",
    "instruments",
    "source",  # test_report | jobs
]


def _headers() -> Dict[str, str]:
    # if not TOKEN:
    #     raise RuntimeError("GITLAB_PRIVATE_TOKEN is not set.")
    return {"Authorization": f"PRIVATE-TOKEN {TOKEN}"}


def _parse_dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _paginate(url: str, params: Dict[str, str]) -> Iterable[dict]:
    page = 1
    while True:
        p = dict(params)
        p["page"] = page
        logging.info(f"GET {url} page={page} per_page={p.get('per_page')}")
        resp = requests.get(url, headers=_headers(), params=p, timeout=60)
        resp.raise_for_status()
        items = resp.json()
        if not items:
            return
        yield from items

        next_page = resp.headers.get("X-Next-Page")
        if not next_page:
            return
        page = int(next_page)


def list_all_scheduled_pipelines(project_id: int) -> List[dict]:
    url = f"{GITLAB_API_URL}/projects/{project_id}/pipelines"
    params = {
        "source": "schedule",
        "order_by": "updated_at",
        "sort": "asc",  # ascending helps progressive processing
        "per_page": "100",
    }
    return list(_paginate(url, params=params))


def get_test_report(project_id: int, pipeline_id: int) -> dict:
    url = f"{GITLAB_API_URL}/projects/{project_id}/pipelines/{pipeline_id}/test_report"
    resp = requests.get(url, headers=_headers(), timeout=60)
    resp.raise_for_status()
    return resp.json()


def is_empty_test_report(report: dict) -> bool:
    if not isinstance(report, dict) or not report:
        return True
    suites = report.get("test_suites")
    if suites is None:
        return True
    if isinstance(suites, list) and len(suites) == 0:
        return True
    return False


def total_tests_in_report(report: dict) -> int:
    if report.get("total_count") is not None:
        return int(report["total_count"])
    return (
        int(report.get("success_count", 0))
        + int(report.get("failed_count", 0))
        + int(report.get("error_count", 0))
        + int(report.get("skipped_count", 0))
    )


def instruments_in_report(report: dict) -> List[str]:
    found = set()
    for suite in report.get("test_suites", []):
        name = (suite.get("name") or "").lower()
        for instr in INSTRUMENTS:
            if instr in name:
                found.add(instr)
    return sorted(found)


def get_pipeline_jobs(project_id: int, pipeline_id: int) -> List[dict]:
    # Paginate because pipelines can have >100 jobs.
    url = f"{GITLAB_API_URL}/projects/{project_id}/pipelines/{pipeline_id}/jobs"
    params = {"per_page": "100"}
    return list(_paginate(url, params=params))


def total_jobs_as_tests(jobs: List[dict]) -> int:
    # Count jobs in any status (as requested)
    return len(jobs)


def instruments_from_jobs_brackets(jobs: List[dict]) -> List[str]:
    found = set()
    for j in jobs:
        name = (j.get("name") or "").lower()
        for instr in INSTRUMENTS:
            if f"[{instr}]" in name:
                found.add(instr)
    return sorted(found)


def load_cache(path: str) -> Dict[int, dict]:
    """
    Returns mapping pipeline_id -> cached row.
    """
    if not path or not os.path.exists(path):
        return {}

    cached: Dict[int, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if not row.get("pipeline_id"):
                continue
            pid = int(row["pipeline_id"])
            # Normalize types a bit (still keep strings for CSV rewrite)
            row["pipeline_id"] = str(pid)
            cached[pid] = row

    logging.info(f"Loaded cache: {path} ({len(cached)} pipelines)")
    return cached


def compute_monthly_averages(daily_rows: List[dict]) -> List[dict]:
    by_month: Dict[Tuple[int, int], List[dict]] = defaultdict(list)
    for r in daily_rows:
        by_month[(int(r["year"]), int(r["month"]))].append(r)

    monthly = []
    for (y, m), rows in sorted(by_month.items()):
        monthly.append(
            {
                "year": y,
                "month": m,
                "date": datetime(y, m, 1),
                "avg_total_tests": mean(int(r["total_tests"]) for r in rows),
                "avg_num_instruments": mean(int(r["num_instruments"]) for r in rows),
                "n_days": len(rows),
            }
        )
    return monthly


def plot(monthly_rows: List[dict], out_png: str, title: str) -> None:
    dates = [r["date"] for r in monthly_rows]

    # ax1: instruments (C0, solid, no markers)
    avg_instruments = [r["avg_num_instruments"] for r in monthly_rows]
    # ax2: tests (C1, line + 'o' markers)
    avg_total_tests = [r["avg_total_tests"] for r in monthly_rows]

    fig, ax1 = plt.subplots(figsize=(10, 5))

    ax1.plot(
        dates,
        avg_instruments,
        color="C0",
        linestyle="-",
        linewidth=2,
        marker=None,
        label="Instruments",
    )
    ax1.set_ylabel("Number of instruments")
    ax1.grid(True, which="major", axis="x", alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(dates, avg_total_tests, "-o", color="C1", linewidth=2, label="Tests")
    ax2.set_ylabel("Number of tests")
    ax2.grid(True, which="major", axis="y", alpha=0.3)

    ax1.set_title(title)

    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate(rotation=45, ha="right")

    ax1.legend(loc=2)
    ax2.legend(loc=4)

    plt.tight_layout()
    plt.savefig(out_png, dpi=200)
    logging.info(f"Wrote plot: {out_png}")


def compute_row_for_pipeline(pid: int, updated_at_iso: str) -> dict:
    dt_local = _parse_dt(updated_at_iso).astimezone(TIMEZONE)

    report = get_test_report(PROJECT_ID, pid)
    if not is_empty_test_report(report):
        total = total_tests_in_report(report)
        instruments = instruments_in_report(report)
        source = "test_report"
    else:
        jobs = get_pipeline_jobs(PROJECT_ID, pid)
        total = total_jobs_as_tests(jobs)
        instruments = instruments_from_jobs_brackets(jobs)
        source = "jobs"

    return {
        "date_local": dt_local.strftime("%Y-%m-%dT%H:%M:%S"),
        "year": str(dt_local.year),
        "month": str(dt_local.month),
        "pipeline_id": str(pid),
        "total_tests": str(total),
        "num_instruments": str(len(instruments)),
        "instruments": ",".join(instruments),
        "source": source,
    }


def append_row_to_cache(path: str, row: dict) -> None:
    """
    Append a single row to the CSV cache, creating it (with header) if needed.
    Flushes after each write so progress survives interruptions.
    """
    file_exists = os.path.exists(path)

    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CACHE_FIELDS)

        if not file_exists:
            w.writeheader()

        out = {k: row.get(k, "") for k in CACHE_FIELDS}
        w.writerow(out)

        # Make partial progress durable even if the process dies.
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            # Some filesystems may not support fsync; flush is still helpful.
            pass


def main(out_png: str, cache_csv: Optional[str]) -> None:
    cache_by_pid = load_cache(cache_csv) if cache_csv else {}

    pipelines = list_all_scheduled_pipelines(PROJECT_ID)
    logging.info(f"Fetched scheduled pipelines (full history): {len(pipelines)}")

    fetched = 0
    skipped = 0

    for p in pipelines:
        logging.info(f"Processing pipeline: {p['id']}")
        pid = int(p["id"])
        updated_at = p["updated_at"]

        if pid in cache_by_pid:
            skipped += 1
            continue

        row = compute_row_for_pipeline(pid, updated_at_iso=updated_at)

        # Update in-memory cache
        cache_by_pid[pid] = row

        # Persist immediately (append-only)
        if cache_csv:
            append_row_to_cache(cache_csv, row)

        fetched += 1

    logging.info(f"Cache update complete. fetched={fetched}, skipped={skipped}")

    # For plotting, read from memory (which includes newly appended rows).
    daily_rows = list(cache_by_pid.values())
    monthly = compute_monthly_averages(daily_rows)

    title = "DMSC nightly integration tests"
    plot(monthly, out_png=out_png, title=title)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plot monthly averages of total tests and instrument coverage from scheduled pipelines."
    )
    parser.add_argument(
        "--out",
        default="monthly_avg_tests_and_coverage.png",
        help="Output PNG path",
    )
    parser.add_argument(
        "--cache-csv",
        default="daily_tests_and_coverage.csv",
        help="CSV cache path (reused between runs). Delete it to refetch everything.",
    )
    args = parser.parse_args()

    main(out_png=args.out, cache_csv=args.cache_csv)
