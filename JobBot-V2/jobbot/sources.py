"""Job data sources. Primary: JobSpy (scrapes Indeed/LinkedIn/etc. via a
maintained library). Optional: JSearch API when RAPIDAPI_KEY is set."""

from __future__ import annotations

import logging
import math
import os
import time

import requests
from jobspy import scrape_jobs

log = logging.getLogger("jobbot.sources")


def _clean(value):
    """Normalize pandas NaN/NaT and empty strings to None."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None


def fetch_jobspy(config: dict, cancel=None) -> list[dict]:
    search = config["search"]
    jobs: list[dict] = []
    for term in search["terms"]:
        if cancel is not None and cancel.is_set():
            log.info("JobSpy: cancelled")
            break
        log.info("JobSpy: searching %r in %s ...", term, search["location"])
        try:
            df = scrape_jobs(
                site_name=search["sites"],
                search_term=term,
                location=search["location"],
                distance=search.get("radius_miles", 50),
                results_wanted=search["results_per_term"],
                hours_old=search["hours_old"],
                country_indeed=search["country_indeed"],
                verbose=0,
            )
        except Exception as exc:  # one failing term shouldn't kill the run
            log.warning("JobSpy search for %r failed: %s", term, exc)
            continue
        for _, row in df.iterrows():
            jobs.append(
                {
                    "source": _clean(row.get("site")) or "jobspy",
                    "title": _clean(row.get("title")),
                    "company": _clean(row.get("company")),
                    "location": _clean(row.get("location")),
                    "description": _clean(row.get("description")),
                    "url": _clean(row.get("job_url")),
                    "salary_min": _num(row.get("min_amount")),
                    "salary_max": _num(row.get("max_amount")),
                    "is_remote": bool(row.get("is_remote"))
                    if _clean(row.get("is_remote")) is not None
                    else False,
                    "date_posted": _clean(row.get("date_posted")),
                    "search_term": term,
                }
            )
    return jobs


def _num(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def fetch_jsearch(config: dict, cancel=None) -> list[dict]:
    """Secondary source: JSearch (Google for Jobs aggregator). Free tier is
    200 requests/month, so this runs one request per search term."""
    api_key = os.environ.get("RAPIDAPI_KEY")
    if not api_key:
        return []
    search = config["search"]
    jobs: list[dict] = []
    for i, term in enumerate(search["terms"]):
        if cancel is not None and cancel.is_set():
            log.info("JSearch: cancelled")
            break
        if i:
            time.sleep(1.5)  # free tier allows ~1 request/second
        log.info("JSearch: searching %r ...", term)
        try:
            resp = requests.get(
                "https://jsearch.p.rapidapi.com/search",
                headers={
                    "X-RapidAPI-Key": api_key,
                    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
                },
                params={
                    "query": f"{term} in {search['location']}",
                    "num_pages": 1,
                    "date_posted": "week",
                    # JSearch radius is in km
                    "radius": round(search.get("radius_miles", 50) * 1.609),
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except Exception as exc:
            log.warning("JSearch search for %r failed: %s", term, exc)
            continue
        for item in data:
            city = item.get("job_city") or ""
            state = item.get("job_state") or ""
            jobs.append(
                {
                    "source": "jsearch",
                    "title": item.get("job_title"),
                    "company": item.get("employer_name"),
                    "location": ", ".join(p for p in (city, state) if p) or None,
                    "description": item.get("job_description"),
                    "url": item.get("job_apply_link"),
                    "salary_min": item.get("job_min_salary"),
                    "salary_max": item.get("job_max_salary"),
                    "is_remote": bool(item.get("job_is_remote")),
                    "date_posted": (item.get("job_posted_at_datetime_utc") or "")[:10]
                    or None,
                    "search_term": term,
                }
            )
    return jobs


def annualized(amount) -> float | None:
    """Boards mix annual and hourly figures; treat small values as hourly."""
    if amount is None:
        return None
    return amount * 2080 if amount < 1000 else amount


def passes_filters(job: dict, config: dict) -> bool:
    title = (job.get("title") or "").lower()
    if not title or not job.get("company"):
        return False
    for keyword in config["filters"]["exclude_title_keywords"]:
        if keyword.lower() in title:
            return False
    min_salary = config["filters"]["min_salary"]
    salary_max = annualized(job.get("salary_max"))
    if min_salary and salary_max and salary_max < min_salary:
        return False
    return True


def fetch_all(config: dict, cancel=None) -> list[dict]:
    jobs = fetch_jobspy(config, cancel) + fetch_jsearch(config, cancel)
    kept = [job for job in jobs if passes_filters(job, config)]
    log.info("Fetched %d jobs, %d after filters", len(jobs), len(kept))
    return kept
