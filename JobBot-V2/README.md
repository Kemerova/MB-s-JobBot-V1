# JobBot V2

Job search automation, rebuilt for 2026. Fetches live job postings via
[JobSpy](https://github.com/speedyapply/JobSpy) (a maintained scraper library
covering Indeed, LinkedIn, Glassdoor, Google Jobs, and ZipRecruiter), scores
each job against your resume with Claude, and tracks your application pipeline
in a local SQLite database with a static HTML dashboard.

## What changed from V1

| | V1 | V2 |
|---|---|---|
| Job data | Homegrown HTML scrapers (rotted/blocked) | JobSpy library (community-maintained) + optional JSearch API |
| AI | CrewAI + LangChain + gpt-3.5-turbo | Direct Anthropic SDK: Haiku 4.5 scoring, Opus 4.8 bullets |
| Storage | Scattered JSON files | Single SQLite database with dedupe across runs |
| Dashboard | FastAPI server + static server hybrid | Single self-contained HTML file, no server |
| Code size | ~9,000 lines | ~1,100 lines |

## Setup

```powershell
cd JobBot-V2
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

API keys (create a `.env` file in this folder, or set environment variables):

```
ANTHROPIC_API_KEY=sk-ant-...    # required for AI scoring/bullets
RAPIDAPI_KEY=...                # optional: enables the JSearch source
```

Without an Anthropic key the bot still runs, using keyword-based scoring.

Edit `config.yaml` for your search terms, location, salary floor, and which
job boards to hit. Put your current resume at `resume/base_resume.txt`
(gitignored — your resume and job data never leave your machine).

## Usage — GUI (primary)

Double-click **`JobBot.bat`**, or run:

```powershell
.venv\Scripts\python main.py        # launches the GUI at http://127.0.0.1:8787
```

Everything happens in the browser:

- **Run Search** — fetches and scores jobs with a live progress bar and a
  Stop button to abort mid-run (partial results are kept)
- **Jobs tab** — stat tiles, pipeline chips (clickable status counts),
  filters (search / score / location / remote), score rings, NEW badges on
  fresh postings, follow-up nudges on stale applications, quick-hide ✕
- **Per-job AI** — one-click tailored resume bullets and full cover letters
  (Opus), shown in a copyable modal and saved with the job
- **Settings tab** — job titles, location + search radius, salary floor, job
  boards, posting age, exclusion keywords, AI toggle (saved to config.yaml)
- **Resume tab** — edit the resume Claude scores against, right in the app
- **Excel / CSV** buttons — download a formatted spreadsheet of everything

Hourly salaries are annualized (×2080) before the minimum-salary filter is
applied, so a "$45/hr" posting correctly counts as ≈$93k.

## Usage — CLI (optional / scripting)

```powershell
.venv\Scripts\python main.py search          # headless fetch + score
.venv\Scripts\python main.py list --min-score 70
.venv\Scripts\python main.py status <id> applied --notes "Applied via site"
.venv\Scripts\python main.py bullets <id>    # Opus-tailored resume bullets
.venv\Scripts\python main.py export xlsx     # or csv
.venv\Scripts\python main.py stats
```

Statuses: `new, interested, applied, phone_screen, interviewing, offer,
accepted, rejected, hidden` (hidden removes a job from view).

## Costs

Scoring uses `claude-haiku-4-5` (~$0.001 per job — a 100-job run costs about
a dime). Resume bullets use `claude-opus-4-8` on demand (~$0.05 per job).
Job data via JobSpy is free.

## Notes

- Jobs are deduplicated by (title, company, location) across runs; re-running
  `search` only scores newly discovered jobs.
- LinkedIn rate-limits aggressively; Indeed is the most reliable JobSpy source.
  If LinkedIn returns nothing, remove it from `search.sites` in config.yaml.
- The dashboard (`output/dashboard.html`) is fully self-contained — open it on
  any device, no server needed.
