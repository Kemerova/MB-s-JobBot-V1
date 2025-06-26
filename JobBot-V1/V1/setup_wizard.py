"""
Interactive Setup Wizard for Job Hunting Application
Provides web-based configuration with live validation and user-friendly interface.
"""
import os
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, ValidationError
import requests
from datetime import datetime

from .config import AppConfig, UserProfile, JobsConfig, LocationConfig, ScrapingConfig
from .models import JobSource


class SetupValidationError(Exception):
    """Custom exception for setup validation errors"""
    def __init__(self, field: str, message: str, solution: str = ""):
        self.field = field
        self.message = message
        self.solution = solution
        super().__init__(message)


class APIKeyValidator:
    """Validates API keys with live API calls"""
    
    @staticmethod
    def validate_openai_key(api_key: str) -> Dict[str, Any]:
        """Validate OpenAI API key"""
        if not api_key or len(api_key) < 20:
            return {
                "valid": False,
                "error": "API key appears to be invalid (too short)",
                "solution": "Get a valid API key from https://platform.openai.com/api-keys"
            }
        
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Test with a minimal request
            response = requests.get(
                "https://api.openai.com/v1/models",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                models = response.json().get('data', [])
                gpt_models = [m['id'] for m in models if 'gpt' in m['id'].lower()]
                return {
                    "valid": True,
                    "message": "API key is valid",
                    "available_models": gpt_models[:5],  # Show first 5 GPT models
                    "account_info": "Key validated successfully"
                }
            elif response.status_code == 401:
                return {
                    "valid": False,
                    "error": "Invalid API key",
                    "solution": "Check your API key at https://platform.openai.com/api-keys"
                }
            elif response.status_code == 429:
                return {
                    "valid": False,
                    "error": "Rate limited or insufficient credits",
                    "solution": "Add billing information at https://platform.openai.com/account/billing"
                }
            else:
                return {
                    "valid": False,
                    "error": f"API error: {response.status_code}",
                    "solution": "Check OpenAI status at https://status.openai.com/"
                }
                
        except requests.exceptions.Timeout:
            return {
                "valid": False,
                "error": "Connection timeout",
                "solution": "Check your internet connection and try again"
            }
        except Exception as e:
            return {
                "valid": False,
                "error": f"Connection error: {str(e)}",
                "solution": "Check your internet connection"
            }
    
    @staticmethod
    def validate_usajobs_key(api_key: str) -> Dict[str, Any]:
        """Validate USAJobs API key"""
        if not api_key:
            return {"valid": True, "message": "USAJobs API key is optional"}
        
        try:
            headers = {
                "Host": "data.usajobs.gov",
                "User-Agent": "job-hunter-app",
                "Authorization-Key": api_key
            }
            
            response = requests.get(
                "https://data.usajobs.gov/api/search?ResultsPerPage=1",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return {"valid": True, "message": "USAJobs API key is valid"}
            else:
                return {
                    "valid": False,
                    "error": f"USAJobs API error: {response.status_code}",
                    "solution": "Get an API key from https://developer.usajobs.gov/"
                }
                
        except Exception as e:
            return {
                "valid": False,
                "error": f"Error validating USAJobs key: {str(e)}",
                "solution": "Check your internet connection"
            }


class SetupWizardStep(BaseModel):
    """Base class for setup wizard steps"""
    id: str
    title: str
    description: str
    required: bool = True
    completed: bool = False


class APIKeysStep(SetupWizardStep):
    """API Keys configuration step"""
    id: str = "api_keys"
    title: str = "API Keys Setup"
    description: str = "Configure API keys for job analysis and searching"
    
    openai_key: Optional[str] = None
    openai_valid: bool = False
    usajobs_key: Optional[str] = None
    usajobs_valid: bool = False
    adzuna_app_id: Optional[str] = None
    adzuna_app_key: Optional[str] = None


class UserProfileStep(SetupWizardStep):
    """User profile configuration step"""
    id: str = "user_profile"
    title: str = "User Profile"
    description: str = "Tell us about yourself for personalized job matching"
    
    name: str = ""
    email: str = ""
    experience_level: str = "Mid-level"
    target_industry: str = ""
    current_location: str = ""
    willing_to_relocate: bool = False


class JobPreferencesStep(SetupWizardStep):
    """Job preferences configuration step"""
    id: str = "job_preferences"
    title: str = "Job Preferences"
    description: str = "Define your ideal job criteria"
    
    target_titles: List[str] = []
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    preferred_locations: List[str] = []
    remote_ok: bool = True
    exclude_keywords: List[str] = []


class JobSourcesStep(SetupWizardStep):
    """Job sources configuration step"""
    id: str = "job_sources"
    title: str = "Job Sources"
    description: str = "Select which job boards to search"
    
    enabled_sources: Dict[str, bool] = {
        "LinkedIn": True,
        "Indeed": True,
        "Dice": False,
        "ClearanceJobs": False,
        "USAJobs": False,
        "Adzuna": False
    }
    pages_per_source: int = 2


class ResumeUploadStep(SetupWizardStep):
    """Resume upload step"""
    id: str = "resume_upload"
    title: str = "Resume Upload"
    description: str = "Upload your resume for personalized job matching"
    required: bool = False
    
    resume_text: str = ""
    resume_file_name: str = ""


class SetupWizard:
    """Main setup wizard class"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.validator = APIKeyValidator()
        self.steps = self._initialize_steps()
        self.current_step = 0
    
    def _initialize_steps(self) -> List[SetupWizardStep]:
        """Initialize wizard steps"""
        return [
            APIKeysStep(),
            UserProfileStep(),
            JobPreferencesStep(),
            JobSourcesStep(),
            ResumeUploadStep()
        ]
    
    def get_step(self, step_id: str) -> Optional[SetupWizardStep]:
        """Get step by ID"""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def validate_step(self, step_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate step data"""
        step = self.get_step(step_id)
        if not step:
            return {"valid": False, "error": "Invalid step"}
        
        try:
            if step_id == "api_keys":
                return self._validate_api_keys(data)
            elif step_id == "user_profile":
                return self._validate_user_profile(data)
            elif step_id == "job_preferences":
                return self._validate_job_preferences(data)
            elif step_id == "job_sources":
                return self._validate_job_sources(data)
            elif step_id == "resume_upload":
                return self._validate_resume_upload(data)
            else:
                return {"valid": True}
                
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def _validate_api_keys(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate API keys step"""
        results = {"valid": True, "validations": {}}
        
        # Validate OpenAI key (required)
        openai_key = data.get("openai_key", "").strip()
        if not openai_key:
            results["valid"] = False
            results["validations"]["openai_key"] = {
                "valid": False,
                "error": "OpenAI API key is required",
                "solution": "Get an API key from https://platform.openai.com/api-keys"
            }
        else:
            openai_result = self.validator.validate_openai_key(openai_key)
            results["validations"]["openai_key"] = openai_result
            if not openai_result["valid"]:
                results["valid"] = False
        
        # Validate USAJobs key (optional)
        usajobs_key = data.get("usajobs_key", "").strip()
        if usajobs_key:
            results["validations"]["usajobs_key"] = self.validator.validate_usajobs_key(usajobs_key)
        
        return results
    
    def _validate_user_profile(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user profile step"""
        required_fields = ["name", "experience_level"]
        errors = {}
        
        for field in required_fields:
            if not data.get(field, "").strip():
                errors[field] = f"{field.replace('_', ' ').title()} is required"
        
        if errors:
            return {"valid": False, "errors": errors}
        
        return {"valid": True}
    
    def _validate_job_preferences(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate job preferences step"""
        errors = {}
        
        target_titles = data.get("target_titles", [])
        if not target_titles or len(target_titles) == 0:
            errors["target_titles"] = "At least one target job title is required"
        
        min_salary = data.get("min_salary")
        max_salary = data.get("max_salary")
        
        if min_salary and max_salary and min_salary > max_salary:
            errors["salary"] = "Minimum salary cannot be greater than maximum salary"
        
        if errors:
            return {"valid": False, "errors": errors}
        
        return {"valid": True}
    
    def _validate_job_sources(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate job sources step"""
        enabled_sources = data.get("enabled_sources", {})
        
        if not any(enabled_sources.values()):
            return {
                "valid": False,
                "errors": {"sources": "At least one job source must be enabled"}
            }
        
        return {"valid": True}
    
    def _validate_resume_upload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate resume upload step"""
        # Resume is optional
        return {"valid": True}
    
    def save_configuration(self, all_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save complete configuration"""
        try:
            # Create configuration structure
            config_data = self._build_config_data(all_data)
            
            # Save to YAML file
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
            
            # Save environment variables
            self._save_env_file(all_data)
            
            # Save resume file
            self._save_resume_file(all_data)
            
            return {
                "success": True,
                "message": "Configuration saved successfully!",
                "config_path": str(self.config_path),
                "next_steps": [
                    "Run 'python main.py' to start your first job search",
                    "Use 'python main.py --concurrent' for faster searches",
                    "Visit the dashboard at http://localhost:8000 to view results"
                ]
            }
            
        except Exception as e:
            logging.error(f"Error saving configuration: {e}")
            return {
                "success": False,
                "error": f"Failed to save configuration: {str(e)}"
            }
    
    def _build_config_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build configuration data structure"""
        api_keys = data.get("api_keys", {})
        profile = data.get("user_profile", {})
        preferences = data.get("job_preferences", {})
        sources = data.get("job_sources", {})
        
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "user": {
                "name": profile.get("name", ""),
                "email": profile.get("email", ""),
                "experience_level": profile.get("experience_level", "Mid-level"),
                "target_industry": profile.get("target_industry", ""),
                "current_location": profile.get("current_location", ""),
                "willing_to_relocate": profile.get("willing_to_relocate", False)
            },
            "jobs": {
                "target_titles": preferences.get("target_titles", []),
                "min_salary": preferences.get("min_salary"),
                "max_salary": preferences.get("max_salary"),
                "exclude_keywords": preferences.get("exclude_keywords", [])
            },
            "location": {
                "primary_locations": preferences.get("preferred_locations", []),
                "remote_ok": preferences.get("remote_ok", True)
            },
            "scraping": {
                "enabled_sources": [
                    name for name, enabled in sources.get("enabled_sources", {}).items()
                    if enabled
                ],
                "pages_per_source": sources.get("pages_per_source", 2),
                "base_delay": 2.0,
                "max_retries": 3
            },
            "analysis": {
                "enabled": True,
                "lazy_analysis": True,
                "score_threshold": 70,
                "llm_model": "gpt-3.5-turbo",
                "llm_temperature": 0.1,
                "batch_size": 10
            },
            "output": {
                "output_dir": "output",
                "log_level": "INFO"
            }
        }
    
    def _save_env_file(self, data: Dict[str, Any]) -> None:
        """Save environment variables to .env file"""
        api_keys = data.get("api_keys", {})
        
        env_content = "# Job Hunter API Keys\n"
        env_content += "# Generated by setup wizard\n\n"
        
        if api_keys.get("openai_key"):
            env_content += f"OPENAI_API_KEY={api_keys['openai_key']}\n"
        
        if api_keys.get("usajobs_key"):
            env_content += f"USAJOBS_API_KEY={api_keys['usajobs_key']}\n"
        
        if api_keys.get("adzuna_app_id"):
            env_content += f"ADZUNA_APP_ID={api_keys['adzuna_app_id']}\n"
        
        if api_keys.get("adzuna_app_key"):
            env_content += f"ADZUNA_APP_KEY={api_keys['adzuna_app_key']}\n"
        
        env_path = Path(".env")
        with open(env_path, 'w') as f:
            f.write(env_content)
    
    def _save_resume_file(self, data: Dict[str, Any]) -> None:
        """Save resume text to file"""
        resume_data = data.get("resume_upload", {})
        resume_text = resume_data.get("resume_text", "").strip()
        
        if resume_text:
            resume_path = Path("resume.txt")
            with open(resume_path, 'w', encoding='utf-8') as f:
                f.write(resume_text)
    
    def get_wizard_state(self) -> Dict[str, Any]:
        """Get current wizard state"""
        return {
            "steps": [
                {
                    "id": step.id,
                    "title": step.title,
                    "description": step.description,
                    "required": step.required,
                    "completed": step.completed
                }
                for step in self.steps
            ],
            "current_step": self.current_step,
            "total_steps": len(self.steps)
        }


class SetupWizardTemplates:
    """Predefined configuration templates"""
    
    @staticmethod
    def get_templates() -> Dict[str, Dict[str, Any]]:
        """Get predefined job search templates"""
        return {
            "software_engineer": {
                "name": "Software Engineer",
                "description": "For software developers and engineers",
                "job_preferences": {
                    "target_titles": [
                        "Software Engineer",
                        "Software Developer",
                        "Full Stack Developer",
                        "Backend Developer",
                        "Frontend Developer"
                    ],
                    "min_salary": 80000,
                    "exclude_keywords": ["intern", "unpaid", "volunteer"]
                },
                "job_sources": {
                    "enabled_sources": {
                        "LinkedIn": True,
                        "Indeed": True,
                        "Dice": True,
                        "ClearanceJobs": False,
                        "USAJobs": False,
                        "Adzuna": True
                    }
                }
            },
            "data_scientist": {
                "name": "Data Scientist",
                "description": "For data science and analytics roles",
                "job_preferences": {
                    "target_titles": [
                        "Data Scientist",
                        "Data Analyst",
                        "Machine Learning Engineer",
                        "Research Scientist",
                        "Business Intelligence Analyst"
                    ],
                    "min_salary": 90000,
                    "exclude_keywords": ["intern", "entry level"]
                },
                "job_sources": {
                    "enabled_sources": {
                        "LinkedIn": True,
                        "Indeed": True,
                        "Dice": True,
                        "ClearanceJobs": False,
                        "USAJobs": True,
                        "Adzuna": True
                    }
                }
            },
            "product_manager": {
                "name": "Product Manager",
                "description": "For product management roles",
                "job_preferences": {
                    "target_titles": [
                        "Product Manager",
                        "Senior Product Manager",
                        "Product Owner",
                        "Technical Product Manager",
                        "Associate Product Manager"
                    ],
                    "min_salary": 100000,
                    "exclude_keywords": ["intern", "coordinator"]
                },
                "job_sources": {
                    "enabled_sources": {
                        "LinkedIn": True,
                        "Indeed": True,
                        "Dice": False,
                        "ClearanceJobs": False,
                        "USAJobs": False,
                        "Adzuna": True
                    }
                }
            }
        }