"""
Background task runner using Python threads — no Celery, no Redis needed.

Each function runs in a daemon thread so Django doesn't block waiting for it.
TaskRecord tracks progress exactly as before — the UI polls /api/task/<pk>/
and auto-refreshes until status is SUCCESS or FAILURE.
"""

import logging
import threading
import time

from django.utils import timezone

logger = logging.getLogger(__name__)
STOP_EVENTS = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mark(record_id, status, notes="", progress=None):
    """Update a TaskRecord status. Safe to call from any thread."""
    from analysis.models import TaskRecord
    updates = {
        "status": status,
        "notes": notes,
        "finished_at": timezone.now() if status in ("SUCCESS", "FAILURE", "STOPPED") else None,
    }
    if progress is not None:
        updates["progress"] = max(0, min(100, int(progress)))
    TaskRecord.objects.filter(id=record_id).update(**updates)


def _stopped(record_id):
    event = STOP_EVENTS.get(record_id)
    return bool(event and event.is_set())


def _run_in_thread(fn, *args, **kwargs):
    """Spawn fn(*args, **kwargs) as a daemon thread and return immediately."""
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------------------
# Task functions (called in threads)
# ---------------------------------------------------------------------------

def _do_gap_analysis(run_name, record_id):
    from analysis.services import run_gap_analysis
    _mark(record_id, "STARTED", "Preparing analysis...", 1)
    try:
        def report(percent, notes):
            _mark(record_id, "STARTED", notes, percent)

        run = run_gap_analysis(run_name=run_name, progress_callback=report)
        _mark(record_id, "SUCCESS", f"Done. AnalysisRun ID: {run.id}", 100)
    except Exception as exc:
        logger.error(f"Gap analysis failed: {exc}", exc_info=True)
        _mark(record_id, "FAILURE", str(exc))


def _do_csv_import(csv_bytes, record_id):
    from jobs.ingestion import import_from_csv
    _mark(record_id, "STARTED", "Importing CSV...", 10)
    try:
        result = import_from_csv(csv_bytes)
        notes = f"Saved: {result['saved']}, Skipped: {result['skipped']}"
        if result["errors"]:
            notes += f" | Errors: {'; '.join(str(e) for e in result['errors'][:3])}"
        _mark(record_id, "SUCCESS", notes, 100)
    except Exception as exc:
        logger.error(f"CSV import failed: {exc}", exc_info=True)
        _mark(record_id, "FAILURE", str(exc))


def _do_adzuna_fetch(keyword, location, max_results, record_id):
    from jobs.ingestion import fetch_from_adzuna
    _mark(record_id, "STARTED", "Fetching jobs from Adzuna...", 10)
    try:
        count = fetch_from_adzuna(keyword, location, max_results)
        _mark(record_id, "SUCCESS", f"Fetched {count} new jobs for '{keyword}'", 100)
    except Exception as exc:
        logger.error(f"Adzuna fetch failed: {exc}", exc_info=True)
        _mark(record_id, "FAILURE", str(exc))


def _do_continuous_adzuna_fetch(keyword, location, max_results, interval_seconds, record_id):
    from jobs.ingestion import fetch_from_adzuna

    cycle = 0
    try:
        while not _stopped(record_id):
            cycle += 1
            _mark(record_id, "STARTED", f"Jobs cycle {cycle}: fetching up to {max_results} jobs for '{keyword}'...", 10)
            saved = fetch_from_adzuna(keyword, location, max_results)
            if _stopped(record_id):
                break

            _mark(record_id, "STARTED", f"Jobs cycle {cycle}: fetched {saved} new jobs. Waiting {interval_seconds} seconds before the next fetch...", 85)
            for remaining in range(max(1, int(interval_seconds)), 0, -1):
                if _stopped(record_id):
                    break
                if remaining == interval_seconds or remaining <= 5 or remaining % 10 == 0:
                    _mark(record_id, "STARTED", f"Jobs cycle {cycle}: next fetch in {remaining} seconds.", 90)
                time.sleep(1)

        _mark(record_id, "STOPPED", "Jobs-only fetch loop paused by user.", 100)
    except Exception as exc:
        logger.error(f"Continuous Adzuna fetch failed: {exc}", exc_info=True)
        _mark(record_id, "FAILURE", str(exc))
    finally:
        STOP_EVENTS.pop(record_id, None)


