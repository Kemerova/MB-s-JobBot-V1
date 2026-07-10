"""Command-line interface for JobBot V2."""

from __future__ import annotations

import argparse
import logging
import sys
import webbrowser

from . import config as config_mod
from . import dashboard as dashboard_mod
from . import sources
from .analyzer import Analyzer
from .store import STATUSES, Store

log = logging.getLogger("jobbot")


def _open_store(config: dict) -> Store:
    return Store(config_mod.output_dir(config) / "jobbot.db")


def _regenerate_dashboard(config: dict, store: Store) -> None:
    out = config_mod.output_dir(config) / "dashboard.html"
    dashboard_mod.generate(store.all_jobs(), store.stats(), out)
    print(f"Dashboard: {out}")


def cmd_search(args, config: dict) -> None:
    store = _open_store(config)
    print("Fetching jobs (this can take a minute or two)...")
    jobs = sources.fetch_all(config)
    new_count = store.upsert_jobs(jobs)
    print(f"Fetched {len(jobs)} jobs; {new_count} new.")

    unscored = store.unscored_jobs()
    if unscored and not args.no_analyze:
        resume = config_mod.resume_text(config)
        if not resume:
            print("WARNING: resume file not found; scoring quality will suffer.")
        analyzer = Analyzer(config, resume)
        print(f"Scoring {len(unscored)} jobs with {config['analysis']['score_model']}...")
        for i, row in enumerate(unscored, 1):
            job = dict(row)
            result = analyzer.score_job(job)
            store.save_score(
                job["id"], result.score, result.fit_summary,
                result.strengths, result.gaps,
            )
            print(f"  [{i}/{len(unscored)}] {result.score:>3}  "
                  f"{job['title']} @ {job['company']}")

    _regenerate_dashboard(config, store)
    stats = store.stats()
    print(f"Totals: {stats['total']} jobs, {stats['high'] or 0} scored 70+.")
    if not args.no_open:
        webbrowser.open((config_mod.output_dir(config) / "dashboard.html").as_uri())
    store.close()


def cmd_dashboard(args, config: dict) -> None:
    store = _open_store(config)
    _regenerate_dashboard(config, store)
    if not args.no_open:
        webbrowser.open((config_mod.output_dir(config) / "dashboard.html").as_uri())
    store.close()


def cmd_list(args, config: dict) -> None:
    store = _open_store(config)
    jobs = [j for j in store.all_jobs() if (j["score"] or 0) >= args.min_score]
    for job in jobs[: args.limit]:
        print(f"{job['id']}  {job['score'] or '?':>3}  [{job['status']}] "
              f"{job['title']} @ {job['company']} ({job['location']})")
    if not jobs:
        print("No jobs match. Run `python main.py search` first.")
    store.close()


def cmd_status(args, config: dict) -> None:
    store = _open_store(config)
    if store.set_status(args.job_id, args.status, args.notes):
        job = store.get_job(args.job_id)
        print(f"{job['title']} @ {job['company']} -> {args.status}")
    else:
        print(f"No job with id {args.job_id}", file=sys.stderr)
        sys.exit(1)
    _regenerate_dashboard(config, store)
    store.close()


def cmd_bullets(args, config: dict) -> None:
    store = _open_store(config)
    row = store.get_job(args.job_id)
    if not row:
        print(f"No job with id {args.job_id}", file=sys.stderr)
        sys.exit(1)
    job = dict(row)
    analyzer = Analyzer(config, config_mod.resume_text(config))
    print(f"Generating tailored bullets for {job['title']} @ {job['company']} "
          f"with {config['analysis']['bullets_model']}...")
    bullets = analyzer.generate_bullets(job)
    store.save_bullets(job["id"], bullets)
    print()
    for bullet in bullets:
        print(f"  * {bullet}")
    _regenerate_dashboard(config, store)
    store.close()


