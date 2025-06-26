# V1/dashboard.py - Enhanced Dashboard API with pagination functionality
"""
V1/dashboard.py - FastAPI Server for Interactive Job Dashboard
- Serves dashboard and static files
- Provides /api/generate_bullets endpoint for AI resume bullets
- Starring functionality endpoints
- NEW: Pagination functionality endpoints
"""

import os
import json
import logging
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict
import uvicorn

from V1.config import ConfigManager
from V1.analyzer import JobAnalyzer
from V1.models import Job
from V1.setup_wizard import SetupWizard, SetupWizardTemplates
from V1.application_tracking import ApplicationTracker, ApplicationStatus


class BulletsRequest(BaseModel):
    job_id: int

class StarJobRequest(BaseModel):
    job_id: int
    notes: Optional[str] = None

class UnstarJobRequest(BaseModel):
    job_id: int

class UpdateNotesRequest(BaseModel):
    job_id: int
    notes: str

class PaginationRequest(BaseModel):
    page: int = 1
    page_size: Optional[int] = None
    filters: Optional[Dict] = None

class ApplicationRequest(BaseModel):
    job_id: int
    status: str
    notes: Optional[str] = None

class InterviewRequest(BaseModel):
    job_id: int
    interview_date: str
    notes: Optional[str] = None
    contact_person: Optional[str] = None

class DeadlineRequest(BaseModel):
    job_id: int
    deadline: str
    notes: Optional[str] = None


