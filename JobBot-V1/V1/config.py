# V1/config.py - Fixed Configuration with Simple List Support
"""
Fixed configuration management that supports both simple list and complex object formats
"""

import os
import json
import yaml
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set
from pathlib import Path
from enum import Enum

class JobBoardType(Enum):
    """Available job board types"""
    SCRAPER = "scraper"  # Web scraping based
    API = "api"          # API based
    MANUAL = "manual"    # Manually curated

@dataclass
class JobBoardConfig:
    """Configuration for individual job boards"""
    name: str
    type: JobBoardType
    enabled: bool = True
    priority: int = 1  # 1=highest, 5=lowest
    pages_per_search: int = 3
    rate_limit_delay: float = 1.0
    custom_settings: Dict = field(default_factory=dict)
    description: str = ""
    
    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = JobBoardType(self.type)

@dataclass
class ScrapingConfig:
    """Enhanced scraping configuration with backward compatibility"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 5.0
    timeout: int = 15
    respect_robots_txt: bool = False
    concurrent_requests: int = 3
    user_agent_rotation: bool = True
    proxy_enabled: bool = False
    proxy_list: List[str] = field(default_factory=list)
    
    # Support both simple list and complex job board configs
    enabled_sources: List[str] = field(default_factory=list)  # Simple format
    job_boards: Dict[str, JobBoardConfig] = field(default_factory=dict)  # Complex format
    pages_per_source: int = 2  # For simple format compatibility
    
    def __post_init__(self):
        # If we have a simple enabled_sources list, convert to job_boards
        if self.enabled_sources and not self.job_boards:
            self.job_boards = self._create_job_boards_from_list()
        
        # If we have job_boards but no enabled_sources, create the list
        elif self.job_boards and not self.enabled_sources:
            self.enabled_sources = [name for name, board in self.job_boards.items() if board.enabled]
        
        # If neither exists, create defaults
        elif not self.job_boards and not self.enabled_sources:
            self.job_boards = self._get_default_job_boards()
            self.enabled_sources = [name for name, board in self.job_boards.items() if board.enabled]
    
    def _create_job_boards_from_list(self) -> Dict[str, JobBoardConfig]:
        """Create job board configs from simple enabled_sources list"""
        default_configs = self._get_default_job_boards()
        
        # Enable only the sources in the list
        for name, config in default_configs.items():
            config.enabled = name in self.enabled_sources
            config.pages_per_search = self.pages_per_source
        
        return default_configs
    
    def _get_default_job_boards(self) -> Dict[str, JobBoardConfig]:
        """Get default job board configurations"""
        return {
            "Manual": JobBoardConfig(
                name="Manual",
                type=JobBoardType.MANUAL,
                enabled=True,
                priority=1,
                description="Manually curated high-quality positions"
            ),
            "LinkedIn": JobBoardConfig(
                name="LinkedIn",
                type=JobBoardType.SCRAPER,
                enabled=True,
                priority=2,
                pages_per_search=self.pages_per_source,
                rate_limit_delay=2.0,
                description="LinkedIn job postings"
            ),
            "Indeed": JobBoardConfig(
                name="Indeed",
                type=JobBoardType.SCRAPER,
                enabled=True,
                priority=3,
                pages_per_search=self.pages_per_source,
                rate_limit_delay=1.5,
                description="Indeed job board"
            ),
            "Dice": JobBoardConfig(
                name="Dice",
                type=JobBoardType.SCRAPER,
                enabled=False,  # Disabled by default due to frequent changes
                priority=3,
                pages_per_search=self.pages_per_source,
                rate_limit_delay=1.5,
                description="Dice technology job board"
            ),
            "ClearanceJobs": JobBoardConfig(
                name="ClearanceJobs",
                type=JobBoardType.SCRAPER,
                enabled=False,  # Only enable if user has clearance
                priority=2,
                pages_per_search=self.pages_per_source,
                rate_limit_delay=2.0,
                description="Security clearance positions"
            ),
            "USAJobs": JobBoardConfig(
                name="USAJobs",
                type=JobBoardType.API,
                enabled=False,
                priority=4,
                pages_per_search=self.pages_per_source,
                rate_limit_delay=1.0,
                description="USAJobs Government API"
            ),
            "Adzuna": JobBoardConfig(
                name="Adzuna",
                type=JobBoardType.API,
                enabled=False,
                priority=4,
                pages_per_search=self.pages_per_source,
                rate_limit_delay=1.0,
                description="Adzuna jobs API"
            )
        }
    
    @property
    def enabled_boards(self) -> List[JobBoardConfig]:
        """Get list of enabled job boards sorted by priority"""
        enabled = [board for board in self.job_boards.values() if board.enabled]
        return sorted(enabled, key=lambda x: x.priority)
    
    def enable_board(self, board_name: str):
        """Enable a specific job board"""
        if board_name in self.job_boards:
            self.job_boards[board_name].enabled = True
    
    def disable_board(self, board_name: str):
        """Disable a specific job board"""
        if board_name in self.job_boards:
            self.job_boards[board_name].enabled = False
    
    def get_board_config(self, board_name: str) -> Optional[JobBoardConfig]:
        """Get configuration for a specific board"""
        return self.job_boards.get(board_name)

    def sync_enabled_sources_and_boards(self):
        """
        Ensure enabled_sources and job_boards are consistent.
        Call this after any manual update to either.
        """
        # Update job_boards based on enabled_sources
        if self.enabled_sources:
            for name, board in self.job_boards.items():
                board.enabled = name in self.enabled_sources
        # Update enabled_sources based on job_boards
        self.enabled_sources = [name for name, board in self.job_boards.items() if board.enabled]

    def validate_sources(self, sources: List[str]) -> List[str]:
        """
        Return a list of invalid sources from the provided list.
        """
        valid = set(self._get_default_job_boards().keys())
        return [s for s in sources if s not in valid]

@dataclass
class AnalysisConfig:
    """Enhanced analysis configuration"""
    score_threshold: int = 75
    llm_model: str = "gpt-3.5-turbo"
    llm_temperature: float = 0.1
    batch_size: int = 5
    cache_llm_calls: bool = True
    lazy_analysis: bool = True
    
    # Performance settings
    max_concurrent_analysis: int = 3
    analysis_timeout: int = 30
    retry_failed_analysis: bool = True
    
    # AI Enhancement settings
    enhance_high_score_descriptions: bool = True
    high_score_threshold: int = 86
    generate_bullets_threshold: int = 75

@dataclass
class LocationConfig:
    """Enhanced location configuration"""
    primary_locations: List[str] = field(default_factory=lambda: [
        "Austin, TX", "Dallas, TX", "Houston, TX", "San Antonio, TX"
    ])
    target_locations: List[str] = field(default_factory=lambda: [
        "Remote", "Texas", "DFW", "Austin Metro"
    ])
    country: str = "United States"
    
    # Location scoring weights
    primary_location_weight: float = 1.0
    target_location_weight: float = 0.8
    remote_location_weight: float = 0.9

@dataclass
class JobConfig:
    """Enhanced job search criteria"""
    target_titles: List[str] = field(default_factory=lambda: [
        "Software Engineer", "Data Scientist", "Product Manager",
        "Cloud Engineer", "DevOps Engineer", "Full Stack Developer"
    ])
    target_companies: List[str] = field(default_factory=list)
    min_salary: int = 90000
    max_age_days: int = 30
    job_types: List[str] = field(default_factory=lambda: [
        "Full-time", "Contract"
    ])
    exclude_keywords: List[str] = field(default_factory=lambda: [
        "intern", "unpaid", "volunteer", "entry level"
    ])
    
    # Enhanced filtering
    required_keywords: List[str] = field(default_factory=list)
    preferred_keywords: List[str] = field(default_factory=list)
    title_weight: float = 0.3
    company_weight: float = 0.2
    salary_weight: float = 0.25
    location_weight: float = 0.25

@dataclass
class UserProfile:
    """Enhanced user profile"""
    name: str = "Job Seeker"
    email: str = ""
    resume_path: str = "resume/base_resume.txt"
    target_industry: str = "Technology"
    experience_level: str = "Senior"  # Entry, Mid, Senior, Executive
    clearance_level: Optional[str] = None  # None, Secret, TS, TS/SCI
    preferred_work_type: str = "Hybrid"  # Remote, Hybrid, On-site

@dataclass
class AppConfig:
    """Main application configuration with enhanced modularity"""
    scraping: ScrapingConfig = field(default_factory=ScrapingConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    location: LocationConfig = field(default_factory=LocationConfig)
    jobs: JobConfig = field(default_factory=JobConfig)
    user: UserProfile = field(default_factory=UserProfile)
    profiles: Dict[str, UserProfile] = field(default_factory=dict)
    active_profile: str = ''
    
    # System settings
    output_dir: str = "./output"
    log_level: str = "INFO"
    version: str = "1.0.0"

class ConfigManager:
    """Enhanced configuration manager with validation and templates"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
    
    def load_config(self) -> AppConfig:
        """Load configuration with error handling and validation"""
        if not os.path.exists(self.config_path):
            print(f"⚠️  Configuration file {self.config_path} not found. Creating default...")
            self._create_default_config()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            # Handle scraping config specially to support both formats
            scraping_data = data.get('scraping', {})
            
            # Convert simple enabled_sources list to full config if needed
            if 'enabled_sources' in scraping_data and 'job_boards' not in scraping_data:
                scraping_config = ScrapingConfig(
                    enabled_sources=scraping_data.get('enabled_sources', []),
                    pages_per_source=scraping_data.get('pages_per_source', 2),
                    max_retries=scraping_data.get('max_retries', 3),
                    base_delay=scraping_data.get('base_delay', 1.0),
                    max_delay=scraping_data.get('max_delay', 5.0),
                    timeout=scraping_data.get('timeout', 15)
                )
            else:
                # Handle complex job_boards format
                if 'job_boards' in scraping_data:
                    job_boards = {}
                    for name, board_data in scraping_data['job_boards'].items():
                        job_boards[name] = JobBoardConfig(**board_data)
                    scraping_data['job_boards'] = job_boards
                
                scraping_config = ScrapingConfig(**scraping_data)

            # Always sync enabled_sources and job_boards after loading
            scraping_config.sync_enabled_sources_and_boards()

            config = AppConfig(
                scraping=scraping_config,
                analysis=AnalysisConfig(**data.get('analysis', {})),
                location=LocationConfig(**data.get('location', {})),
                jobs=JobConfig(**data.get('jobs', {})),
                # Load single user or profiles
                user=UserProfile(**data.get('user', {})),
                profiles={k: UserProfile(**v) for k, v in data.get('profiles', {}).items()},
                active_profile=data.get('active_profile', '') or (list(data.get('profiles', {}).keys())[0] if data.get('profiles') else 'default'),
                output_dir=data.get('output_dir', './output'),
                log_level=data.get('log_level', 'INFO'),
                version=data.get('version', '1.0.0')
            )
            # If no profiles defined, use single user as 'default'
            if not config.profiles:
                config.profiles = {'default': config.user}
                config.active_profile = 'default'
            # Override user with active_profile
            if config.active_profile in config.profiles:
                config.user = config.profiles[config.active_profile]
            print(f"✅ Configuration loaded from {self.config_path} (active profile: {config.active_profile})")
            return config
            
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            print("Using default configuration...")
            return AppConfig()
    
    def _create_default_config(self):
        """Create a default configuration file"""
        default_config = """# Job Hunter Configuration File
# Simple configuration for easy customization

# User Profile
user:
  name: "Your Name Here"
  email: "your.email@example.com"
  resume_path: "resume/base_resume.txt"
  target_industry: "Technology"
  experience_level: "Senior"  # Entry, Mid, Senior, Executive
  clearance_level: null       # null, Secret, TS, TS/SCI
  preferred_work_type: "Hybrid"  # Remote, Hybrid, On-site

# Job Search Criteria
jobs:
  target_titles:
    - "Software Engineer"
    - "Data Scientist" 
    - "Product Manager"
    - "Cloud Engineer"
    - "DevOps Engineer"
    - "Full Stack Developer"
  target_companies: []  # Leave empty for all companies
  min_salary: 90000
  max_age_days: 30
  job_types:
    - "Full-time"
    - "Contract"
  exclude_keywords:
    - "intern"
    - "unpaid"
    - "volunteer"

# Location Preferences
location:
  primary_locations:
    - "Austin, TX"
    - "Dallas, TX" 
    - "Houston, TX"
  target_locations:
    - "Remote"
    - "Texas"
    - "DFW"
  country: "United States"

# Scraping Configuration (Simple Format)
scraping:
  pages_per_source: 2
  max_retries: 3
  base_delay: 1.0
  max_delay: 5.0
  timeout: 15
  enabled_sources:  # Simple list format
    - "Manual"
    - "LinkedIn"
    - "Indeed"
    # - "Dice"          # Enable if needed
    # - "ClearanceJobs" # Enable if you have clearance

# AI Analysis Configuration
analysis:
  score_threshold: 75           # Minimum score for high priority
  llm_model: "gpt-3.5-turbo"   # LLM model to use
  llm_temperature: 0.1          # AI creativity (0.0-1.0)
  batch_size: 5                 # Jobs to analyze in parallel
  cache_llm_calls: true         # Cache AI responses
  lazy_analysis: true           # Generate bullets on-demand only

# System Settings
output_dir: "./output"
log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR
version: "1.0.0"
"""
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write(default_config)
            print(f"📄 Default configuration created: {self.config_path}")
        except Exception as e:
            print(f"❌ Error creating default config: {e}")
    
    def get_config_summary(self, config: AppConfig) -> str:
        """Get human-readable configuration summary"""
        enabled_boards = config.scraping.enabled_boards
        
        summary = [
            f"🎯 Job Hunter Configuration Summary",
            f"{'='*50}",
            f"👤 User: {config.user.name} ({config.user.experience_level})",
            f"🏢 Industry: {config.user.target_industry}",
            f"💼 Work Type: {config.user.preferred_work_type}",
            f"",
            f"📋 Job Search Criteria:",
            f"  • Target Titles: {len(config.jobs.target_titles)} roles",
            f"  • Min Salary: ${config.jobs.min_salary:,}",
            f"  • Locations: {', '.join(config.location.primary_locations[:3])}{'...' if len(config.location.primary_locations) > 3 else ''}",
            f"",
            f"🔍 Enabled Job Sources ({len(enabled_boards)}):",
        ]
        
        for board in enabled_boards:
            status_icon = "🤖" if board.type == JobBoardType.API else "🕷️" if board.type == JobBoardType.SCRAPER else "✋"
            summary.append(f"  {status_icon} {board.name} (Priority: {board.priority}, Pages: {board.pages_per_search})")
        
        summary.extend([
            f"",
            f"🤖 Analysis Settings:",
            f"  • Score Threshold: {config.analysis.score_threshold}",
            f"  • Lazy Analysis: {'Yes' if config.analysis.lazy_analysis else 'No'}",
            f"  • LLM Model: {config.analysis.llm_model}",
            f"",
            f"📁 Output: {config.output_dir}",
        ])
        
        return "\n".join(summary)

    def get_config_summary(self, config: AppConfig) -> str:
        """Get human-readable configuration summary"""
        enabled_boards = config.scraping.enabled_boards
        enabled_sources = getattr(config.scraping, 'enabled_sources', [])
        
        summary = [
            f"🎯 Job Hunter Configuration Summary",
            f"{'='*50}",
            f"👤 User: {config.user.name} ({config.user.experience_level})",
            f"🏢 Industry: {config.user.target_industry}",
            f"💼 Work Type: {config.user.preferred_work_type}",
            f"",
            f"📋 Job Search Criteria:",
            f"  • Target Titles: {len(config.jobs.target_titles)} roles",
            f"  • Min Salary: ${config.jobs.min_salary:,}",
            f"  • Locations: {', '.join(config.location.primary_locations[:3])}{'...' if len(config.location.primary_locations) > 3 else ''}",
            f"",
            f"🔍 Enabled Job Sources ({len(enabled_sources)}):",
        ]
        
        # Use enabled_sources list if available, otherwise use enabled_boards
        if enabled_sources:
            for source in enabled_sources:
                summary.append(f"  🕷️ {source}")
        else:
            for board in enabled_boards:
                status_icon = "🤖" if board.type == JobBoardType.API else "🕷️" if board.type == JobBoardType.SCRAPER else "✋"
                summary.append(f"  {status_icon} {board.name} (Priority: {board.priority})")
        
        summary.extend([
            f"",
            f"🤖 Analysis Settings:",
            f"  • Score Threshold: {config.analysis.score_threshold}",
            f"  • Lazy Analysis: {'Yes' if config.analysis.lazy_analysis else 'No'}",
            f"  • LLM Model: {config.analysis.llm_model}",
            f"",
            f"📁 Output: {config.output_dir}",
        ])
        
        return "\n".join(summary)
    
    def validate_config(self, config: AppConfig) -> List[str]:
        """Validate configuration and return warnings"""
        warnings = []
        
        # Check API requirements
        if not os.getenv('OPENAI_API_KEY'):
            warnings.append("OPENAI_API_KEY not set - AI features will be limited")
        
        # Check enabled boards
        enabled_boards = config.scraping.enabled_boards
        if not enabled_boards:
            warnings.append("No job sources enabled - you won't find any jobs!")
        
        # Check resume file
        if not os.path.exists(config.user.resume_path):
            warnings.append(f"Resume file not found: {config.user.resume_path}")
        
        # Check salary range
        if config.jobs.min_salary < 30000:
            warnings.append("Minimum salary seems unusually low")
        
        return warnings

def create_sample_config(config_path: str = "config.yaml"):
    """Create a sample configuration file"""
    manager = ConfigManager(config_path)
    manager._create_default_config()