def _do_continuous_job_cycle(keyword, location, max_results, interval_seconds, record_id):
    from analysis.services import run_gap_analysis
    from jobs.ingestion import fetch_from_adzuna

    cycle = 0
    try:
        while not _stopped(record_id):
            cycle += 1
            _mark(record_id, "STARTED", f"Cycle {cycle}: fetching jobs for '{keyword}'...", 5)
            saved = fetch_from_adzuna(keyword, location, max_results)
            if _stopped(record_id):
                break

            _mark(record_id, "STARTED", f"Cycle {cycle}: fetched {saved} new jobs. Running analysis...", 35)

            def report(percent, notes):
                if _stopped(record_id):
                    raise InterruptedError("Live pipeline paused by user.")
                mapped = 35 + int(55 * max(0, min(100, percent)) / 100)
                _mark(record_id, "STARTED", f"Cycle {cycle}: {notes}", mapped)

            run = run_gap_analysis(run_name=f"Live Run {cycle}", progress_callback=report)
            _mark(record_id, "STARTED", f"Cycle {cycle}: analysis #{run.id} complete. Waiting for next fetch...", 95)

            for _ in range(max(1, int(interval_seconds))):
                if _stopped(record_id):
                    break
                time.sleep(1)

        _mark(record_id, "STOPPED", "Live pipeline paused by user.", 100)
    except InterruptedError:
        _mark(record_id, "STOPPED", "Live pipeline paused by user.", 100)
    except Exception as exc:
        logger.error(f"Continuous job cycle failed: {exc}", exc_info=True)
        _mark(record_id, "FAILURE", str(exc))
    finally:
        STOP_EVENTS.pop(record_id, None)


# ---------------------------------------------------------------------------
# Public API — drop-in replacements for the old Celery .delay() calls
# ---------------------------------------------------------------------------

def run_gap_analysis_task(run_name="Analysis Run", record_id=None):
    """Start gap analysis in a background thread."""
    _run_in_thread(_do_gap_analysis, run_name, record_id)


def import_csv_task(csv_bytes, record_id=None):
    """Import CSV in a background thread. csv_bytes must be bytes."""
    _run_in_thread(_do_csv_import, csv_bytes, record_id)


def fetch_adzuna_task(keyword, location="south africa", max_results=50, record_id=None):
    """Fetch Adzuna jobs in a background thread."""
    _run_in_thread(_do_adzuna_fetch, keyword, location, max_results, record_id)


def start_continuous_job_task(keyword, location="south africa", max_results=50, interval_seconds=30, record_id=None):
    """Continuously fetch jobs and run gap analysis until paused."""
    STOP_EVENTS[record_id] = threading.Event()
    _run_in_thread(_do_continuous_job_cycle, keyword, location, max_results, interval_seconds, record_id)


def start_continuous_adzuna_task(keyword, location="south africa", max_results=50, interval_seconds=30, record_id=None):
    """Continuously fetch Adzuna jobs only until paused."""
    STOP_EVENTS[record_id] = threading.Event()
    _run_in_thread(_do_continuous_adzuna_fetch, keyword, location, max_results, interval_seconds, record_id)


def stop_task(record_id):
    event = STOP_EVENTS.get(record_id)
    if event:
        event.set()
        _mark(record_id, "STARTED", "Pause requested. Finishing the current step...", None)
        return True
    _mark(record_id, "STOPPED", "Pause requested.", 100)
    return False
