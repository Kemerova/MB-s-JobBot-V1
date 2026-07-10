"""FastAPI backend for the JobBot GUI.

The GUI is a single-page app served from jobbot/static/index.html; this module
provides the JSON API it talks to. Searches run in a background thread and
report progress through /api/search/status.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import config as config_mod
from . import dashboard as dashboard_mod
from . import export as export_mod
from . import sources
from .analyzer import Analyzer
from .store import STATUSES, Store

log = logging.getLogger("jobbot.server")

app = FastAPI(title="JobBot V2")

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Search progress shared between the worker thread and status requests.
_search_lock = threading.Lock()
_search_cancel = threading.Event()
_search_state = {
    "running": False,
    "phase": "idle",       # idle | fetching | scoring | done | error
    "message": "",
    "scored": 0,
    "to_score": 0,
    "new_jobs": 0,
}


def _config() -> dict:
    return config_mod.load_config()


def _store(config: dict) -> Store:
    return Store(config_mod.output_dir(config) / "jobbot.db")


def _set_state(**kwargs) -> None:
    with _search_lock:
        _search_state.update(kwargs)


def _regen_static_dashboard(config: dict, store: Store) -> None:
    """Keep the standalone output/dashboard.html in sync as a bonus artifact."""
    try:
        dashboard_mod.generate(
            store.all_jobs(), store.stats(), config_mod.output_dir(config) / "dashboard.html"
        )
    except Exception:  # the GUI is the primary surface; never fail on this
        log.exception("static dashboard regeneration failed")


# ---------------------------------------------------------------- pages

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


# ---------------------------------------------------------------- jobs

@app.get("/api/jobs")
def get_jobs():
    config = _config()
    store = _store(config)
    try:
        return {"jobs": store.all_jobs(), "stats": store.stats()}
    finally:
        store.close()


class StatusUpdate(BaseModel):
    status: str
    notes: str | None = None


@app.post("/api/jobs/{job_id}/status")
def update_status(job_id: str, body: StatusUpdate):
    if body.status not in STATUSES:
        raise HTTPException(400, f"status must be one of {STATUSES}")
    config = _config()
    store = _store(config)
    try:
        if not store.set_status(job_id, body.status, body.notes):
            raise HTTPException(404, "job not found")
        _regen_static_dashboard(config, store)
        return {"ok": True}
    finally:
        store.close()


@app.post("/api/jobs/{job_id}/bullets")
def generate_bullets(job_id: str):
    config = _config()
    store = _store(config)
    try:
        row = store.get_job(job_id)
        if not row:
            raise HTTPException(404, "job not found")
        analyzer = Analyzer(config, config_mod.resume_text(config))
        try:
            bullets = analyzer.generate_bullets(dict(row))
        except Exception as exc:
            raise HTTPException(502, f"bullet generation failed: {exc}")
        store.save_bullets(job_id, bullets)
        _regen_static_dashboard(config, store)
        return {"bullets": bullets}
    finally:
        store.close()


@app.post("/api/jobs/{job_id}/cover")
def generate_cover(job_id: str):
    config = _config()
    store = _store(config)
    try:
        row = store.get_job(job_id)
        if not row:
            raise HTTPException(404, "job not found")
        analyzer = Analyzer(config, config_mod.resume_text(config))
        try:
            letter = analyzer.generate_cover_letter(dict(row))
        except Exception as exc:
            raise HTTPException(502, f"cover letter generation failed: {exc}")
        store.save_cover_letter(job_id, letter)
        return {"cover_letter": letter}
    finally:
        store.close()


# ---------------------------------------------------------------- search

def _run_search() -> None:
    try:
        config = _config()
        _set_state(running=True, phase="fetching", message="Fetching job boards...",
                   scored=0, to_score=0, new_jobs=0)
        jobs = sources.fetch_all(config, cancel=_search_cancel)
        store = _store(config)
        try:
            new_count = store.upsert_jobs(jobs)
            unscored = store.unscored_jobs()
            _set_state(phase="scoring", new_jobs=new_count, to_score=len(unscored),
                       message=f"Fetched {len(jobs)} jobs ({new_count} new). "
                               f"Scoring {len(unscored)}...")
            if unscored and config["analysis"]["enabled"]:
                analyzer = Analyzer(config, config_mod.resume_text(config))
                for i, row in enumerate(unscored, 1):
                    if _search_cancel.is_set():
                        break
                    job = dict(row)
                    result = analyzer.score_job(job)
                    store.save_score(job["id"], result.score, result.fit_summary,
                                     result.strengths, result.gaps)
                    _set_state(scored=i,
                               message=f"Scored {i}/{len(unscored)}: "
                                       f"{job['title']} @ {job['company']}")
            _regen_static_dashboard(config, store)
            if _search_cancel.is_set():
                _set_state(running=False, phase="done",
                           message=f"Search stopped. {new_count} new jobs kept; "
                                   "partial scores saved.")
            else:
                _set_state(running=False, phase="done",
                           message=f"Done. {new_count} new jobs added.")
        finally:
            store.close()
    except Exception as exc:
        log.exception("search failed")
        _set_state(running=False, phase="error", message=f"Search failed: {exc}")


@app.post("/api/search")
def start_search():
    with _search_lock:
        if _search_state["running"]:
            raise HTTPException(409, "a search is already running")
        _search_state.update(running=True, phase="fetching",
                             message="Starting...", scored=0, to_score=0)
    _search_cancel.clear()
    threading.Thread(target=_run_search, daemon=True).start()
    return {"ok": True}


@app.post("/api/search/cancel")
def cancel_search():
    with _search_lock:
        if not _search_state["running"]:
            raise HTTPException(409, "no search is running")
        _search_state["message"] = "Stopping after the current step..."
    _search_cancel.set()
    return {"ok": True}


@app.get("/api/search/status")
def search_status():
    with _search_lock:
        return dict(_search_state)


@app.post("/api/suggest-terms")
def suggest_terms():
    config = _config()
    analyzer = Analyzer(config, config_mod.resume_text(config))
    try:
        roles = analyzer.suggest_roles()
    except Exception as exc:
        raise HTTPException(502, f"suggestion failed: {exc}")
    return {
        "roles": [
            {"title": r.title, "why": r.why, "stretch": r.stretch} for r in roles
        ]
    }


# ---------------------------------------------------------------- export

@app.get("/api/export/{fmt}")
def export_jobs(fmt: str):
    if fmt not in ("xlsx", "csv"):
        raise HTTPException(400, "format must be xlsx or csv")
    config = _config()
    store = _store(config)
    try:
        jobs = store.all_jobs()
    finally:
        store.close()
    out = config_mod.output_dir(config) / export_mod.timestamped("jobbot_export", fmt)
    if fmt == "xlsx":
        export_mod.export_xlsx(jobs, out)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        export_mod.export_csv(jobs, out)
        media = "text/csv"
    return FileResponse(out, media_type=media, filename=out.name)


# ---------------------------------------------------------------- settings

EDITABLE = {
    "search": ["terms", "location", "radius_miles", "sites", "results_per_term",
               "hours_old"],
    "filters": ["min_salary", "exclude_title_keywords"],
    "analysis": ["enabled", "score_threshold"],
}


@app.get("/api/config")
def get_config():
    config = _config()
    return {
        section: {key: config[section][key] for key in keys}
        for section, keys in EDITABLE.items()
    }


@app.put("/api/config")
def put_config(body: dict):
    config_path = config_mod.PROJECT_ROOT / "config.yaml"
    raw = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    for section, keys in EDITABLE.items():
        incoming = body.get(section) or {}
        for key in keys:
            if key in incoming:
                raw.setdefault(section, {})[key] = incoming[key]
    config_path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return get_config()


# ---------------------------------------------------------------- resume

@app.get("/api/resume")
def get_resume():
    return {"text": config_mod.resume_text(_config())}


class ResumeUpdate(BaseModel):
    text: str


@app.put("/api/resume")
def put_resume(body: ResumeUpdate):
    config = _config()
    path = Path(config["resume_path"])
    if not path.is_absolute():
        path = config["_root"] / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.text, encoding="utf-8")
    return {"ok": True, "chars": len(body.text)}
