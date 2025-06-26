# V1/utils.py
"""
Utility functions for the job hunting system
"""

import os
import sys
import time
import hashlib
import logging
from functools import wraps
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from .models import Job


def cache_result(ttl_seconds: int = 3600):
    """Decorator to cache function results"""
    cache = {}
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = hashlib.md5(f"{func.__name__}{str(args)}{str(kwargs)}".encode()).hexdigest()
            
            if key in cache:
                result, timestamp = cache[key]
                if time.time() - timestamp < ttl_seconds:
                    return result
            
            result = func(*args, **kwargs)
            cache[key] = (result, time.time())
            return result
        
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator to retry function on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(delay * (2 ** attempt))
                        logging.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                    
            logging.error(f"All {max_retries} attempts failed for {func.__name__}: {last_exception}")
            raise last_exception
        
        return wrapper
    return decorator


def setup_logging(level: str, output_dir: str):
    """Setup logging with Windows-compatible formatting"""
    log_dir = Path(output_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    class NoEmojiFormatter(logging.Formatter):
        def format(self, record):
            if hasattr(record, 'msg'):
                emoji_replacements = {
                    '🚀': '[START]', '📡': '[SEARCH]', '🔄': '[PROCESS]',
                    '📊': '[DATA]', '🤖': '[AI]', '✅': '[OK]', '❌': '[ERROR]',
                    '⚠️': '[WARN]', '📄': '[REPORT]', '💾': '[SAVE]',
                    '🔥': '[TOP]', '📈': '[STATS]'
                }
                
                msg_str = str(record.msg)
                for emoji, replacement in emoji_replacements.items():
                    msg_str = msg_str.replace(emoji, replacement)
                record.msg = msg_str
            
            return super().format(record)
    
    # File handler
    file_handler = logging.FileHandler(
        log_dir / f"job_hunt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", 
        encoding='utf-8'
    )
    file_handler.setFormatter(NoEmojiFormatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # Console handler  
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(NoEmojiFormatter('%(levelname)s - %(message)s'))
    
    # Root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=[file_handler, console_handler],
        force=True
    )


def make_unique(jobs: List[Job]) -> List[Job]:
    """Remove duplicate jobs"""
    unique_jobs = []
    selectable: List[str] = []
    seen = set()
    
    for job in jobs:
        key = job.make_unique_key()
        if key not in seen:
            unique_jobs.append(job)
            seen.add(key)
    
    return unique_jobs


def filter_stale_jobs(jobs: List[Job], max_age_days: int = 30) -> List[Job]:
    """Filter out stale job postings"""
    cutoff_date = datetime.now() - timedelta(days=max_age_days)
    return [job for job in jobs if job.scraped_at >= cutoff_date]


def extract_salary_range(salary_text: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract min and max salary from text"""
    if not salary_text:
        return None, None
    
    import re
    
    # Remove common prefixes
    salary_clean = re.sub(r'(up to|starting at|from|salary:)', '', salary_text.lower())
    
    # Find numbers (with k, thousand, etc.)
    numbers = re.findall(r'[\$]?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:k|thousand|K)?', salary_clean)
    
    if not numbers:
        return None, None
    
    # Convert to integers
    converted = []
    for num in numbers:
        num_clean = num.replace(',', '')
        try:
            value = float(num_clean)
            # If it's less than 1000, assume it's in thousands
            if value < 1000:
                value *= 1000
            converted.append(int(value))
        except ValueError:
            continue
    
    if not converted:
        return None, None
    
    return min(converted), max(converted) if len(converted) > 1 else None


def validate_environment():
    """Validate required environment variables and dependencies"""
    errors = []
    
    # Check for OpenAI API key
    if not os.getenv('OPENAI_API_KEY'):
        errors.append("OPENAI_API_KEY environment variable not set. Please check your .env file.")
    
    # Check for required directories
    required_dirs = ['output', 'resume']
    for dir_name in required_dirs:
        if not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name)
                print(f"Created directory: {dir_name}")
            except Exception as e:
                errors.append(f"Could not create directory {dir_name}: {e}")
    
    return errors


def create_sample_files():
    """Create sample resume and config files"""
    # Sample resume
    resume_dir = Path("resume")
    resume_dir.mkdir(exist_ok=True)
    
    sample_resume = """[Your Name]
[Your Title]

Professional software engineer with 5+ years experience in cloud technologies and full-stack development.

TECHNICAL SKILLS:
• Programming: Python, JavaScript, Java, SQL
• Cloud: AWS, Azure, Google Cloud Platform
• Frameworks: React, Node.js, Django, Spring Boot
• Tools: Docker, Kubernetes, Git, Jenkins

EXPERIENCE:
Software Engineer | Tech Company (2020-Present)
• Developed scalable web applications serving 100k+ users
• Implemented CI/CD pipelines reducing deployment time by 50%
• Collaborated with cross-functional teams on product features

EDUCATION:
Bachelor of Science in Computer Science
University Name, 2020
"""
    
    with open(resume_dir / "base_resume.txt", "w", encoding="utf-8") as f:
        f.write(sample_resume)
    
    # Sample config (if not exists)
    if not os.path.exists("config.yaml"):
        from .config import ConfigManager
        config_manager = ConfigManager()
        config_manager.create_default_config()

def compute_semantic_similarity(resume: str, job_text: str) -> float:
    """Return a 0–1 semantic similarity estimate via SequenceMatcher"""
    if not resume or not job_text:
        return 0.0
    return SequenceMatcher(None, resume, job_text).ratio()

def compute_title_score(title: str, target_titles: list) -> float:
    """Return a 0–1 score based on best fuzzy match against target titles"""
    title = title or ""
    ratios = [SequenceMatcher(None, title.lower(), tt.lower()).ratio() for tt in target_titles]
    return max(ratios) if ratios else 0.0

def compute_location_score(job_location: str, primary: list, targets: list, allow_remote: bool) -> float:
    """1.0 if direct match to preferred locations, 0.8 for remote if allowed, else 0"""
    loc = (job_location or "").lower()
    for p in primary + targets:
        if p.lower() in loc:
            return 1.0
    if allow_remote and 'remote' in loc:
        return 0.8
    return 0.0

def compute_job_score(job, resume_text: str, config) -> tuple:
    """
    Compute a weighted score for a job based on resume similarity, title match, location, and exclude penalties.
    Returns (score_fraction, breakdown_dict).
    """
    # Extract texts
    job_text = ' '.join(filter(None, [job.title, job.description or '']))
    # Subscores
    sem = compute_semantic_similarity(resume_text, job_text)
    title_sc = compute_title_score(job.title, config.jobs.target_titles)
    loc_sc = compute_location_score(job.location, config.location.primary_locations, config.location.target_locations, config.jobs.allow_remote)
    exclude = 1.0 if any(kw.lower() in job_text.lower() for kw in config.jobs.exclude_keywords) else 0.0
    # Weights
    w_sem, w_loc, w_title, w_excl = 0.5, 0.2, 0.2, 0.1
    # Combine (subtract exclude weight)
    raw = sem * w_sem + loc_sc * w_loc + title_sc * w_title - exclude * w_excl
    score = max(min(raw, 1.0), 0.0)
    breakdown = {
        'semantic': round(sem, 2),
        'title': round(title_sc, 2),
        'location': round(loc_sc, 2),
        'exclude_penalty': int(exclude)
    }
    return score, breakdown