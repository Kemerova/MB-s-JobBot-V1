"""Claude-powered job analysis: bulk scoring (Haiku) and tailored resume
bullets (Opus). Falls back to keyword scoring when no API key is available."""

from __future__ import annotations

import logging
import re

import anthropic
from pydantic import BaseModel, Field

log = logging.getLogger("jobbot.analyzer")


class JobScore(BaseModel):
    score: int = Field(description="Overall match score, 0-100")
    fit_summary: str = Field(description="One-sentence verdict on the match")
    strengths: list[str] = Field(description="Top 2-4 reasons this job fits the resume")
    gaps: list[str] = Field(description="Top 1-3 requirements the resume doesn't show")


class ResumeBullets(BaseModel):
    bullets: list[str] = Field(
        description="4-6 resume bullet points tailored to this job posting"
    )


class SuggestedRole(BaseModel):
    title: str = Field(
        description="A job title as commonly written on job boards, suitable "
        "as a search query (e.g. 'Cloud Engineer', not 'Cloud Wizard III')"
    )
    why: str = Field(description="One sentence: why this candidate qualifies")
    stretch: bool = Field(
        description="True if this is a growth/stretch role rather than a "
        "role the candidate is fully qualified for today"
    )


class RoleSuggestions(BaseModel):
    roles: list[SuggestedRole] = Field(
        description="8-12 roles, strongest matches first, stretch roles last"
    )


SCORING_SYSTEM = """You score job postings against a candidate's resume.

Scoring rubric (0-100):
- Role fit: does the candidate's experience match the responsibilities? (35)
- Requirements match: skills/tools/certifications overlap (30)
- Seniority alignment: not too junior, not unreachably senior (15)
- Location/logistics: matches the candidate's location or remote preference (10)
- Compensation: salary (if listed) meets or beats the candidate's floor (10)

Be honest and discriminating — most jobs should land between 40 and 75.
Reserve 80+ for genuinely strong matches.

CANDIDATE RESUME:
{resume}
"""

BULLETS_SYSTEM = """You write resume bullet points tailored to a specific job
posting, grounded strictly in the candidate's actual experience. Never invent
experience the resume doesn't support. Use strong action verbs, mirror the
posting's key terminology where the resume genuinely backs it up, and include
concrete metrics from the resume when available.

CANDIDATE RESUME:
{resume}
"""

SUGGEST_SYSTEM = """You are a career strategist. Given a resume, produce a
list of job titles the candidate should actually search for on job boards.

Rules:
- Titles must be phrased the way employers post them (searchable keywords),
  not creative or internal titles.
- Strong matches first: roles the candidate could start tomorrow based on
  demonstrated experience, certifications, and clearances.
- Then 2-3 stretch roles: a realistic next step up, marked as stretch.
- Consider the whole resume: certifications, clearances, tooling, industries,
  and seniority level. Don't suggest roles that need years of experience the
  resume doesn't show.
- Prefer distinct role families over near-duplicate phrasings.
"""

COVER_SYSTEM = """You write concise, professional cover letters grounded
strictly in the candidate's actual resume. Rules:
- Under 300 words, three to four short paragraphs.
- Open with genuine specificity about the role/company, never "I am writing to
  express my interest".
- Connect 2-3 of the candidate's strongest relevant achievements to the
  posting's needs. Never invent experience the resume doesn't support.
- Confident, warm, direct tone. No clichés ("team player", "fast-paced
  environment"), no flattery padding.
- Close with a simple call to action. Sign off as the candidate's name from
  the resume.

CANDIDATE RESUME:
{resume}
"""

FALLBACK_KEYWORDS = {
    "cloud": 8, "aws": 8, "azure": 8, "devops": 8, "kubernetes": 6, "docker": 6,
    "python": 6, "terraform": 6, "ci/cd": 5, "linux": 5, "security": 5,
    "automation": 5, "engineer": 4, "infrastructure": 4, "senior": 3,
}


def _job_prompt(job: dict, max_chars: int) -> str:
    description = (job.get("description") or "(no description provided)")[:max_chars]
    salary = ""
    if job.get("salary_min") or job.get("salary_max"):
        salary = f"Salary: {job.get('salary_min')} - {job.get('salary_max')}\n"
    return (
        f"Title: {job.get('title')}\n"
        f"Company: {job.get('company')}\n"
        f"Location: {job.get('location')} "
        f"({'remote OK' if job.get('is_remote') else 'on-site/unknown'})\n"
        f"{salary}"
        f"Description:\n{description}"
    )


