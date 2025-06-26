"""
Smart Error Handling System
Provides user-friendly error messages with solutions and recovery suggestions.
"""
import logging
import functools
from typing import Dict, Any, Optional, Callable, Union
from enum import Enum
import traceback
import sys
from pathlib import Path


class ErrorCategory(Enum):
    """Categories of errors for better handling"""
    CONFIGURATION = "configuration"
    NETWORK = "network"
    API = "api"
    FILE_SYSTEM = "file_system"
    VALIDATION = "validation"
    SCRAPING = "scraping"
    ANALYSIS = "analysis"
    UNKNOWN = "unknown"


class UserFriendlyError(Exception):
    """User-friendly error with solutions and context"""
    
    def __init__(
        self,
        title: str,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        solution: Optional[str] = None,
        help_link: Optional[str] = None,
        technical_details: Optional[str] = None,
        recoverable: bool = True
    ):
        self.title = title
        self.message = message
        self.category = category
        self.solution = solution
        self.help_link = help_link
        self.technical_details = technical_details
        self.recoverable = recoverable
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for JSON serialization"""
        return {
            "title": self.title,
            "message": self.message,
            "category": self.category.value,
            "solution": self.solution,
            "help_link": self.help_link,
            "technical_details": self.technical_details,
            "recoverable": self.recoverable
        }
    
    def format_for_cli(self) -> str:
        """Format error for command line display"""
        output = f"❌ {self.title}\n"
        output += f"   {self.message}\n"
        
        if self.solution:
            output += f"\n💡 Solution:\n   {self.solution}\n"
        
        if self.help_link:
            output += f"\n🔗 Help: {self.help_link}\n"
        
        return output


class ErrorTranslator:
    """Translates technical errors to user-friendly messages"""
    
    ERROR_PATTERNS = {
        # Configuration Errors
        "OPENAI_API_KEY": {
            "category": ErrorCategory.CONFIGURATION,
            "title": "Missing OpenAI API Key",
            "message": "OpenAI API key is required for job analysis features",
            "solution": "Get an API key from https://platform.openai.com/api-keys and add it to your .env file",
            "help_link": "https://docs.anthropic.com/en/docs/claude-code/setup"
        },
        
        "config.yaml not found": {
            "category": ErrorCategory.CONFIGURATION,
            "title": "Configuration File Missing",
            "message": "The configuration file config.yaml was not found",
            "solution": "Run 'python main.py --setup-config' to create a sample configuration file",
            "help_link": "/setup"
        },
        
        "Invalid configuration": {
            "category": ErrorCategory.CONFIGURATION,
            "title": "Invalid Configuration",
            "message": "The configuration file contains invalid settings",
            "solution": "Check your config.yaml file for syntax errors or missing required fields",
            "help_link": "/setup"
        },
        
        # Network Errors
        "Connection refused": {
            "category": ErrorCategory.NETWORK,
            "title": "Connection Failed",
            "message": "Unable to connect to the service",
            "solution": "Check your internet connection and try again",
            "recoverable": True
        },
        
        "timeout": {
            "category": ErrorCategory.NETWORK,
            "title": "Request Timeout",
            "message": "The request took too long to complete",
            "solution": "The service might be slow. Try again in a few moments",
            "recoverable": True
        },
        
        "429": {  # Rate limiting
            "category": ErrorCategory.API,
            "title": "Rate Limited",
            "message": "Too many requests sent to the service",
            "solution": "Wait a moment before trying again. Consider reducing the number of pages searched",
            "recoverable": True
        },
        
        # API Errors
        "401": {  # Unauthorized
            "category": ErrorCategory.API,
            "title": "Authentication Failed",
            "message": "Invalid API credentials",
            "solution": "Check your API keys in the .env file",
            "help_link": "/setup"
        },
        
        "quota_exceeded": {
            "category": ErrorCategory.API,
            "title": "API Quota Exceeded",
            "message": "You've exceeded your API usage limits",
            "solution": "Check your API billing and usage at the provider's dashboard",
            "recoverable": False
        },
        
        # File System Errors
        "Permission denied": {
            "category": ErrorCategory.FILE_SYSTEM,
            "title": "File Permission Error",
            "message": "Insufficient permissions to access the file or directory",
            "solution": "Check file permissions or run with appropriate privileges",
            "recoverable": True
        },
        
        "No space left": {
            "category": ErrorCategory.FILE_SYSTEM,
            "title": "Storage Full",
            "message": "Not enough disk space to complete the operation",
            "solution": "Free up disk space and try again",
            "recoverable": True
        },
        
        # Validation Errors
        "Invalid email": {
            "category": ErrorCategory.VALIDATION,
            "title": "Invalid Email Format",
            "message": "The email address format is not valid",
            "solution": "Enter a valid email address (e.g., user@example.com)",
            "recoverable": True
        },
        
        # Scraping Errors
        "blocked": {
            "category": ErrorCategory.SCRAPING,
            "title": "Scraping Blocked",
            "message": "The job board has blocked our requests",
            "solution": "Try again later or use different job sources",
            "recoverable": True
        },
        
        "parse error": {
            "category": ErrorCategory.SCRAPING,
            "title": "Page Structure Changed",
            "message": "Unable to parse job listings from the page",
            "solution": "The job board may have updated their layout. Try other sources for now",
            "recoverable": True
        }
    }
    
    @classmethod
    def translate_error(cls, error: Exception, context: Optional[str] = None) -> UserFriendlyError:
        """Translate a technical error to user-friendly format"""
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Look for patterns in error message
        for pattern, error_info in cls.ERROR_PATTERNS.items():
            if pattern.lower() in error_str or pattern.lower() in error_type.lower():
                return UserFriendlyError(
                    title=error_info["title"],
                    message=error_info["message"],
                    category=error_info["category"],
                    solution=error_info.get("solution"),
                    help_link=error_info.get("help_link"),
                    technical_details=str(error),
                    recoverable=error_info.get("recoverable", True)
                )
        
        # Handle specific exception types
        if isinstance(error, FileNotFoundError):
            return UserFriendlyError(
                title="File Not Found",
                message=f"Required file not found: {error.filename}",
                category=ErrorCategory.FILE_SYSTEM,
                solution="Check that all required files are in place",
                technical_details=str(error),
                recoverable=True
            )
        
        elif isinstance(error, ImportError):
            missing_module = str(error).split("'")[1] if "'" in str(error) else "unknown"
            return UserFriendlyError(
                title="Missing Dependency",
                message=f"Required Python package '{missing_module}' is not installed",
                category=ErrorCategory.CONFIGURATION,
                solution=f"Install the missing package: pip install {missing_module}",
                technical_details=str(error),
                recoverable=True
            )
        
        elif isinstance(error, KeyError):
            missing_key = str(error).strip("'\"")
            return UserFriendlyError(
                title="Missing Configuration",
                message=f"Required setting '{missing_key}' is missing",
                category=ErrorCategory.CONFIGURATION,
                solution="Check your configuration file for missing required fields",
                help_link="/setup",
                technical_details=str(error),
                recoverable=True
            )
        
        # Default fallback
        return UserFriendlyError(
            title="Unexpected Error",
            message="An unexpected error occurred",
            category=ErrorCategory.UNKNOWN,
            solution="Try the operation again. If the problem persists, check the logs for more details",
            technical_details=str(error),
            recoverable=True
        )


class ErrorHandler:
    """Centralized error handling and logging"""
    
    def __init__(self, log_errors: bool = True):
        self.log_errors = log_errors
        self.error_count = 0
        self.recent_errors = []
    
    def handle_error(
        self,
        error: Exception,
        context: Optional[str] = None,
        show_user_message: bool = True
    ) -> UserFriendlyError:
        """Handle an error with logging and user feedback"""
        
        # Translate to user-friendly error
        friendly_error = ErrorTranslator.translate_error(error, context)
        
        # Log technical details
        if self.log_errors:
            logging.error(f"Error in {context or 'unknown context'}: {error}")
            logging.debug(f"Full traceback: {traceback.format_exc()}")
        
        # Track error statistics
        self.error_count += 1
        self.recent_errors.append({
            "timestamp": __import__("datetime").datetime.now(),
            "context": context,
            "category": friendly_error.category.value,
            "title": friendly_error.title
        })
        
        # Keep only last 10 errors
        if len(self.recent_errors) > 10:
            self.recent_errors = self.recent_errors[-10:]
        
        # Show user message if requested
        if show_user_message:
            print(friendly_error.format_for_cli())
        
        return friendly_error
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        categories = {}
        for error in self.recent_errors:
            category = error["category"]
            categories[category] = categories.get(category, 0) + 1
        
        return {
            "total_errors": self.error_count,
            "recent_errors": len(self.recent_errors),
            "categories": categories,
            "last_error": self.recent_errors[-1] if self.recent_errors else None
        }


# Global error handler instance
global_error_handler = ErrorHandler()


def handle_errors(
    context: Optional[str] = None,
    show_user_message: bool = True,
    reraise: bool = False,
    fallback_return: Any = None
):
    """Decorator for automatic error handling"""
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                friendly_error = global_error_handler.handle_error(
                    e, 
                    context or func.__name__,
                    show_user_message
                )
                
                if reraise:
                    raise friendly_error
                
                return fallback_return
        
        return wrapper
    return decorator


def handle_openai_errors(func: Callable) -> Callable:
    """Specialized decorator for OpenAI API errors"""
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            
            if "api key" in error_str or "unauthorized" in error_str:
                raise UserFriendlyError(
                    title="Invalid OpenAI API Key",
                    message="Your OpenAI API key is invalid or missing",
                    category=ErrorCategory.API,
                    solution="Get a valid API key from https://platform.openai.com/api-keys",
                    help_link="/setup",
                    technical_details=str(e)
                )
            
            elif "quota" in error_str or "billing" in error_str:
                raise UserFriendlyError(
                    title="OpenAI Quota Exceeded",
                    message="You've exceeded your OpenAI API usage limits",
                    category=ErrorCategory.API,
                    solution="Add billing information at https://platform.openai.com/account/billing",
                    technical_details=str(e),
                    recoverable=False
                )
            
            elif "rate limit" in error_str:
                raise UserFriendlyError(
                    title="OpenAI Rate Limited",
                    message="Too many requests to OpenAI API",
                    category=ErrorCategory.API,
                    solution="Wait a moment before trying again",
                    technical_details=str(e),
                    recoverable=True
                )
            
            elif "model" in error_str and "not found" in error_str:
                raise UserFriendlyError(
                    title="OpenAI Model Not Available",
                    message="The requested AI model is not available",
                    category=ErrorCategory.API,
                    solution="Try using gpt-3.5-turbo instead",
                    technical_details=str(e),
                    recoverable=True
                )
            
            else:
                # Use general error translation
                raise ErrorTranslator.translate_error(e)
    
    return wrapper


def handle_network_errors(func: Callable) -> Callable:
    """Specialized decorator for network-related errors"""
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            
            if "connection" in error_str and "refused" in error_str:
                raise UserFriendlyError(
                    title="Connection Refused",
                    message="Unable to connect to the service",
                    category=ErrorCategory.NETWORK,
                    solution="Check your internet connection and try again",
                    technical_details=str(e),
                    recoverable=True
                )
            
            elif "timeout" in error_str:
                raise UserFriendlyError(
                    title="Request Timeout",
                    message="The request took too long to complete",
                    category=ErrorCategory.NETWORK,
                    solution="The service might be slow. Try again in a few moments",
                    technical_details=str(e),
                    recoverable=True
                )
            
            elif "dns" in error_str or "name resolution" in error_str:
                raise UserFriendlyError(
                    title="DNS Resolution Failed",
                    message="Unable to resolve the domain name",
                    category=ErrorCategory.NETWORK,
                    solution="Check your internet connection and DNS settings",
                    technical_details=str(e),
                    recoverable=True
                )
            
            else:
                raise ErrorTranslator.translate_error(e)
    
    return wrapper


class ProgressTracker:
    """Enhanced progress tracking with error handling"""
    
    def __init__(self, total_items: int, description: str = "Processing"):
        self.total_items = total_items
        self.current_item = 0
        self.description = description
        self.errors = []
        self.start_time = __import__("time").time()
    
    def update(self, increment: int = 1, item_description: str = ""):
        """Update progress"""
        self.current_item += increment
        
        # Calculate progress
        progress = (self.current_item / self.total_items) * 100
        elapsed_time = __import__("time").time() - self.start_time
        
        # Estimate time remaining
        if self.current_item > 0:
            rate = self.current_item / elapsed_time
            remaining_time = (self.total_items - self.current_item) / rate if rate > 0 else 0
            remaining_str = f" (ETA: {int(remaining_time)}s)" if remaining_time > 5 else ""
        else:
            remaining_str = ""
        
        # Display progress
        bar_length = 30
        filled_length = int(bar_length * progress / 100)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        print(f"\r{self.description}: {bar} {progress:.1f}%{remaining_str} - {item_description}", end="", flush=True)
    
    def add_error(self, error: Exception, item_description: str = ""):
        """Add an error to the tracker"""
        self.errors.append({
            "item": self.current_item,
            "description": item_description,
            "error": str(error)
        })
    
    def finish(self):
        """Complete the progress tracking"""
        print()  # New line
        
        if self.errors:
            print(f"⚠️  Completed with {len(self.errors)} errors:")
            for error in self.errors[-3:]:  # Show last 3 errors
                print(f"   • {error['description']}: {error['error']}")
            
            if len(self.errors) > 3:
                print(f"   ... and {len(self.errors) - 3} more errors")
        else:
            print("✅ Completed successfully!")


# Context manager for progress tracking
class progress_context:
    """Context manager for progress tracking with error handling"""
    
    def __init__(self, total_items: int, description: str = "Processing"):
        self.tracker = ProgressTracker(total_items, description)
    
    def __enter__(self):
        return self.tracker
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tracker.finish()
        return False  # Don't suppress exceptions


# Utility functions
def validate_environment() -> list:
    """Validate environment and return list of issues"""
    issues = []
    
    # Check Python version
    if sys.version_info < (3, 8):
        issues.append(
            "Python 3.8+ is required. You're running " + 
            f"{sys.version_info.major}.{sys.version_info.minor}"
        )
    
    # Check required environment variables
    required_env_vars = ["OPENAI_API_KEY"]
    for var in required_env_vars:
        if not __import__("os").getenv(var):
            issues.append(f"Missing environment variable: {var}")
    
    # Check required files
    required_files = ["config.yaml"]
    for file_path in required_files:
        if not Path(file_path).exists():
            issues.append(f"Missing required file: {file_path}")
    
    # Check write permissions
    try:
        test_file = Path("output/.test_write")
        test_file.parent.mkdir(exist_ok=True)
        test_file.write_text("test")
        test_file.unlink()
    except Exception:
        issues.append("No write permission in output directory")
    
    return issues


def safe_import(module_name: str, package_name: str = None) -> bool:
    """Safely try to import a module and return success status"""
    try:
        __import__(module_name)
        return True
    except ImportError:
        package = package_name or module_name
        print(f"⚠️  Optional dependency '{package}' not found.")
        print(f"   Install with: pip install {package}")
        return False