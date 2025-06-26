# V1/finder.py - Cleaned Job Finder, ManualJobProvider Removed
"""
Job finding module with updated scrapers and proper error handling.
ManualJobProvider has been removed as requested.
"""
import requests
import time
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Type
from urllib.parse import urljoin, quote_plus
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
import json
import re
import os

from .models import Job, JobSource
from .config import AppConfig, JobBoardConfig, JobBoardType
from .utils import retry_on_failure, extract_salary_range, compute_job_score

class RateLimitedSession:
    """HTTP session with built-in rate limiting and retry logic"""
    def __init__(self, config: AppConfig):
        self.config = config.scraping
        self.session = requests.Session()
        # Setup retry strategy
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        self.last_request_time = {}

    def _rate_limit(self, domain: str, delay: float = None):
        """Enforce rate limiting per domain with custom delay"""
        if delay is None:
            delay = self.config.base_delay
        if domain in self.last_request_time:
            elapsed = time.time() - self.last_request_time[domain]
            if elapsed < delay:
                sleep_time = delay - elapsed
                time.sleep(sleep_time)
        self.last_request_time[domain] = time.time()

    def get(self, url: str, delay: float = None, **kwargs) -> Optional[requests.Response]:
        """Rate-limited GET request with enhanced retry logic and timeouts"""
        domain = url.split('/')[2] if len(url.split('/')) > 2 else url
        self._rate_limit(domain, delay)
        
        max_retries = getattr(self.config, 'max_retries', 3)
        base_delay = 1
        
        for attempt in range(max_retries):
            try:
                headers = kwargs.pop('headers', {})
                headers.update({
                    'User-Agent': random.choice(self.user_agents),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Cache-Control': 'max-age=0'
                })
                
                # Enhanced timeout configuration
                timeout = kwargs.pop('timeout', (10, 30))  # (connect, read)
                
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=timeout,
                    **kwargs
                )
                
                # Handle rate limiting with exponential backoff
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        retry_delay = int(retry_after)
                    else:
                        retry_delay = base_delay * (2 ** attempt)
                    
                    logging.warning(f"Rate limited by {domain}, waiting {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                
                # Handle temporary server errors
                elif response.status_code in [500, 502, 503, 504]:
                    if attempt < max_retries - 1:
                        retry_delay = base_delay * (2 ** attempt)
                        logging.warning(f"Server error {response.status_code} from {domain}, retrying in {retry_delay}s")
                        time.sleep(retry_delay)
                        continue
                
                # Success or other non-retryable status codes
                response.raise_for_status()
                return response
                
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < max_retries - 1:
                    retry_delay = base_delay * (2 ** attempt)
                    logging.warning(f"Network error for {domain}: {e}, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                else:
                    logging.error(f"Final network error for {url} after {max_retries} attempts: {e}")
                    return None
            
            except requests.exceptions.RequestException as e:
                logging.warning(f"Request error for {url} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    retry_delay = base_delay * (2 ** attempt)
                    time.sleep(retry_delay)
                    continue
                else:
                    return None
            
            except Exception as e:
                logging.debug(f"Unexpected error for {url}: {e}")
                return None
        
        return None

class BaseScraper:
    """Enhanced base class for job board scrapers"""
    def __init__(self, config: AppConfig, board_config: JobBoardConfig, session: RateLimitedSession):
        self.config = config
        self.board_config = board_config
        self.session = session
        self.source = getattr(JobSource, board_config.name.upper(), JobSource.MANUAL)

    def is_job_relevant(self, job: Job) -> bool:
        """Enhanced job relevance checking"""
        if not job.title or not job.company:
            return False
        # Title matching
        title_lower = job.title.lower()
        title_match = any(target.lower() in title_lower for target in self.config.jobs.target_titles)
        # Location matching
        location_lower = job.location.lower()
        location_match = (
            any(loc.lower() in location_lower for loc in self.config.location.primary_locations) or
            any(loc.lower() in location_lower for loc in self.config.location.target_locations) or
            'remote' in location_lower
        )
        # Exclude keywords check
        exclude_text = f"{job.title} {job.description or ''}".lower()
        has_exclude_keywords = any(keyword.lower() in exclude_text for keyword in self.config.jobs.exclude_keywords)
        return title_match and location_match and not has_exclude_keywords

    def extract_job_from_card(self, card) -> Optional[Job]:
        """Extract job data from HTML card - implement in subclasses"""
        raise NotImplementedError

    def search_jobs(self, keywords: str, location: str, pages: int = None) -> List[Job]:
        """Search for jobs - implement in subclasses"""
        raise NotImplementedError

class LinkedInScraper(BaseScraper):
    """LinkedIn scraper - parses LinkedIn's HTML job cards correctly"""
    def __init__(self, config: AppConfig, board_config: JobBoardConfig, session: RateLimitedSession):
        super().__init__(config, board_config, session)
        self.base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        self.source = JobSource.LINKEDIN

    def extract_job_from_card(self, card) -> Optional[Job]:
        try:
            # LinkedIn's job cards (as of 2024) use these selectors
            title_elem = card.select_one('h3.base-search-card__title')
            company_elem = card.select_one('h4.base-search-card__subtitle')
            location_elem = card.select_one('span.job-search-card__location')
            link_elem = card.select_one('a.base-card__full-link')

            title = title_elem.get_text(strip=True) if title_elem else None
            company = company_elem.get_text(strip=True) if company_elem else None
            location = location_elem.get_text(strip=True) if location_elem else None
            job_url = link_elem['href'] if link_elem and link_elem.get('href') else None

            job = Job(
                title=title,
                company=company,
                location=location,
                url=job_url,
                source=self.source,
                scraped_at=datetime.now(),
                remote_friendly='remote' in (location or '').lower()
            )
            return job if self.is_job_relevant(job) else None
        except Exception as e:
            logging.debug(f"Error parsing LinkedIn job card: {e}")
            return None

    def search_jobs(self, keywords: str, location: str, pages: int = None) -> List[Job]:
        if pages is None:
            pages = self.board_config.pages_per_search
        jobs = []
        for page in range(pages):
            try:
                params = {
                    "keywords": keywords,
                    "location": location,
                    "start": page * 25,
                }
                response = self.session.get(self.base_url, params=params, delay=self.board_config.rate_limit_delay)
                if not response or response.status_code != 200:
                    logging.warning(f"LinkedIn: returned status {response.status_code if response else 'None'}")
                    continue
                soup = BeautifulSoup(response.content, "html.parser")
                job_cards = soup.find_all('div', class_=lambda x: x and 'base-search-card' in x)
                if not job_cards:
                    logging.warning(f"LinkedIn: No job cards found on page {page + 1}")
                    print(response.text[:500])  # Debug: print first 500 chars
                    continue
                for card in job_cards:
                    job = self.extract_job_from_card(card)
                    if job:
                        job.search_keywords = keywords
                        jobs.append(job)
            except Exception as e:
                logging.error(f"LinkedIn search failed for page {page + 1}: {e}")
                continue
        return jobs

class DiceScraper(BaseScraper):
    """Updated Dice scraper for 2025"""
    def __init__(self, config: AppConfig, board_config: JobBoardConfig, session: RateLimitedSession):
        super().__init__(config, board_config, session)
        self.base_url = "https://www.dice.com/jobs"
        self.source = JobSource.DICE

    def extract_job_from_card(self, card) -> Optional[Job]:
        """Extract Dice job data"""
        try:
            title_selectors = [
                'a[data-cy="card-title-link"]',
                'h5[data-cy="card-title"] a',
                '.card-title-link',
                'h5 a'
            ]
            title_elem = None
            for selector in title_selectors:
                title_elem = card.select_one(selector)
                if title_elem:
                    break
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)
            if not title or not re.search(r'\w', title):  # Ensure title is not empty
                return None

            company_selectors = [
                'a[data-cy="card-company"]',
                'span[data-cy="card-company"]',
                '.card-company'
            ]
            company_elem = None
            for selector in company_selectors:
                company_elem = card.select_one(selector)
                if company_elem:
                    break
            company = company_elem.get_text(strip=True) if company_elem else 'Dice Company'

            location_selectors = [
                'span[data-cy="card-location"]',
                '.card-location',
                'li[data-cy="card-location"]'
            ]
            location_elem = None
            for selector in location_selectors:
                location_elem = card.select_one(selector)
                if location_elem:
                    break
            location = location_elem.get_text(strip=True) if location_elem else 'Various'

            salary_selectors = [
                'span[data-cy="card-salary"]',
                '.card-salary',
                'li[data-cy="card-salary"]'
            ]
            salary = None
            for selector in salary_selectors:
                salary_elem = card.select_one(selector)
                if salary_elem:
                    salary_text = salary_elem.get_text(strip=True)
                    if '$' in salary_text or 'hour' in salary_text.lower():
                        salary = salary_text
                        break

            job_url = None
            if title_elem and title_elem.name == 'a' and title_elem.get('href'):
                job_url = urljoin("https://www.dice.com", title_elem['href'])

            salary_min, salary_max = extract_salary_range(salary) if salary else (None, None)

            job = Job(
                title=title,
                company=company,
                location=location,
                salary=salary,
                salary_min=salary_min,
                salary_max=salary_max,
                source=self.source,
                url=job_url,
                remote_friendly='remote' in location.lower(),
                scraped_at=datetime.now()
            )
            return job if self.is_job_relevant(job) else None
        except Exception as e:
            logging.debug(f"Error parsing Dice job card: {e}")
            return None

    def search_jobs(self, keywords: str, location: str, pages: int = None) -> List[Job]:
        """Search Dice jobs"""
        if pages is None:
            pages = self.board_config.pages_per_search
        jobs = []
        for page in range(pages):
            try:
                params = {
                    'keywords': keywords,
                    'location': location,
                    'start': page * 25,
                }
                response = self.session.get(self.base_url, params=params, delay=self.board_config.rate_limit_delay)
                if not response or response.status_code != 200:
                    logging.warning(f"Dice returned status {response.status_code if response else 'None'}")
                    continue
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = (
                    soup.find_all('dhi-search-card') or
                    soup.find_all('div', attrs={'data-cy': 'card'}) or
                    soup.find_all('div', class_='search-card')
                )
                if not job_cards:
                    logging.warning(f"Dice: No job cards found on page {page + 1}")
                    continue
                for card in job_cards:
                    job = self.extract_job_from_card(card)
                    if job:
                        job.search_keywords = keywords
                        jobs.append(job)
            except Exception as e:
                logging.error(f"Dice search failed for page {page + 1}: {e}")
                continue
        return jobs

class IndeedScraper(BaseScraper):
    """Updated Indeed scraper for 2025"""
    def __init__(self, config: AppConfig, board_config: JobBoardConfig, session: RateLimitedSession):
        super().__init__(config, board_config, session)
        self.base_url = "https://www.indeed.com/jobs"
        self.source = JobSource.INDEED

    def extract_job_from_card(self, card) -> Optional[Job]:
        """Extract Indeed job data with updated selectors"""
        try:
            title_selectors = [
                'h2 a span[title]',
                '.jobTitle a span',
                '[data-testid="job-title"] span',
                'h2 span'
            ]
            title_elem = None
            for selector in title_selectors:
                title_elem = card.select_one(selector)
                if title_elem:
                    break
            if not title_elem:
                return None
            title = title_elem.get('title') or title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                return None

            company_selectors = [
                '[data-testid="company-name"]',
                '.companyName a',
                '.companyName span',
                'span.companyName'
            ]
            company_elem = None
            for selector in company_selectors:
                company_elem = card.select_one(selector)
                if company_elem:
                    break
            company = company_elem.get_text(strip=True) if company_elem else 'Indeed Company'

            location_selectors = [
                '[data-testid="job-location"]',
                '.companyLocation',
                '[data-testid="text-location"]'
            ]
            location_elem = None
            for selector in location_selectors:
                location_elem = card.select_one(selector)
                if location_elem:
                    break
            location = location_elem.get_text(strip=True) if location_elem else 'Various'

            salary_selectors = [
                '[data-testid="attribute_snippet_testid"]',
                '.salary-snippet-container',
                '.attribute_snippet'
            ]
            salary = None
            for selector in salary_selectors:
                salary_elem = card.select_one(selector)
                if salary_elem:
                    salary_text = salary_elem.get_text(strip=True)
                    if '$' in salary_text:
                        salary = salary_text
                        break

            job_url = None
            link_elem = card.select_one('h2 a, .jobTitle a')
            if link_elem and link_elem.get('href'):
                job_url = urljoin("https://www.indeed.com", link_elem['href'])

            salary_min, salary_max = extract_salary_range(salary) if salary else (None, None)
            job = Job(
                title=title,
                company=company,
                location=location,
                salary=salary,
                salary_min=salary_min,
                salary_max=salary_max,
                source=self.source,
                url=job_url,
                remote_friendly='remote' in location.lower(),
                scraped_at=datetime.now()
            )
            return job if self.is_job_relevant(job) else None
        except Exception as e:
            logging.debug(f"Error parsing Dice card: {e}")
            return None

    def search_jobs(self, keywords: str, location: str, pages: int = None) -> List[Job]:
        """Search Dice jobs"""
        if pages is None:
            pages = self.board_config.pages_per_search
        jobs = []
        for page in range(1, pages + 1):
            try:
                if page > 1:
                    time.sleep(self.board_config.rate_limit_delay)
                params = {
                    'q': keywords,
                    'location': location,
                    'page': page,
                    'pageSize': 20,
                    'sort': 'date'
                }
                response = self.session.get(self.base_url, params=params, delay=self.board_config.rate_limit_delay)
                if not response or response.status_code != 200:
                    logging.warning(f"Dice returned status {response.status_code if response else 'None'}")
                    continue
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = (
                    soup.find_all('dhi-search-card') or
                    soup.find_all('div', attrs={'data-cy': 'card'}) or
                    soup.find_all('div', class_='search-card')
                )
                if not job_cards:
                    logging.warning(f"Dice: No job cards found on page {page}")
                    break
                page_jobs = []
                for card in job_cards:
                    job = self.extract_job_from_card(card)
                    if job:
                        job.search_keywords = keywords
                        page_jobs.append(job)
                jobs.extend(page_jobs)
                logging.info(f"Dice: Found {len(page_jobs)} relevant jobs on page {page}")
                if len(page_jobs) == 0:
                    break
            except Exception as e:
                logging.error(f"Dice search failed for page {page}: {e}")
                continue
        return jobs

class ClearanceJobsScraper(BaseScraper):
    """Updated ClearanceJobs scraper for 2025"""
    def __init__(self, config: AppConfig, board_config: JobBoardConfig, session: RateLimitedSession):
        super().__init__(config, board_config, session)
        self.base_url = "https://www.clearancejobs.com/jobs"
        self.source = JobSource.CLEARANCEJOBS

    def extract_job_from_card(self, card) -> Optional[Job]:
        """Extract ClearanceJobs job data"""
        try:
            title_selectors = [
                'h3 a',
                'h4 a',
                '.title a',
                'a[href*="/jobs/"]'
            ]
            title_elem = None
            for selector in title_selectors:
                title_elem = card.select_one(selector)
                if title_elem:
                    break
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                return None

            company_selectors = [
                '.company-name',
                'span[class*="company"]',
                'div[class*="company"]'
            ]
            company_elem = None
            for selector in company_selectors:
                company_elem = card.select_one(selector)
                if company_elem:
                    break
            company = company_elem.get_text(strip=True) if company_elem else 'ClearanceJobs Company'

            location_selectors = [
                '.location',
                'span[class*="location"]',
                'div[class*="location"]'
            ]
            location_elem = None
            for selector in location_selectors:
                location_elem = card.select_one(selector)
                if location_elem:
                    break
            location = location_elem.get_text(strip=True) if location_elem else 'Various'

            clearance_text = card.get_text()
            clearance = None
            if 'Secret' in clearance_text:
                if 'Top Secret' in clearance_text or 'TS' in clearance_text:
                    if 'SCI' in clearance_text:
                        clearance = 'TS/SCI'
                    else:
                        clearance = 'Top Secret'
                else:
                    clearance = 'Secret'

            job_url = None
            if title_elem and title_elem.get('href'):
                job_url = urljoin("https://www.clearancejobs.com", title_elem['href'])

            job = Job(
                title=title,
                company=company,
                location=location,
                clearance_required=clearance,
                source=self.source,
                url=job_url,
                remote_friendly='remote' in location.lower(),
                scraped_at=datetime.now()
            )
            return job if self.is_job_relevant(job) else None
        except Exception as e:
            logging.debug(f"Error parsing ClearanceJobs card: {e}")
            return None

    def search_jobs(self, keywords: str, location: str, pages: int = None) -> List[Job]:
        """Search ClearanceJobs"""
        if pages is None:
            pages = self.board_config.pages_per_search
        jobs = []
        for page in range(1, pages + 1):
            try:
                if page > 1:
                    time.sleep(self.board_config.rate_limit_delay)
                params = {
                    'keywords': keywords,
                    'location': location,
                    'page': page,
                    'radius': 50
                }
                response = self.session.get(self.base_url, params=params, delay=self.board_config.rate_limit_delay)
                if not response:
                    continue
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = (
                    soup.find_all('div', class_=lambda x: x and 'job' in x.lower()) or
                    soup.find_all('article', class_=lambda x: x and 'job' in x.lower()) or
                    soup.find_all('div', class_='search-result')
                )
                if not job_cards:
                    logging.warning(f"ClearanceJobs: No job cards found on page {page}")
                    break
                page_jobs = []
                for card in job_cards:
                    job = self.extract_job_from_card(card)
                    if job:
                        job.search_keywords = keywords
                        page_jobs.append(job)
                jobs.extend(page_jobs)
                logging.info(f"ClearanceJobs: Found {len(page_jobs)} relevant jobs on page {page}")
                if len(page_jobs) == 0:
                    break
            except Exception as e:
                logging.error(f"ClearanceJobs search failed for page {page}: {e}")
                continue
        return jobs

class USAJobsScraper(BaseScraper):
    """Scraper for USAJobs API"""
    def __init__(self, config: AppConfig, board_config: JobBoardConfig, session: RateLimitedSession):
        super().__init__(config, board_config, session)
        self.base_url = "https://data.usajobs.gov/api/search"
        self.api_key = os.getenv('USAJOBS_API_KEY')
        self.source = JobSource.USAJOBS

    def search_jobs(self, keywords: str, location: str, pages: int = None) -> List[Job]:
        if not self.api_key:
            logging.error("USAJobs API key not set in USAJOBS_API_KEY")
            return []
        headers = {
            'User-Agent': random.choice(self.session.user_agents),
            'Authorization-Key': self.api_key,
            'Accept': 'application/json'
        }
        jobs = []
        for page in range(1, (pages or self.board_config.pages_per_search) + 1):
            params = {'Keyword': keywords, 'LocationName': location, 'Page': page}
            response = self.session.get(self.base_url, headers=headers, params=params, delay=self.board_config.rate_limit_delay)
            if not response:
                continue
            data = response.json().get('SearchResult', {})
            items = data.get('SearchResultItems', [])
            for item in items:
                desc = item.get('MatchedObjectDescriptor', {})
                job = Job(
                    title=desc.get('PositionTitle'),
                    company=desc.get('OrganizationName'),
                    location=desc.get('PositionLocationDisplay', ''),
                    url=(desc.get('ApplyURI') or [None])[0],
                    source=self.source,
                    scraped_at=datetime.now(),
                    remote_friendly='remote' in desc.get('PositionLocationDisplay', '').lower()
                )
                if self.is_job_relevant(job):
                    jobs.append(job)
            time.sleep(self.board_config.rate_limit_delay)
        return jobs

class AdzunaScraper(BaseScraper):
    """Scraper for Adzuna Jobs API"""
    def __init__(self, config: AppConfig, board_config: JobBoardConfig, session: RateLimitedSession):
        super().__init__(config, board_config, session)
        self.app_id = os.getenv('ADZUNA_APP_ID')
        self.app_key = os.getenv('ADZUNA_APP_KEY')
        self.base_url = f"https://api.adzuna.com/v1/api/jobs/{self.config.location.country.lower()}/search"
        self.source = JobSource.ADZUNA

    def search_jobs(self, keywords: str, location: str, pages: int = None) -> List[Job]:
        if not (self.app_id and self.app_key):
            logging.error("Adzuna credentials not set in ADZUNA_APP_ID/ADZUNA_APP_KEY")
            return []
        jobs = []
        per_page = self.board_config.pages_per_search or 50
        for page in range((pages or 1)):
            url = f"{self.base_url}/{page + 1}"
            params = {
                'app_id': self.app_id,
                'app_key': self.app_key,
                'results_per_page': per_page,
                'what': keywords,
                'where': location
            }
            response = self.session.get(url, params=params, delay=self.board_config.rate_limit_delay)
            if not response:
                continue
            data = response.json().get('results', [])
            for item in data:
                job = Job(
                    title=item.get('title'),
                    company=item.get('company', {}).get('display_name'),
                    location=item.get('location', {}).get('display_name'),
                    url=item.get('redirect_url'),
                    source=self.source,
                    scraped_at=datetime.now(),
                    salary_min=item.get('salary_min'),
                    salary_max=item.get('salary_max'),
                    remote_friendly='remote' in item.get('location', {}).get('display_name', '').lower(),
                )
                if self.is_job_relevant(job):
                    jobs.append(job)
            time.sleep(self.board_config.rate_limit_delay)
        return jobs

class JobFinder:
    """Main job finder with modular scraper system (ManualJobProvider removed)"""
    def __init__(self, config: AppConfig):
        self.config = config
        self.session = RateLimitedSession(config)
        self.scrapers = self._initialize_scrapers()

    def _initialize_scrapers(self) -> Dict[str, BaseScraper]:
        """Initialize scrapers based on enabled job boards"""
        scraper_classes = {
            "LinkedIn": LinkedInScraper,
            "Indeed": IndeedScraper,
            "Dice": DiceScraper,
            "ClearanceJobs": ClearanceJobsScraper,
            "USAJobs": USAJobsScraper,
            "Adzuna": AdzunaScraper,
        }
        scrapers = {}
        for board in self.config.scraping.enabled_boards:
            if board.type == JobBoardType.SCRAPER and board.name in scraper_classes:
                scraper_class = scraper_classes[board.name]
                scrapers[board.name] = scraper_class(self.config, board, self.session)
                logging.info(f"✅ Initialized {board.name} scraper (Priority: {board.priority})")
            elif board.type == JobBoardType.API and board.name in scraper_classes:
                scraper_class = scraper_classes[board.name]
                scrapers[board.name] = scraper_class(self.config, board, self.session)
                logging.info(f"✅ Initialized {board.name} API scraper (Priority: {board.priority})")
        return scrapers

    def find_jobs(self, keywords: List[str] = None, locations: List[str] = None) -> List[Job]:
        """Find jobs using enabled scrapers"""
        all_jobs = []
        if not keywords:
            keywords = self.config.jobs.target_titles[:3]  # Limit for performance
        if not locations:
            locations = self.config.location.primary_locations[:2] + ["Remote"]
        enabled_scrapers = [(name, scraper) for name, scraper in self.scrapers.items()]
        enabled_scrapers.sort(key=lambda x: self.config.scraping.job_boards[x[0]].priority)
        for scraper_name, scraper in enabled_scrapers:
            board_config = self.config.scraping.job_boards[scraper_name]
            logging.info(f"🔍 Starting {scraper_name} search (Priority: {board_config.priority})...")
            board_jobs = []
            keywords_to_use = keywords[:2] if board_config.priority <= 2 else keywords[:1]
            locations_to_use = locations[:2] if board_config.priority <= 2 else locations[:1]
            for keyword in keywords_to_use:
                for location in locations_to_use:
                    try:
                        jobs = scraper.search_jobs(keyword, location, board_config.pages_per_search)
                        board_jobs.extend(jobs)
                        logging.info(f"📊 {scraper_name}: Found {len(jobs)} jobs for '{keyword}' in '{location}'")
                        if len(keywords_to_use) > 1 or len(locations_to_use) > 1:
                            time.sleep(board_config.rate_limit_delay)
                    except Exception as e:
                        logging.error(f"❌ {scraper_name} search failed for '{keyword}' in '{location}': {e}")
                        continue
            all_jobs.extend(board_jobs)
            logging.info(f"✅ {scraper_name}: Total {len(board_jobs)} jobs found")
            time.sleep(random.uniform(1, 3))
        logging.info(f"🎯 Total jobs found across all sources: {len(all_jobs)}")
        # Compute relevance scores for each job
        from pathlib import Path
        try:
            resume_text = Path(self.config.user.resume_path).read_text(encoding='utf-8')
        except Exception:
            resume_text = ""
        scored_jobs = []
        for job in all_jobs:
            score_fraction, breakdown = compute_job_score(job, resume_text, self.config)
            job.score = int(score_fraction * 100)
            job.score_breakdown = breakdown
            scored_jobs.append(job)
        # Filter by threshold
        threshold = self.config.analysis.score_threshold
        filtered = [j for j in scored_jobs if j.score >= threshold]
        logging.info(f"🔢 Jobs above threshold ({threshold}): {len(filtered)}")
        # Sort by descending score
        filtered.sort(key=lambda j: j.score, reverse=True)
        return filtered

    def get_available_sources(self) -> List[str]:
        """Get list of available job sources"""
        return [board.name for board in self.config.scraping.job_boards.values()]

    def get_enabled_sources(self) -> List[str]:
        """Get list of enabled job sources"""
        return [board.name for board in self.config.scraping.enabled_boards]

# For backward compatibility
EnhancedJobFinder = JobFinder