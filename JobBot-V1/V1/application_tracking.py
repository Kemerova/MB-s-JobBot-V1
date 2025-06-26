"""
Job Application Tracking System
Comprehensive tracking of job applications with status management and analytics.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
from .models import Job
from .config import AppConfig


class ApplicationStatus(Enum):
    """Application status enum"""
    INTERESTED = "interested"
    APPLIED = "applied"
    PHONE_SCREEN = "phone_screen"
    INTERVIEWING = "interviewing"
    WAITING_RESPONSE = "waiting_response"
    REJECTED = "rejected"
    OFFER = "offer"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


@dataclass
class ApplicationEvent:
    """Individual event in application timeline"""
    timestamp: datetime
    event_type: str
    description: str
    notes: Optional[str] = None
    contact_person: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "description": self.description,
            "notes": self.notes,
            "contact_person": self.contact_person
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ApplicationEvent':
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=data["event_type"],
            description=data["description"],
            notes=data.get("notes"),
            contact_person=data.get("contact_person")
        )


@dataclass
class JobApplication:
    """Complete job application tracking record"""
    job_id: int
    job_title: str
    company: str
    location: str
    url: str
    source: str
    status: ApplicationStatus
    applied_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    salary_expectation: Optional[int] = None
    notes: str = ""
    contact_info: Dict[str, str] = None
    resume_version: Optional[str] = None
    cover_letter: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    interview_dates: List[datetime] = None
    rejection_feedback: Optional[str] = None
    offer_details: Dict[str, Any] = None
    events: List[ApplicationEvent] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.contact_info is None:
            self.contact_info = {}
        if self.interview_dates is None:
            self.interview_dates = []
        if self.events is None:
            self.events = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
        if self.offer_details is None:
            self.offer_details = {}
    
    def add_event(self, event_type: str, description: str, notes: Optional[str] = None, contact_person: Optional[str] = None):
        """Add an event to the application timeline"""
        event = ApplicationEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            description=description,
            notes=notes,
            contact_person=contact_person
        )
        self.events.append(event)
        self.updated_at = datetime.now()
    
    def update_status(self, new_status: ApplicationStatus, notes: Optional[str] = None):
        """Update application status and add timeline event"""
        old_status = self.status.value
        self.status = new_status
        self.updated_at = datetime.now()
        
        status_descriptions = {
            ApplicationStatus.INTERESTED: "Marked as interested",
            ApplicationStatus.APPLIED: "Application submitted",
            ApplicationStatus.PHONE_SCREEN: "Phone screen scheduled",
            ApplicationStatus.INTERVIEWING: "Interview process started",
            ApplicationStatus.WAITING_RESPONSE: "Waiting for response",
            ApplicationStatus.REJECTED: "Application rejected",
            ApplicationStatus.OFFER: "Offer received",
            ApplicationStatus.ACCEPTED: "Offer accepted",
            ApplicationStatus.DECLINED: "Offer declined",
            ApplicationStatus.WITHDRAWN: "Application withdrawn"
        }
        
        description = status_descriptions.get(new_status, f"Status changed to {new_status.value}")
        self.add_event("status_change", description, notes)
        
        # Set applied_date when status changes to applied
        if new_status == ApplicationStatus.APPLIED and not self.applied_date:
            self.applied_date = datetime.now()
    
    def add_interview(self, interview_date: datetime, notes: Optional[str] = None, contact_person: Optional[str] = None):
        """Add an interview to the application"""
        self.interview_dates.append(interview_date)
        self.add_event(
            "interview_scheduled",
            f"Interview scheduled for {interview_date.strftime('%Y-%m-%d %H:%M')}",
            notes,
            contact_person
        )
        
        # Update status if not already interviewing
        if self.status not in [ApplicationStatus.INTERVIEWING, ApplicationStatus.WAITING_RESPONSE, 
                               ApplicationStatus.OFFER, ApplicationStatus.ACCEPTED, ApplicationStatus.REJECTED]:
            self.update_status(ApplicationStatus.INTERVIEWING)
    
    def set_deadline(self, deadline: datetime, notes: Optional[str] = None):
        """Set application deadline"""
        self.deadline = deadline
        self.add_event(
            "deadline_set",
            f"Application deadline set for {deadline.strftime('%Y-%m-%d')}",
            notes
        )
    
    def set_follow_up(self, follow_up_date: datetime, notes: Optional[str] = None):
        """Set follow-up reminder date"""
        self.follow_up_date = follow_up_date
        self.add_event(
            "follow_up_scheduled",
            f"Follow-up scheduled for {follow_up_date.strftime('%Y-%m-%d')}",
            notes
        )
    
    def days_since_applied(self) -> Optional[int]:
        """Calculate days since application was submitted"""
        if self.applied_date:
            return (datetime.now() - self.applied_date).days
        return None
    
    def days_until_deadline(self) -> Optional[int]:
        """Calculate days until application deadline"""
        if self.deadline:
            return (self.deadline - datetime.now()).days
        return None
    
    def is_overdue(self) -> bool:
        """Check if follow-up is overdue"""
        if self.follow_up_date:
            return datetime.now() > self.follow_up_date
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "job_id": self.job_id,
            "job_title": self.job_title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "source": self.source,
            "status": self.status.value,
            "applied_date": self.applied_date.isoformat() if self.applied_date else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "salary_expectation": self.salary_expectation,
            "notes": self.notes,
            "contact_info": self.contact_info,
            "resume_version": self.resume_version,
            "cover_letter": self.cover_letter,
            "follow_up_date": self.follow_up_date.isoformat() if self.follow_up_date else None,
            "interview_dates": [d.isoformat() for d in self.interview_dates],
            "rejection_feedback": self.rejection_feedback,
            "offer_details": self.offer_details,
            "events": [event.to_dict() for event in self.events],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobApplication':
        """Create from dictionary"""
        return cls(
            job_id=data["job_id"],
            job_title=data["job_title"],
            company=data["company"],
            location=data["location"],
            url=data["url"],
            source=data["source"],
            status=ApplicationStatus(data["status"]),
            applied_date=datetime.fromisoformat(data["applied_date"]) if data.get("applied_date") else None,
            deadline=datetime.fromisoformat(data["deadline"]) if data.get("deadline") else None,
            salary_expectation=data.get("salary_expectation"),
            notes=data.get("notes", ""),
            contact_info=data.get("contact_info", {}),
            resume_version=data.get("resume_version"),
            cover_letter=data.get("cover_letter"),
            follow_up_date=datetime.fromisoformat(data["follow_up_date"]) if data.get("follow_up_date") else None,
            interview_dates=[datetime.fromisoformat(d) for d in data.get("interview_dates", [])],
            rejection_feedback=data.get("rejection_feedback"),
            offer_details=data.get("offer_details", {}),
            events=[ApplicationEvent.from_dict(e) for e in data.get("events", [])],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )


class ApplicationTracker:
    """Main application tracking manager"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.applications_file = Path(config.output_dir) / "job_applications.json"
        self.applications_file.parent.mkdir(parents=True, exist_ok=True)
        self.applications: Dict[int, JobApplication] = {}
        self.load_applications()
    
    def load_applications(self) -> None:
        """Load applications from file"""
        try:
            if self.applications_file.exists():
                with open(self.applications_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for app_data in data:
                    app = JobApplication.from_dict(app_data)
                    self.applications[app.job_id] = app
                
                logging.info(f"Loaded {len(self.applications)} job applications")
        except Exception as e:
            logging.error(f"Error loading applications: {e}")
            self.applications = {}
    
    def save_applications(self) -> None:
        """Save applications to file"""
        try:
            data = [app.to_dict() for app in self.applications.values()]
            with open(self.applications_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logging.debug(f"Saved {len(self.applications)} job applications")
        except Exception as e:
            logging.error(f"Error saving applications: {e}")
    
    def create_application(self, job: Job, status: ApplicationStatus = ApplicationStatus.INTERESTED) -> JobApplication:
        """Create new application from job"""
        application = JobApplication(
            job_id=job.id,
            job_title=job.title,
            company=job.company,
            location=job.location,
            url=job.url,
            source=job.source.name if job.source else "Unknown",
            status=status
        )
        
        application.add_event("created", f"Application created for {job.title} at {job.company}")
        
        self.applications[job.id] = application
        self.save_applications()
        
        logging.info(f"Created application for {job.title} at {job.company}")
        return application
    
    def get_application(self, job_id: int) -> Optional[JobApplication]:
        """Get application by job ID"""
        return self.applications.get(job_id)
    
    def update_application_status(self, job_id: int, status: ApplicationStatus, notes: Optional[str] = None) -> bool:
        """Update application status"""
        app = self.get_application(job_id)
        if app:
            app.update_status(status, notes)
            self.save_applications()
            return True
        return False
    
    def add_interview(self, job_id: int, interview_date: datetime, notes: Optional[str] = None, contact_person: Optional[str] = None) -> bool:
        """Add interview to application"""
        app = self.get_application(job_id)
        if app:
            app.add_interview(interview_date, notes, contact_person)
            self.save_applications()
            return True
        return False
    
    def set_deadline(self, job_id: int, deadline: datetime, notes: Optional[str] = None) -> bool:
        """Set application deadline"""
        app = self.get_application(job_id)
        if app:
            app.set_deadline(deadline, notes)
            self.save_applications()
            return True
        return False
    
    def add_notes(self, job_id: int, notes: str) -> bool:
        """Add notes to application"""
        app = self.get_application(job_id)
        if app:
            app.notes = notes
            app.updated_at = datetime.now()
            app.add_event("notes_updated", "Application notes updated", notes)
            self.save_applications()
            return True
        return False
    
    def get_applications_by_status(self, status: ApplicationStatus) -> List[JobApplication]:
        """Get all applications with specific status"""
        return [app for app in self.applications.values() if app.status == status]
    
    def get_active_applications(self) -> List[JobApplication]:
        """Get applications that are still active (not rejected, withdrawn, or accepted)"""
        active_statuses = [
            ApplicationStatus.INTERESTED,
            ApplicationStatus.APPLIED,
            ApplicationStatus.PHONE_SCREEN,
            ApplicationStatus.INTERVIEWING,
            ApplicationStatus.WAITING_RESPONSE,
            ApplicationStatus.OFFER
        ]
        return [app for app in self.applications.values() if app.status in active_statuses]
    
    def get_overdue_followups(self) -> List[JobApplication]:
        """Get applications with overdue follow-ups"""
        return [app for app in self.applications.values() if app.is_overdue()]
    
    def get_upcoming_interviews(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Get upcoming interviews within specified days"""
        upcoming = []
        cutoff_date = datetime.now() + timedelta(days=days_ahead)
        
        for app in self.applications.values():
            for interview_date in app.interview_dates:
                if datetime.now() <= interview_date <= cutoff_date:
                    upcoming.append({
                        "application": app,
                        "interview_date": interview_date,
                        "days_until": (interview_date - datetime.now()).days
                    })
        
        return sorted(upcoming, key=lambda x: x["interview_date"])
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive application statistics"""
        total_apps = len(self.applications)
        
        if total_apps == 0:
            return {
                "total_applications": 0,
                "status_breakdown": {},
                "success_rate": 0,
                "average_response_time": None,
                "upcoming_interviews": 0,
                "overdue_followups": 0
            }
        
        # Status breakdown
        status_counts = {}
        for status in ApplicationStatus:
            status_counts[status.value] = len(self.get_applications_by_status(status))
        
        # Success metrics
        offers = status_counts.get(ApplicationStatus.OFFER.value, 0)
        accepted = status_counts.get(ApplicationStatus.ACCEPTED.value, 0)
        success_rate = ((offers + accepted) / total_apps) * 100 if total_apps > 0 else 0
        
        # Response time calculation
        response_times = []
        for app in self.applications.values():
            if app.applied_date and app.status not in [ApplicationStatus.INTERESTED, ApplicationStatus.APPLIED]:
                # Find first response event after application
                for event in app.events:
                    if event.timestamp > app.applied_date and event.event_type == "status_change":
                        response_times.append((event.timestamp - app.applied_date).days)
                        break
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else None
        
        return {
            "total_applications": total_apps,
            "status_breakdown": status_counts,
            "success_rate": round(success_rate, 1),
            "average_response_time": round(avg_response_time, 1) if avg_response_time else None,
            "upcoming_interviews": len(self.get_upcoming_interviews()),
            "overdue_followups": len(self.get_overdue_followups()),
            "active_applications": len(self.get_active_applications())
        }
    
    def export_applications(self, format: str = "csv") -> Optional[Path]:
        """Export applications to specified format"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if format.lower() == "csv":
                import csv
                export_file = Path(self.config.output_dir) / f"job_applications_{timestamp}.csv"
                
                with open(export_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    # Headers
                    headers = [
                        "Job Title", "Company", "Location", "Status", "Applied Date",
                        "Days Since Applied", "Deadline", "Days Until Deadline",
                        "Salary Expectation", "Source", "Interview Count", 
                        "Last Updated", "Notes", "URL"
                    ]
                    writer.writerow(headers)
                    
                    # Data rows
                    for app in sorted(self.applications.values(), key=lambda x: x.updated_at, reverse=True):
                        writer.writerow([
                            app.job_title,
                            app.company,
                            app.location,
                            app.status.value,
                            app.applied_date.strftime("%Y-%m-%d") if app.applied_date else "",
                            app.days_since_applied() or "",
                            app.deadline.strftime("%Y-%m-%d") if app.deadline else "",
                            app.days_until_deadline() or "",
                            app.salary_expectation or "",
                            app.source,
                            len(app.interview_dates),
                            app.updated_at.strftime("%Y-%m-%d %H:%M"),
                            app.notes,
                            app.url
                        ])
                
            elif format.lower() == "json":
                export_file = Path(self.config.output_dir) / f"job_applications_{timestamp}.json"
                
                with open(export_file, 'w', encoding='utf-8') as f:
                    data = [app.to_dict() for app in self.applications.values()]
                    json.dump(data, f, indent=2)
            
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            logging.info(f"Exported {len(self.applications)} applications to {export_file}")
            return export_file
            
        except Exception as e:
            logging.error(f"Error exporting applications: {e}")
            return None
    
    def delete_application(self, job_id: int) -> bool:
        """Delete application"""
        if job_id in self.applications:
            app = self.applications[job_id]
            del self.applications[job_id]
            self.save_applications()
            logging.info(f"Deleted application for {app.job_title} at {app.company}")
            return True
        return False