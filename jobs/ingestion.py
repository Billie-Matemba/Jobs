"""
Job ingestion: CSV upload and Adzuna API.
"""

import csv
import io
import logging
from datetime import datetime

import requests
from django.conf import settings
from requests import RequestException

from .models import JobAdvert

logger = logging.getLogger(__name__)

REQUIRED_COLS = {"title", "description"}


class AdzunaAPIError(Exception):
    def __init__(self, message, status_code=None, retryable=True, limit_reached=False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.limit_reached = limit_reached


def import_from_csv(file_bytes: bytes) -> dict:
    """
    Import jobs from CSV bytes. Handles BOM, various encodings.
    Returns {"saved": N, "skipped": M, "errors": [...]}
    """
    # Try UTF-8 with BOM first, then latin-1 as fallback
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        return {"saved": 0, "skipped": 0, "errors": ["Could not decode file. Save as UTF-8 CSV."]}

    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        return {"saved": 0, "skipped": 0, "errors": ["CSV appears empty or has no header row."]}

    # Normalize header names (strip whitespace, lowercase)
    fieldnames_clean = [f.strip().lower() for f in reader.fieldnames]
    missing = REQUIRED_COLS - set(fieldnames_clean)
    if missing:
        return {
            "saved": 0, "skipped": 0,
            "errors": [f"Missing required columns: {', '.join(missing)}. Found: {', '.join(fieldnames_clean)}"]
        }

    saved, skipped, errors = 0, 0, []
    batch = []

    for i, raw_row in enumerate(reader, start=2):
        # Re-key with cleaned names
        row = {k.strip().lower(): v.strip() for k, v in raw_row.items() if k}

        title = row.get("title", "")
        description = row.get("description", "")

        if not title or not description:
            skipped += 1
            continue

        try:
            batch.append(JobAdvert(
                title=title[:255],
                company=row.get("company", "")[:255],
                location=row.get("location", "")[:255],
                description=description,
                url=row.get("url", "")[:500],
                source="csv",
                salary_min=_to_int(row.get("salary_min")),
                salary_max=_to_int(row.get("salary_max")),
            ))
            saved += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")

        # Bulk insert every 500 rows to avoid memory issues
        if len(batch) >= 500:
            JobAdvert.objects.bulk_create(batch, ignore_conflicts=True)
            batch = []

    if batch:
        JobAdvert.objects.bulk_create(batch, ignore_conflicts=True)

    return {"saved": saved, "skipped": skipped, "errors": errors}

def _adzuna_credentials():
    app_id = settings.ADZUNA_APP_ID
    app_key = settings.ADZUNA_APP_KEY
    country = getattr(settings, "ADZUNA_COUNTRY", "za")

    if not app_id or not app_key:
        raise ValueError("Missing ADZUNA credentials")
    return app_id, app_key, country


def fetch_adzuna_page(keyword: str, location: str = "south africa", page: int = 1, per_page: int = 50, progress_callback=None) -> dict:
    app_id, app_key, country = _adzuna_credentials()
    per_page = max(1, min(50, int(per_page)))
    page = max(1, int(page))
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

    try:
        resp = requests.get(url, params={
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": per_page,
            "what": keyword,
            "where": location,
            "content-type": "application/json",
        }, headers={
            "Accept": "application/json",
        }, timeout=20)
    except RequestException as exc:
        raise AdzunaAPIError(f"Adzuna network error: {exc}", retryable=True) from exc

    if resp.status_code != 200:
        raise _adzuna_error_from_response(resp)

    data = resp.json()
    results = data.get("results", [])
    saved = 0
    duplicates = 0

    if progress_callback:
        progress_callback({
            "page": page,
            "saved": saved,
            "duplicates": duplicates,
            "seen": len(results),
            "processed": 0,
            "db_total": JobAdvert.objects.count(),
        })

    for index, item in enumerate(results, start=1):
        ext_id = str(item.get("id", ""))

        if ext_id and JobAdvert.objects.filter(external_id=ext_id).exists():
            duplicates += 1
            if progress_callback:
                progress_callback({
                    "page": page,
                    "saved": saved,
                    "duplicates": duplicates,
                    "seen": len(results),
                    "processed": index,
                    "db_total": JobAdvert.objects.count(),
                })
            continue

        JobAdvert.objects.create(
            title=item.get("title", "")[:255],
            company=item.get("company", {}).get("display_name", "")[:255],
            location=item.get("location", {}).get("display_name", "")[:255],
            description=item.get("description", ""),
            url=item.get("redirect_url", ""),
            source="adzuna",
            external_id=ext_id,
            salary_min=item.get("salary_min"),
            salary_max=item.get("salary_max"),
            date_posted=_parse_date(item.get("created")),
        )
        saved += 1
        if progress_callback:
            progress_callback({
                "page": page,
                "saved": saved,
                "duplicates": duplicates,
                "seen": len(results),
                "processed": index,
                "db_total": JobAdvert.objects.count(),
            })

    return {
        "page": page,
        "saved": saved,
        "duplicates": duplicates,
        "seen": len(results),
        "total_count": int(data.get("count") or 0),
        "db_total": JobAdvert.objects.count(),
        "has_more": len(results) == per_page,
    }


def fetch_from_adzuna(keyword: str, location: str = "south africa", max_results: int = 800) -> int:
    saved = 0
    page = 1
    per_page = 50

    while True:
        result = fetch_adzuna_page(keyword, location, page=page, per_page=per_page)
        if not result["seen"]:
            break

        saved += result["saved"]
        if saved >= max_results:
            return saved
        if not result["has_more"]:
            break

        page += 1

    return saved


def _adzuna_error_from_response(resp):
    detail = _extract_error_detail(resp)
    status = resp.status_code
    if status == 429:
        return AdzunaAPIError(
            f"Adzuna API limit reached or rate limited (HTTP 429). {detail}",
            status_code=status,
            retryable=True,
            limit_reached=True,
        )
    if status in (401, 403):
        return AdzunaAPIError(
            f"Adzuna authentication error (HTTP {status}). Check ADZUNA_APP_ID and ADZUNA_APP_KEY. {detail}",
            status_code=status,
            retryable=False,
        )
    if 400 <= status < 500:
        return AdzunaAPIError(
            f"Adzuna request error (HTTP {status}). {detail}",
            status_code=status,
            retryable=False,
        )
    return AdzunaAPIError(
        f"Adzuna server error (HTTP {status}). {detail}",
        status_code=status,
        retryable=True,
    )


def _extract_error_detail(resp):
    try:
        data = resp.json()
    except ValueError:
        return (resp.text or "").strip()[:300]
    for key in ("error", "message", "display_name", "description"):
        if data.get(key):
            return str(data[key])[:300]
    return str(data)[:300]


def _to_int(val):
    try:
        return int(float(str(val).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:10]).date()
    except Exception:
        return None