class Analyzer:
    def __init__(self, config: dict, resume: str):
        self.config = config["analysis"]
        self.resume = resume
        self.client = None
        try:
            client = anthropic.Anthropic()
            # cheap auth sanity check happens lazily on first call
            self.client = client
        except Exception as exc:
            log.warning("Anthropic client unavailable (%s); using keyword scoring", exc)

    def score_job(self, job: dict) -> JobScore:
        if self.client is None or not self.config["enabled"]:
            return self._keyword_score(job)
        try:
            response = self.client.messages.parse(
                model=self.config["score_model"],
                max_tokens=1024,
                system=SCORING_SYSTEM.format(resume=self.resume),
                messages=[
                    {
                        "role": "user",
                        "content": "Score this job posting against the resume:\n\n"
                        + _job_prompt(job, self.config["max_description_chars"]),
                    }
                ],
                output_format=JobScore,
            )
            result = response.parsed_output
            if result is None:
                raise ValueError("model returned unparseable output")
            result.score = max(0, min(100, result.score))
            return result
        except anthropic.AuthenticationError:
            log.warning("Invalid ANTHROPIC_API_KEY; falling back to keyword scoring")
            self.client = None
            return self._keyword_score(job)
        except Exception as exc:
            log.warning("Scoring failed for %s: %s", job.get("title"), exc)
            return self._keyword_score(job)

    def _keyword_score(self, job: dict) -> JobScore:
        text = f"{job.get('title', '')} {job.get('description', '')}".lower()
        score = 25
        hits = []
        for keyword, points in FALLBACK_KEYWORDS.items():
            if re.search(re.escape(keyword), text):
                score += points
                hits.append(keyword)
        return JobScore(
            score=min(score, 90),
            fit_summary="Keyword-based estimate (no AI scoring available).",
            strengths=[f"Keyword match: {k}" for k in hits[:4]],
            gaps=[],
        )

    def generate_bullets(self, job: dict) -> list[str]:
        if self.client is None:
            raise RuntimeError(
                "Resume bullets require a valid ANTHROPIC_API_KEY in .env or the "
                "environment."
            )
        response = self.client.messages.parse(
            model=self.config["bullets_model"],
            max_tokens=2048,
            system=BULLETS_SYSTEM.format(resume=self.resume),
            messages=[
                {
                    "role": "user",
                    "content": "Write tailored resume bullets for this job:\n\n"
                    + _job_prompt(job, self.config["max_description_chars"]),
                }
            ],
            output_format=ResumeBullets,
        )
        result = response.parsed_output
        if result is None:
            raise ValueError("model returned unparseable output")
        return result.bullets

    def suggest_roles(self) -> list[SuggestedRole]:
        if self.client is None:
            raise RuntimeError(
                "Role suggestions require a valid ANTHROPIC_API_KEY in .env or "
                "the environment."
            )
        if not self.resume.strip():
            raise RuntimeError("Resume is empty — add it in the Resume tab first.")
        response = self.client.messages.parse(
            model=self.config["bullets_model"],
            max_tokens=2048,
            system=SUGGEST_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": "Suggest job-board search titles for this "
                    "candidate:\n\n" + self.resume,
                }
            ],
            output_format=RoleSuggestions,
        )
        result = response.parsed_output
        if result is None or not result.roles:
            raise ValueError("model returned no suggestions")
        return result.roles

    def generate_cover_letter(self, job: dict) -> str:
        if self.client is None:
            raise RuntimeError(
                "Cover letters require a valid ANTHROPIC_API_KEY in .env or the "
                "environment."
            )
        response = self.client.messages.create(
            model=self.config["bullets_model"],
            max_tokens=2048,
            system=COVER_SYSTEM.format(resume=self.resume),
            messages=[
                {
                    "role": "user",
                    "content": "Write a cover letter for this job:\n\n"
                    + _job_prompt(job, self.config["max_description_chars"]),
                }
            ],
        )
        text = "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
        if not text:
            raise ValueError("model returned no text")
        return text
