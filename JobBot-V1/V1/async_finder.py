"""
Async job finding module with concurrent scraping capabilities.
Provides 3x faster job searching through parallel processing.
"""
import asyncio
import aiohttp
import time
import random
import logging
from datetime import datetime
from typing import List, Dict, Optional, AsyncGenerator
from urllib.parse import urljoin, quote_plus
import json
import re
from bs4 import BeautifulSoup

from .models import Job, JobSource
from .config import AppConfig, JobBoardConfig, JobBoardType
from .utils import extract_salary_range, compute_job_score


class AsyncRateLimitedSession:
    """Async HTTP session with rate limiting and retry logic"""
    
    def __init__(self, config: AppConfig):
        self.config = config.scraping
        self.domain_delays = {}
        self.last_request_time = {}
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
    async def _rate_limit(self, domain: str, delay: float = None):
        """Async rate limiting with adaptive delays"""
        if delay is None:
            delay = self.domain_delays.get(domain, self.config.base_delay)
            
        if domain in self.last_request_time:
            elapsed = time.time() - self.last_request_time[domain]
            if elapsed < delay:
                sleep_time = delay - elapsed
                # Add jitter to avoid thundering herd
                jitter = random.uniform(0.8, 1.2)
                await asyncio.sleep(sleep_time * jitter)
        
        self.last_request_time[domain] = time.time()
    
    def _get_realistic_headers(self):
        """Generate realistic browser headers"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': random.choice(['en-US,en;q=0.9', 'en-GB,en;q=0.8']),
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': random.choice(['1', '0']),
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Cache-Control': 'max-age=0'
        }
    
    async def get(self, session: aiohttp.ClientSession, url: str, **kwargs) -> Optional[aiohttp.ClientResponse]:
        """Async GET with rate limiting and error handling"""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        await self._rate_limit(domain)
        
        headers = kwargs.get('headers', {})
        headers.update(self._get_realistic_headers())
        kwargs['headers'] = headers
        
        # Add timeout if not specified
        if 'timeout' not in kwargs:
            kwargs['timeout'] = aiohttp.ClientTimeout(total=30, connect=10)
        
        try:
            response = await session.get(url, **kwargs)
            
            # Adaptive rate limiting based on response
            if response.status == 429:
                self.domain_delays[domain] = min(self.domain_delays.get(domain, 1) * 2, 30)
                logging.warning(f"Rate limited by {domain}, increasing delay to {self.domain_delays[domain]}s")
            elif response.status == 200 and domain in self.domain_delays:
                # Gradually reduce delay on success
                self.domain_delays[domain] = max(self.domain_delays[domain] * 0.9, 0.5)
            
            return response
            
        except asyncio.TimeoutError:
            logging.warning(f"Timeout accessing {url}")
            return None
        except Exception as e:
            logging.error(f"Error accessing {url}: {e}")
            return None


class AsyncBaseScraper:
    """Base class for async job scrapers"""
    
    def __init__(self, config: AppConfig, board_config: JobBoardConfig, rate_limiter: AsyncRateLimitedSession):
        self.config = config
        self.board_config = board_config
        self.rate_limiter = rate_limiter
        self.source = JobSource(board_config.name, board_config.base_url)
    
    def is_job_relevant(self, job: Job) -> bool:
        """Check if job matches user criteria"""
        if not job.title or not job.company:
            return False
        
        # Check excluded keywords
        title_lower = job.title.lower()
        for excluded in self.config.jobs.exclude_keywords:
            if excluded.lower() in title_lower:
                return False
        
        # Check minimum salary
        if job.salary_min and job.salary_min < self.config.jobs.min_salary:
            return False
        
        return True
    
    async def search_jobs(self, session: aiohttp.ClientSession, keywords: str, location: str, pages: int = None) -> List[Job]:
        """Override in subclasses"""
        raise NotImplementedError


class AsyncLinkedInScraper(AsyncBaseScraper):
    """Async LinkedIn job scraper"""
    
    async def parse_job_card(self, card_html: str) -> Optional[Job]:
        """Parse individual job card"""
        try:
            soup = BeautifulSoup(card_html, 'html.parser')
            
            # Multiple selectors for robustness
            title_selectors = [
                'h3.base-search-card__title a',
                '[data-entity-urn*="jobPosting"] h3 a',
                '.job-search-card__title a',
                'h3[class*="title"] a'
            ]
            
            title_elem = None
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    break
            
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            job_url = title_elem.get('href', '')
            if job_url and not job_url.startswith('http'):
                job_url = urljoin(self.board_config.base_url, job_url)
            
            # Company info
            company_selectors = [
                'h4.base-search-card__subtitle a',
                '.job-search-card__subtitle-link',
                'h4 a'
            ]
            
            company_elem = None
            for selector in company_selectors:
                company_elem = soup.select_one(selector)
                if company_elem:
                    break
            
            company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
            
            # Location
            location_selectors = [
                'span.job-search-card__location',
                '.base-search-card__metadata span',
                '[class*="location"]'
            ]
            
            location_elem = None
            for selector in location_selectors:
                location_elem = soup.select_one(selector)
                if location_elem:
                    break
            
            location = location_elem.get_text(strip=True) if location_elem else "Location not specified"
            
            # Extract salary if available
            salary_text = soup.get_text()
            salary_min, salary_max = extract_salary_range(salary_text)
            
            job = Job(
                title=title,
                company=company,
                location=location,
                description="",  # LinkedIn doesn't show full description in search
                salary_min=salary_min,
                salary_max=salary_max,
                source=self.source,
                url=job_url,
                remote_friendly='remote' in location.lower() or 'remote' in title.lower(),
                scraped_at=datetime.now()
            )
            
            return job if self.is_job_relevant(job) else None
            
        except Exception as e:
            logging.debug(f"Error parsing LinkedIn job card: {e}")
            return None
    
    async def search_jobs(self, session: aiohttp.ClientSession, keywords: str, location: str, pages: int = None) -> List[Job]:
        """Search LinkedIn jobs asynchronously"""
        if pages is None:
            pages = self.board_config.pages_per_search
        
        jobs = []
        
        for page in range(pages):
            start = page * 25
            search_url = f"{self.board_config.base_url}/jobs/search/"
            
            params = {
                'keywords': keywords,
                'location': location,
                'start': start,
                'f_TPR': 'r86400'  # Last 24 hours
            }
            
            # Build URL with parameters
            param_str = '&'.join([f"{k}={quote_plus(str(v))}" for k, v in params.items()])
            full_url = f"{search_url}?{param_str}"
            
            response = await self.rate_limiter.get(session, full_url)
            if not response or response.status != 200:
                logging.warning(f"Failed to fetch LinkedIn page {page + 1}")
                continue
            
            try:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find job cards
                job_cards = soup.select('.base-card.relative')
                
                # Parse job cards concurrently
                card_tasks = []
                for card in job_cards:
                    card_html = str(card)
                    task = self.parse_job_card(card_html)
                    card_tasks.append(task)
                
                # Gather results
                page_jobs = await asyncio.gather(*card_tasks, return_exceptions=True)
                
                # Filter out None results and exceptions
                valid_jobs = [job for job in page_jobs if isinstance(job, Job)]
                jobs.extend(valid_jobs)
                
                logging.debug(f"LinkedIn page {page + 1}: Found {len(valid_jobs)} valid jobs")
                
            except Exception as e:
                logging.error(f"Error parsing LinkedIn page {page + 1}: {e}")
                continue
        
        return jobs


class AsyncIndeedScraper(AsyncBaseScraper):
    """Async Indeed job scraper"""
    
    async def parse_job_card(self, card_html: str) -> Optional[Job]:
        """Parse individual Indeed job card"""
        try:
            soup = BeautifulSoup(card_html, 'html.parser')
            
            # Title with fallback selectors
            title_selectors = [
                'h2 a span[title]',
                '.jobTitle a span',
                '[data-testid="job-title"] span',
                'h2 span'
            ]
            
            title_elem = None
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    break
            
            if not title_elem:
                return None
            
            title = title_elem.get('title') or title_elem.get_text(strip=True)
            
            # Job URL
            link_elem = soup.select_one('h2 a, .jobTitle a')
            job_url = ""
            if link_elem:
                href = link_elem.get('href', '')
                if href:
                    job_url = urljoin(self.board_config.base_url, href)
            
            # Company
            company_selectors = [
                'span[data-testid="company-name"]',
                '.companyName a',
                '.companyName span'
            ]
            
            company_elem = None
            for selector in company_selectors:
                company_elem = soup.select_one(selector)
                if company_elem:
                    break
            
            company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
            
            # Location
            location_selectors = [
                '[data-testid="job-location"]',
                '.companyLocation',
                '.locationsContainer'
            ]
            
            location_elem = None
            for selector in location_selectors:
                location_elem = soup.select_one(selector)
                if location_elem:
                    break
            
            location = location_elem.get_text(strip=True) if location_elem else "Location not specified"
            
            # Salary
            salary_elem = soup.select_one('[data-testid="attribute_snippet_testid"]')
            salary_text = salary_elem.get_text() if salary_elem else ""
            salary_min, salary_max = extract_salary_range(salary_text)
            
            job = Job(
                title=title,
                company=company,
                location=location,
                description="",
                salary_min=salary_min,
                salary_max=salary_max,
                source=self.source,
                url=job_url,
                remote_friendly='remote' in location.lower() or 'remote' in title.lower(),
                scraped_at=datetime.now()
            )
            
            return job if self.is_job_relevant(job) else None
            
        except Exception as e:
            logging.debug(f"Error parsing Indeed job card: {e}")
            return None
    
    async def search_jobs(self, session: aiohttp.ClientSession, keywords: str, location: str, pages: int = None) -> List[Job]:
        """Search Indeed jobs asynchronously"""
        if pages is None:
            pages = self.board_config.pages_per_search
        
        jobs = []
        
        for page in range(pages):
            start = page * 10
            search_url = f"{self.board_config.base_url}/jobs"
            
            params = {
                'q': keywords,
                'l': location,
                'start': start,
                'sort': 'date'
            }
            
            param_str = '&'.join([f"{k}={quote_plus(str(v))}" for k, v in params.items()])
            full_url = f"{search_url}?{param_str}"
            
            response = await self.rate_limiter.get(session, full_url)
            if not response or response.status != 200:
                logging.warning(f"Failed to fetch Indeed page {page + 1}")
                continue
            
            try:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find job cards with multiple selectors
                job_cards = (soup.select('[data-testid="job-result"]') or 
                           soup.select('.job_seen_beacon') or 
                           soup.select('.slider_container .slider_item'))
                
                # Parse job cards concurrently
                card_tasks = []
                for card in job_cards:
                    card_html = str(card)
                    task = self.parse_job_card(card_html)
                    card_tasks.append(task)
                
                # Gather results
                page_jobs = await asyncio.gather(*card_tasks, return_exceptions=True)
                
                # Filter out None results and exceptions
                valid_jobs = [job for job in page_jobs if isinstance(job, Job)]
                jobs.extend(valid_jobs)
                
                logging.debug(f"Indeed page {page + 1}: Found {len(valid_jobs)} valid jobs")
                
            except Exception as e:
                logging.error(f"Error parsing Indeed page {page + 1}: {e}")
                continue
        
        return jobs


class AsyncJobFinder:
    """Async job finder with concurrent scraping"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.rate_limiter = AsyncRateLimitedSession(config)
        self.scrapers = self._initialize_scrapers()
    
    def _initialize_scrapers(self) -> Dict[str, AsyncBaseScraper]:
        """Initialize async scrapers"""
        scrapers = {}
        
        scraper_classes = {
            'LinkedIn': AsyncLinkedInScraper,
            'Indeed': AsyncIndeedScraper,
        }
        
        for board_name, board_config in self.config.scraping.job_boards.items():
            if not board_config.enabled:
                continue
            
            if board_name in scraper_classes:
                scraper_class = scraper_classes[board_name]
                scrapers[board_name] = scraper_class(self.config, board_config, self.rate_limiter)
                logging.info(f"✅ Initialized async {board_name} scraper")
        
        return scrapers
    
    async def search_single_source(self, session: aiohttp.ClientSession, scraper_name: str, 
                                   scraper: AsyncBaseScraper, keywords: str, location: str) -> List[Job]:
        """Search jobs from a single source"""
        try:
            board_config = self.config.scraping.job_boards[scraper_name]
            jobs = await scraper.search_jobs(session, keywords, location, board_config.pages_per_search)
            logging.info(f"📊 {scraper_name}: Found {len(jobs)} jobs for '{keywords}' in '{location}'")
            return jobs
        except Exception as e:
            logging.error(f"Error scraping {scraper_name}: {e}")
            return []
    
    async def find_jobs_concurrent(self, keywords: List[str] = None, locations: List[str] = None) -> List[Job]:
        """Find jobs using concurrent async scraping"""
        if not keywords:
            keywords = self.config.jobs.target_titles[:3]
        if not locations:
            locations = self.config.location.primary_locations[:2] + ["Remote"]
        
        all_jobs = []
        
        # Create aiohttp session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=10,  # Connections per host
            ttl_dns_cache=300,  # DNS cache TTL
        )
        
        async with aiohttp.ClientSession(connector=connector) as session:
            # Create tasks for all scraper/keyword/location combinations
            tasks = []
            
            for scraper_name, scraper in self.scrapers.items():
                board_config = self.config.scraping.job_boards[scraper_name]
                
                # Limit keywords/locations based on priority
                keywords_to_use = keywords[:2] if board_config.priority <= 2 else keywords[:1]
                locations_to_use = locations[:2] if board_config.priority <= 2 else locations[:1]
                
                for keyword in keywords_to_use:
                    for location in locations_to_use:
                        task = self.search_single_source(session, scraper_name, scraper, keyword, location)
                        tasks.append(task)
            
            logging.info(f"🚀 Starting {len(tasks)} concurrent searches...")
            
            # Execute all searches concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect results
            for result in results:
                if isinstance(result, list):
                    all_jobs.extend(result)
                elif isinstance(result, Exception):
                    logging.error(f"Search task failed: {result}")
        
        logging.info(f"🎯 Total jobs found: {len(all_jobs)}")
        return all_jobs
    
    def find_jobs(self, keywords: List[str] = None, locations: List[str] = None) -> List[Job]:
        """Synchronous wrapper for async job finding"""
        try:
            # Check if we're already in an event loop
            loop = asyncio.get_running_loop()
            # If we're in a loop, we need to run in a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.find_jobs_concurrent(keywords, locations))
                return future.result()
        except RuntimeError:
            # No event loop running, we can create one
            return asyncio.run(self.find_jobs_concurrent(keywords, locations))


# Integration function for backward compatibility
def create_async_job_finder(config: AppConfig) -> AsyncJobFinder:
    """Create async job finder instance"""
    return AsyncJobFinder(config)