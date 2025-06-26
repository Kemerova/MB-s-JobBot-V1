# V1/__init__.py - Enhanced Module Initialization
"""
JobBot V1 - Enhanced AI-Powered Job Hunting System
Now with concurrent scraping, mobile-responsive dashboard, and application tracking
"""

import os
from dotenv import load_dotenv

# Load environment variables before importing other modules
load_dotenv()

# Core models and data structures
from .models import Job, JobSource, Priority

# Configuration management
from .config import (
    AppConfig, ConfigManager, JobBoardConfig, JobBoardType,
    ScrapingConfig, AnalysisConfig, LocationConfig, JobConfig, UserProfile,
    create_sample_config
)

# Core functionality
from .finder import JobFinder
from .async_finder import AsyncJobFinder
from .analyzer import JobAnalyzer
from .dashboard import DashboardServer
from .reporting import ReportGenerator

# Enhanced features
from .application_tracking import ApplicationTracker, ApplicationStatus
from .starred_jobs import StarredJobsManager
from .setup_wizard import SetupWizard
from .error_handling import UserFriendlyError, ErrorCategory

# Utilities
from .utils import (
    setup_logging, make_unique, filter_stale_jobs, validate_environment,
    retry_on_failure, cache_result, extract_salary_range
)

# Check if OPENAI_API_KEY is loaded
AI_FEATURES_AVAILABLE = bool(os.getenv("OPENAI_API_KEY"))

if not AI_FEATURES_AVAILABLE:
    print("⚠️  INFO: OPENAI_API_KEY environment variable not set.")
    print("   Job scraping will work, but AI analysis features will be limited.")
    print("   Please add OPENAI_API_KEY=your_key_here to your .env file for full features.")

__version__ = "1.0.0"
__title__ = "JobBot"
__description__ = "Enhanced AI-Powered Job Hunting Assistant with Concurrent Scraping & Application Tracking"

# Main exports for easy importing
__all__ = [
    # Core models
    "Job", "JobSource", "Priority",
    
    # Core functionality  
    "JobFinder", "AsyncJobFinder", "JobAnalyzer", "DashboardServer", "ReportGenerator",
    
    # Enhanced features
    "ApplicationTracker", "ApplicationStatus", "StarredJobsManager", 
    "SetupWizard", "UserFriendlyError", "ErrorCategory",
    
    # Configuration
    "AppConfig", "ConfigManager", "JobBoardConfig", "JobBoardType",
    "ScrapingConfig", "AnalysisConfig", "LocationConfig", "JobConfig", "UserProfile",
    "create_sample_config",
    
    # Utilities
    "setup_logging", "make_unique", "filter_stale_jobs", "validate_environment",
    "retry_on_failure", "cache_result", "extract_salary_range",
    
    # Features
    "AI_FEATURES_AVAILABLE"
]