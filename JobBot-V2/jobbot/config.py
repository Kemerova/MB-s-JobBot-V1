"""Configuration loading: config.yaml + .env."""

from __future__ import annotations

from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    "search": {
        "terms": ["Software Engineer"],
        "location": "Austin, TX",
        "radius_miles": 50,
        "sites": ["indeed"],
        "results_per_term": 25,
        "hours_old": 168,
        "country_indeed": "USA",
    },
    "filters": {
        "min_salary": 0,
        "exclude_title_keywords": [],
    },
    "analysis": {
        "enabled": True,
        "score_model": "claude-haiku-4-5",
        "bullets_model": "claude-opus-4-8",
        "score_threshold": 70,
        "max_description_chars": 6000,
    },
    "resume_path": "resume/base_resume.txt",
    "output_dir": "output",
}


def _merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        elif value is not None:
            merged[key] = value
    return merged


def load_config(path: str | Path | None = None) -> dict:
    load_dotenv(PROJECT_ROOT / ".env")
    config_path = Path(path) if path else PROJECT_ROOT / "config.yaml"
    user_config = {}
    if config_path.exists():
        user_config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config = _merge(DEFAULTS, user_config)
    config["_root"] = PROJECT_ROOT
    return config


def resume_text(config: dict) -> str:
    path = Path(config["resume_path"])
    if not path.is_absolute():
        path = config["_root"] / path
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    return ""


def output_dir(config: dict) -> Path:
    path = Path(config["output_dir"])
    if not path.is_absolute():
        path = config["_root"] / path
    path.mkdir(parents=True, exist_ok=True)
    return path