def cmd_cover(args, config: dict) -> None:
    store = _open_store(config)
    row = store.get_job(args.job_id)
    if not row:
        print(f"No job with id {args.job_id}", file=sys.stderr)
        sys.exit(1)
    job = dict(row)
    analyzer = Analyzer(config, config_mod.resume_text(config))
    print(f"Writing cover letter for {job['title']} @ {job['company']}...")
    letter = analyzer.generate_cover_letter(job)
    store.save_cover_letter(job["id"], letter)
    print()
    print(letter)
    store.close()


def cmd_suggest(args, config: dict) -> None:
    analyzer = Analyzer(config, config_mod.resume_text(config))
    print("Analyzing resume for matching roles...")
    for role in analyzer.suggest_roles():
        tag = "  [stretch]" if role.stretch else ""
        print(f"  * {role.title}{tag}\n      {role.why}")


def cmd_gui(args, config: dict) -> None:
    import threading

    import uvicorn

    from .server import app

    url = f"http://127.0.0.1:{args.port}"
    print(f"JobBot GUI: {url}  (Ctrl+C to stop)")
    if not args.no_open:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


def cmd_export(args, config: dict) -> None:
    from . import export as export_mod

    store = _open_store(config)
    jobs = store.all_jobs()
    out = config_mod.output_dir(config) / export_mod.timestamped(
        "jobbot_export", args.format
    )
    if args.format == "xlsx":
        export_mod.export_xlsx(jobs, out)
    else:
        export_mod.export_csv(jobs, out)
    print(f"Exported {len(jobs)} jobs -> {out}")
    store.close()


def cmd_stats(args, config: dict) -> None:
    store = _open_store(config)
    stats = store.stats()
    print(f"Jobs tracked:      {stats['total']}")
    print(f"Scored 70+:        {stats['high'] or 0}")
    print(f"In pipeline:       {stats['tracked'] or 0}")
    store.close()


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="jobbot", description="JobBot V2")
    parser.add_argument("--config", "-c", help="Path to config.yaml")
    sub = parser.add_subparsers(dest="command")

    p_search = sub.add_parser("search", help="Fetch, score, and build the dashboard")
    p_search.add_argument("--no-analyze", action="store_true",
                          help="Skip AI scoring")
    p_search.add_argument("--no-open", action="store_true",
                          help="Don't open the dashboard in a browser")

    p_dash = sub.add_parser("dashboard", help="Regenerate and open the dashboard")
    p_dash.add_argument("--no-open", action="store_true")

    p_list = sub.add_parser("list", help="List jobs in the terminal")
    p_list.add_argument("--min-score", type=int, default=0)
    p_list.add_argument("--limit", type=int, default=25)

    p_status = sub.add_parser("status", help="Update application status for a job")
    p_status.add_argument("job_id")
    p_status.add_argument("status", choices=STATUSES)
    p_status.add_argument("--notes")

    p_bullets = sub.add_parser("bullets", help="Generate tailored resume bullets")
    p_bullets.add_argument("job_id")

    p_cover = sub.add_parser("cover", help="Generate a tailored cover letter")
    p_cover.add_argument("job_id")

    sub.add_parser("stats", help="Show pipeline statistics")
    sub.add_parser("suggest", help="Suggest search titles from the resume")

    p_gui = sub.add_parser("gui", help="Launch the web GUI (default)")
    p_gui.add_argument("--port", type=int, default=8787)
    p_gui.add_argument("--no-open", action="store_true")

    p_export = sub.add_parser("export", help="Export jobs to a spreadsheet")
    p_export.add_argument("format", choices=["xlsx", "csv"], nargs="?",
                          default="xlsx")

    args = parser.parse_args(argv)
    config = config_mod.load_config(args.config)

    commands = {
        "search": cmd_search,
        "dashboard": cmd_dashboard,
        "list": cmd_list,
        "status": cmd_status,
        "bullets": cmd_bullets,
        "cover": cmd_cover,
        "stats": cmd_stats,
        "suggest": cmd_suggest,
        "gui": cmd_gui,
        "export": cmd_export,
    }
    handler = commands.get(args.command or "gui")
    if args.command is None:
        # bare `python main.py` launches the GUI
        args.port = 8787
        args.no_open = False
    handler(args, config)