class DashboardServer:
    def __init__(self, config_path="config.yaml"):
        # Load config and files here to share across requests
        self.config = ConfigManager(config_path).load_config()
        self.output_dir = Path(self.config.output_dir)
        self.dashboard_file = self.output_dir / "job_dashboard.html"
        self.jobs_data_file = self.output_dir / "jobs_data.json"
        
        # Initialize managers
        self.starred_manager = StarredJobsManager(self.config)
        self.pagination_manager = PaginationManager(self.config, page_size=20)
        self.setup_wizard = SetupWizard(config_path)
        self.application_tracker = ApplicationTracker(self.config)
        
        # Load jobs into pagination on startup
        self._initialize_pagination()
        
        self.app = FastAPI(title="Job Dashboard API", docs_url="/docs", redoc_url=None)

        # Serve static files (dashboard, jobs_data.json)
        self.app.mount("/output", StaticFiles(directory=self.output_dir), name="output")

        # Serve dashboard HTML at root
        @self.app.get("/", response_class=FileResponse)
        async def serve_dashboard():
            return self.dashboard_file

        # Serve jobs_data.json (for debugging or direct access)
        @self.app.get("/jobs_data.json", response_class=FileResponse)
        async def serve_jobs_data():
            return self.jobs_data_file

        # POST /api/generate_bullets
        @self.app.post("/api/generate_bullets")
        async def generate_bullets(req: BulletsRequest):
            job_id = req.job_id
            # Load the jobs data
            if not self.jobs_data_file.exists():
                logging.error("jobs_data.json not found.")
                raise HTTPException(status_code=404, detail="Job data not found.")
            with open(self.jobs_data_file, "r", encoding="utf-8") as f:
                jobs = json.load(f)
            try:
                job = next(j for j in jobs if j["id"] == job_id)
            except StopIteration:
                logging.error(f"Job ID {job_id} not found in jobs_data.json")
                raise HTTPException(status_code=404, detail="Job not found.")

            # If already generated, return cached bullets
            if job.get("has_bullets") and job.get("bullets"):
                return {"success": True, "bullets": job["bullets"]}

            # Use JobAnalyzer to generate bullets (loads config/resume)
            try:
                analyzer = JobAnalyzer(self.config)
                # The analyzer expects a Job object, so mimic as needed:
                job_obj = self._dict_to_job_object(job)
                bullets = analyzer.generate_bullets(job_obj)
                # Optionally, update jobs_data.json with the new bullets for caching
                job["bullets"] = bullets
                job["has_bullets"] = True
                # Write back to file (best effort, ignore errors)
                try:
                    with open(self.jobs_data_file, "w", encoding="utf-8") as f:
                        json.dump(jobs, f, indent=2)
                except Exception:
                    pass
                return {"success": True, "bullets": bullets}
            except Exception as e:
                logging.exception(f"Failed to generate bullets: {e}")
                return {"success": False, "message": str(e)}

        # STARRING ENDPOINTS

        @self.app.post("/api/star_job")
        async def star_job(req: StarJobRequest):
            try:
                # Load jobs data
                if not self.jobs_data_file.exists():
                    raise HTTPException(status_code=404, detail="Job data not found.")
                
                with open(self.jobs_data_file, "r", encoding="utf-8") as f:
                    jobs_data = json.load(f)
                
                # Find the job
                job_data = next((j for j in jobs_data if j["id"] == req.job_id), None)
                if not job_data:
                    raise HTTPException(status_code=404, detail="Job not found.")
                
                # Convert to Job object
                job_obj = self._dict_to_job_object(job_data)
                
                # Star the job
                success = self.starred_manager.star_job(job_obj, req.notes)
                
                if success:
                    # Update the jobs_data.json to reflect starred status
                    job_data["starred"] = True
                    job_data["starred_at"] = job_obj.starred_at.isoformat() if job_obj.starred_at else None
                    job_data["starred_notes"] = req.notes
                    
                    # Save updated jobs data
                    try:
                        with open(self.jobs_data_file, "w", encoding="utf-8") as f:
                            json.dump(jobs_data, f, indent=2)
                        # Refresh pagination cache
                        self._refresh_pagination_cache()
                    except Exception as e:
                        logging.warning(f"Failed to update jobs_data.json: {e}")
                    
                    return {"success": True, "message": "Job starred successfully"}
                else:
                    return {"success": False, "message": "Job already starred or error occurred"}
                    
            except HTTPException:
                raise
            except Exception as e:
                logging.exception(f"Failed to star job: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/unstar_job")
        async def unstar_job(req: UnstarJobRequest):
            try:
                # Load jobs data
                if not self.jobs_data_file.exists():
                    raise HTTPException(status_code=404, detail="Job data not found.")
                
                with open(self.jobs_data_file, "r", encoding="utf-8") as f:
                    jobs_data = json.load(f)
                
                # Find the job
                job_data = next((j for j in jobs_data if j["id"] == req.job_id), None)
                if not job_data:
                    raise HTTPException(status_code=404, detail="Job not found.")
                
                # Convert to Job object
                job_obj = self._dict_to_job_object(job_data)
                
                # Unstar the job
                success = self.starred_manager.unstar_job(job_obj)
                
                if success:
                    # Update the jobs_data.json
                    job_data["starred"] = False
                    job_data["starred_at"] = None
                    job_data["starred_notes"] = None
                    
                    # Save updated jobs data
                    try:
                        with open(self.jobs_data_file, "w", encoding="utf-8") as f:
                            json.dump(jobs_data, f, indent=2)
                        # Refresh pagination cache
                        self._refresh_pagination_cache()
                    except Exception as e:
                        logging.warning(f"Failed to update jobs_data.json: {e}")
                    
                    return {"success": True, "message": "Job unstarred successfully"}
                else:
                    return {"success": False, "message": "Job not starred or error occurred"}
                    
            except HTTPException:
                raise
            except Exception as e:
                logging.exception(f"Failed to unstar job: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/starred_jobs")
        async def get_starred_jobs():
            try:
                starred_jobs = self.starred_manager.get_starred_jobs()
                return {"success": True, "starred_jobs": starred_jobs}
            except Exception as e:
                logging.exception(f"Failed to get starred jobs: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/update_starred_notes")
        async def update_starred_notes(req: UpdateNotesRequest):
            try:
                # Load jobs data to get job object
                if not self.jobs_data_file.exists():
                    raise HTTPException(status_code=404, detail="Job data not found.")
                
                with open(self.jobs_data_file, "r", encoding="utf-8") as f:
                    jobs_data = json.load(f)
                
                job_data = next((j for j in jobs_data if j["id"] == req.job_id), None)
                if not job_data:
                    raise HTTPException(status_code=404, detail="Job not found.")
                
                job_obj = self._dict_to_job_object(job_data)
                
                success = self.starred_manager.update_starred_job_notes(job_obj, req.notes)
                
                if success:
                    # Update jobs_data.json
                    job_data["starred_notes"] = req.notes
                    
                    try:
                        with open(self.jobs_data_file, "w", encoding="utf-8") as f:
                            json.dump(jobs_data, f, indent=2)
                        # Refresh pagination cache
                        self._refresh_pagination_cache()
                    except Exception as e:
                        logging.warning(f"Failed to update jobs_data.json: {e}")
                    
                    return {"success": True, "message": "Notes updated successfully"}
                else:
                    return {"success": False, "message": "Failed to update notes or job not starred"}
                    
            except HTTPException:
                raise
            except Exception as e:
                logging.exception(f"Failed to update starred notes: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/starred_stats")
        async def get_starred_stats():
            try:
                stats = self.starred_manager.get_stats()
                return {"success": True, "stats": stats}
            except Exception as e:
                logging.exception(f"Failed to get starred stats: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/export_starred/{format}")
        async def export_starred_jobs(format: str):
            try:
                if format not in ['csv', 'json']:
                    raise HTTPException(status_code=400, detail="Format must be 'csv' or 'json'")
                
                export_path = self.starred_manager.export_starred_jobs(format)
                
                if export_path:
                    return FileResponse(
                        export_path,
                        filename=Path(export_path).name,
                        media_type='application/octet-stream'
                    )
                else:
                    raise HTTPException(status_code=404, detail="No starred jobs to export")
                    
            except HTTPException:
                raise
            except Exception as e:
                logging.exception(f"Failed to export starred jobs: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # NEW: PAGINATION ENDPOINTS

        @self.app.get("/api/jobs/page/{page}")
        async def get_jobs_page(
            page: int = 1,
            page_size: int = Query(20, ge=1, le=100),
            priority: Optional[str] = Query(None),
            source: Optional[str] = Query(None),
            remote: Optional[str] = Query(None),
            search: Optional[str] = Query(None)
        ):
            """Get a specific page of jobs with optional filtering"""
            try:
                # Build filters dictionary
                filters = {}
                if priority and priority != 'all':
                    filters['priority'] = priority
                if source and source != 'all':
                    filters['source'] = source
                if remote and remote != 'all':
                    filters['remote'] = remote
                if search:
                    filters['search'] = search
                
                # Update page size if different from default
                if page_size != self.pagination_manager.page_size:
                    self.pagination_manager.update_page_size(page_size)
                
                # Get page data
                jobs_data, pagination_info = self.pagination_manager.get_page(page, filters)
                
                return {
                    "success": True,
                    "jobs": jobs_data,
                    "pagination": {
                        "current_page": pagination_info.current_page,
                        "total_pages": pagination_info.total_pages,
                        "page_size": pagination_info.page_size,
                        "total_items": pagination_info.total_items,
                        "has_next": pagination_info.has_next,
                        "has_previous": pagination_info.has_previous,
                        "start_index": pagination_info.start_index,
                        "end_index": pagination_info.end_index
                    }
                }
                
            except Exception as e:
                logging.exception(f"Failed to get jobs page {page}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/jobs/next/{current_page}")
        async def get_next_page(
            current_page: int,
            priority: Optional[str] = Query(None),
            source: Optional[str] = Query(None),
            remote: Optional[str] = Query(None),
            search: Optional[str] = Query(None)
        ):
            """Get the next page of jobs"""
            return await get_jobs_page(
                current_page + 1, 
                self.pagination_manager.page_size,
                priority, source, remote, search
            )

        @self.app.get("/api/jobs/previous/{current_page}")
        async def get_previous_page(
            current_page: int,
            priority: Optional[str] = Query(None),
            source: Optional[str] = Query(None),
            remote: Optional[str] = Query(None),
            search: Optional[str] = Query(None)
        ):
            """Get the previous page of jobs"""
            return await get_jobs_page(
                current_page - 1, 
                self.pagination_manager.page_size,
                priority, source, remote, search
            )

        @self.app.get("/api/pagination/stats")
        async def get_pagination_stats():
            """Get pagination statistics"""
            try:
                stats = self.pagination_manager.get_pagination_stats()
                return {"success": True, "stats": stats}
            except Exception as e:
                logging.exception(f"Failed to get pagination stats: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/pagination/refresh")
        async def refresh_pagination():
            """Refresh pagination cache from current jobs data"""
            try:
                self._refresh_pagination_cache()
                stats = self.pagination_manager.get_pagination_stats()
                return {"success": True, "message": "Pagination cache refreshed", "stats": stats}
            except Exception as e:
                logging.exception(f"Failed to refresh pagination: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/pagination/page_size/{new_size}")
        async def update_page_size(new_size: int):
            """Update pagination page size"""
            try:
                if new_size < 1 or new_size > 100:
                    raise HTTPException(status_code=400, detail="Page size must be between 1 and 100")
                
                self.pagination_manager.update_page_size(new_size)
                return {"success": True, "message": f"Page size updated to {new_size}"}
            except HTTPException:
                raise
            except Exception as e:
                logging.exception(f"Failed to update page size: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def _initialize_pagination(self):
        """Initialize pagination with existing jobs data"""
        try:
            if self.jobs_data_file.exists():
                with open(self.jobs_data_file, "r", encoding="utf-8") as f:
                    jobs_data = json.load(f)
                
                # Convert to Job objects
                jobs = [self._dict_to_job_object(job_data) for job_data in jobs_data]
                
                # Load into pagination manager
                total_loaded = self.pagination_manager.load_jobs_for_pagination(jobs)
                logging.info(f"Pagination initialized with {total_loaded} jobs")
            else:
                logging.warning("No jobs data file found for pagination initialization")
                
        except Exception as e:
            logging.warning(f"Failed to initialize pagination: {e}")
    
    def _refresh_pagination_cache(self):
        """Refresh pagination cache from current jobs data"""
        try:
            if self.jobs_data_file.exists():
                with open(self.jobs_data_file, "r", encoding="utf-8") as f:
                    jobs_data = json.load(f)
                
                # Convert to Job objects
                jobs = [self._dict_to_job_object(job_data) for job_data in jobs_data]
                
                # Refresh pagination cache
                self.pagination_manager.refresh_cache(jobs)
                logging.info("Pagination cache refreshed")
            
        except Exception as e:
            logging.warning(f"Failed to refresh pagination cache: {e}")

    def _dict_to_job_object(self, job_data: dict) -> Job:
        """Convert job dictionary back to Job object"""
        from .models import JobSource, Priority
        
        # Handle source enum
        source = JobSource.MANUAL
        try:
            source = JobSource(job_data.get("source", "Manual"))
        except ValueError:
            source = JobSource.MANUAL
        
        # Handle priority enum
        priority = Priority.NORMAL
        try:
            priority = Priority(job_data.get("priority", "NORMAL"))
        except ValueError:
            priority = Priority.NORMAL
        
        return Job(
            title=job_data["title"],
            company=job_data["company"],
            location=job_data["location"],
            source=source,
            url=job_data.get("url"),
            salary=job_data.get("salary"),
            description=job_data.get("full_description") or job_data.get("description"),
            salary_min=job_data.get("salary_min"),
            salary_max=job_data.get("salary_max"),
            score=job_data.get("score", 0),
            priority=priority,
            remote_friendly=job_data.get("remote_friendly", False),
            clearance_required=job_data.get("clearance_required"),
            job_type=job_data.get("job_type"),
            search_keywords=job_data.get("search_keywords"),
            starred=job_data.get("starred", False),
            starred_notes=job_data.get("starred_notes")
        )

        # SETUP WIZARD ENDPOINTS
        
        @self.app.get("/setup")
        async def serve_setup_wizard():
            """Serve setup wizard page"""
            return FileResponse("V1/templates/setup_wizard.html")
        
        @self.app.get("/api/setup/state")
        async def get_setup_state():
            """Get current setup wizard state"""
            try:
                return self.setup_wizard.get_wizard_state()
            except Exception as e:
                logging.exception(f"Failed to get setup state: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/setup/templates")
        async def get_setup_templates():
            """Get predefined configuration templates"""
            try:
                return SetupWizardTemplates.get_templates()
            except Exception as e:
                logging.exception(f"Failed to get templates: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/setup/validate/{step_id}")
        async def validate_setup_step(step_id: str, data: Dict[str, Any]):
            """Validate a setup wizard step"""
            try:
                result = self.setup_wizard.validate_step(step_id, data)
                return result
            except Exception as e:
                logging.exception(f"Failed to validate step {step_id}: {e}")
                return {"valid": False, "error": str(e)}
        
        @self.app.post("/api/setup/save")
        async def save_setup_configuration(data: Dict[str, Any]):
            """Save complete setup configuration"""
            try:
                result = self.setup_wizard.save_configuration(data)
                return result
            except Exception as e:
                logging.exception(f"Failed to save configuration: {e}")
                return {"success": False, "error": str(e)}

        # APPLICATION TRACKING ENDPOINTS
        
        @self.app.post("/api/applications/create")
        async def create_application(req: ApplicationRequest):
            """Create new job application"""
            try:
                # Load jobs data to get job details
                if not self.jobs_data_file.exists():
                    raise HTTPException(status_code=404, detail="Job data not found.")
                
                with open(self.jobs_data_file, "r", encoding="utf-8") as f:
                    jobs_data = json.load(f)
                
                # Find the job
                job_data = next((j for j in jobs_data if j["id"] == req.job_id), None)
                if not job_data:
                    raise HTTPException(status_code=404, detail="Job not found.")
                
                # Convert to Job object
                job_obj = self._dict_to_job_object(job_data)
                
                # Create application
                status = ApplicationStatus(req.status)
                application = self.application_tracker.create_application(job_obj, status)
                
                if req.notes:
                    self.application_tracker.add_notes(req.job_id, req.notes)
                
                return {"success": True, "application_id": application.job_id}
                
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid status: {str(e)}")
            except Exception as e:
                logging.exception(f"Failed to create application: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/applications")
        async def get_applications():
            """Get all job applications"""
            try:
                applications = list(self.application_tracker.applications.values())
                return {
                    "success": True,
                    "applications": [app.to_dict() for app in applications]
                }
            except Exception as e:
                logging.exception(f"Failed to get applications: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/applications/{job_id}")
        async def get_application(job_id: int):
            """Get specific application"""
            try:
                application = self.application_tracker.get_application(job_id)
                if not application:
                    raise HTTPException(status_code=404, detail="Application not found.")
                
                return {"success": True, "application": application.to_dict()}
            except HTTPException:
                raise
            except Exception as e:
                logging.exception(f"Failed to get application: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.put("/api/applications/{job_id}/status")
        async def update_application_status(job_id: int, req: ApplicationRequest):
            """Update application status"""
            try:
                status = ApplicationStatus(req.status)
                success = self.application_tracker.update_application_status(job_id, status, req.notes)
                
                if success:
                    return {"success": True, "message": "Status updated successfully"}
                else:
                    raise HTTPException(status_code=404, detail="Application not found.")
                    
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid status: {str(e)}")
            except HTTPException:
                raise
            except Exception as e:
                logging.exception(f"Failed to update application status: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/applications/{job_id}/interview")
        async def add_interview(job_id: int, req: InterviewRequest):
            """Add interview to application"""
            try:
                from datetime import datetime
                interview_date = datetime.fromisoformat(req.interview_date)
                
                success = self.application_tracker.add_interview(
                    job_id, interview_date, req.notes, req.contact_person
                )
                
                if success:
                    return {"success": True, "message": "Interview added successfully"}
                else:
                    raise HTTPException(status_code=404, detail="Application not found.")
                    
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
            except HTTPException:
                raise
            except Exception as e:
                logging.exception(f"Failed to add interview: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/applications/{job_id}/deadline")
        async def set_deadline(job_id: int, req: DeadlineRequest):
            """Set application deadline"""
            try:
                from datetime import datetime
                deadline = datetime.fromisoformat(req.deadline)
                
                success = self.application_tracker.set_deadline(job_id, deadline, req.notes)
                
                if success:
                    return {"success": True, "message": "Deadline set successfully"}
                else:
                    raise HTTPException(status_code=404, detail="Application not found.")
                    
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
            except HTTPException:
                raise
            except Exception as e:
                logging.exception(f"Failed to set deadline: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/applications/statistics")
        async def get_application_statistics():
            """Get application statistics"""
            try:
                stats = self.application_tracker.get_statistics()
                return {"success": True, "statistics": stats}
            except Exception as e:
                logging.exception(f"Failed to get application statistics: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/applications/upcoming-interviews")
        async def get_upcoming_interviews():
            """Get upcoming interviews"""
            try:
                interviews = self.application_tracker.get_upcoming_interviews()
                return {
                    "success": True,
                    "interviews": [
                        {
                            "job_title": item["application"].job_title,
                            "company": item["application"].company,
                            "interview_date": item["interview_date"].isoformat(),
                            "days_until": item["days_until"]
                        }
                        for item in interviews
                    ]
                }
            except Exception as e:
                logging.exception(f"Failed to get upcoming interviews: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/applications/overdue")
        async def get_overdue_followups():
            """Get overdue follow-ups"""
            try:
                overdue = self.application_tracker.get_overdue_followups()
                return {
                    "success": True,
                    "overdue": [app.to_dict() for app in overdue]
                }
            except Exception as e:
                logging.exception(f"Failed to get overdue follow-ups: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/applications/export/{format}")
        async def export_applications(format: str):
            """Export applications"""
            try:
                export_path = self.application_tracker.export_applications(format)
                
                if export_path and export_path.exists():
                    return FileResponse(
                        path=str(export_path),
                        filename=export_path.name,
                        media_type='application/octet-stream'
                    )
                else:
                    raise HTTPException(status_code=404, detail="No applications to export")
                    
            except Exception as e:
                logging.exception(f"Failed to export applications: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/api/applications/{job_id}")
        async def delete_application(job_id: int):
            """Delete application"""
            try:
                success = self.application_tracker.delete_application(job_id)
                
                if success:
                    return {"success": True, "message": "Application deleted successfully"}
                else:
                    raise HTTPException(status_code=404, detail="Application not found.")
                    
            except HTTPException:
                raise
            except Exception as e:
                logging.exception(f"Failed to delete application: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def start_server(self, host="127.0.0.1", port=8000):
        # Run the app using uvicorn
        uvicorn.run(self.app, host=host, port=port, reload=False)


def create_server(config_path="config.yaml"):
    return DashboardServer(config_path)