# V1/models.py - Enhanced models with starring support
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional
import hashlib

class JobSource(Enum):
    LINKEDIN = "LinkedIn"
    INDEED = "Indeed"
    DICE = "Dice"
    CLEARANCEJOBS = "ClearanceJobs"
    ZIPRECRUITER = "ZipRecruiter"
    MANUAL = "Manual"
    API = "API"
    USAJOBS = "USAJobs"
    ADZUNA = "Adzuna"

class Priority(Enum):
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"

@dataclass
class Job:
    title: str
    company: str
    location: str
    source: JobSource
    url: Optional[str] = None
    salary: Optional[str] = None
    description: Optional[str] = None
    scraped_at: datetime = field(default_factory=datetime.now)
    search_keywords: Optional[str] = None
    
    # Analysis results
    score: int = 0
    score_breakdown: Dict[str, int] = field(default_factory=dict)
    score_rationale: str = ""
    tailored_bullets: List[str] = field(default_factory=list)
    priority: Priority = Priority.NORMAL
    analyzed_at: Optional[datetime] = None
    
    # Enhanced fields
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    posted_date: Optional[datetime] = None
    expires_date: Optional[datetime] = None
    job_type: Optional[str] = None
    remote_friendly: bool = False
    clearance_required: Optional[str] = None
    
    # NEW: Starring functionality
    starred: bool = False
    starred_at: Optional[datetime] = None
    starred_notes: Optional[str] = None  # User notes about why they starred it
    
    def make_unique_key(self) -> str:
        """Generate unique key for deduplication"""
        return f"{self.title.lower().strip()}-{self.company.lower().strip()}-{self.location[:20]}"
    
    def star_job(self, notes: Optional[str] = None):
        """Mark job as starred"""
        self.starred = True
        self.starred_at = datetime.now()
        self.starred_notes = notes
    
    def unstar_job(self):
        """Remove star from job"""
        self.starred = False
        self.starred_at = None
        self.starred_notes = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary with proper datetime handling"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif key == 'source':
                data[key] = value.value if hasattr(value, 'value') else str(value)
            elif key == 'priority':
                data[key] = value.value if hasattr(value, 'value') else str(value)
        return data
    
    def get_truncated_description(self, max_length: int = 200) -> str:
        """Get truncated description for UI display"""
        if not self.description:
            return "No description available"
        
        if len(self.description) <= max_length:
            return self.description
        
        return self.description[:max_length].rsplit(' ', 1)[0] + "..."