"""
Starred Jobs Management
Handles starring/unstarring jobs and persisting starred job data.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from .models import Job
from .config import AppConfig


class StarredJobsManager:
    """Manages starred jobs functionality"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.starred_file = Path(config.output_dir) / "starred_jobs.json"
        self.starred_file.parent.mkdir(parents=True, exist_ok=True)
    
    def star_job(self, job: Job, notes: Optional[str] = None) -> bool:
        """Star a job with optional notes"""
        try:
            starred_jobs = self._load_starred_jobs()
            
            # Check if already starred
            if any(j["id"] == job.id for j in starred_jobs):
                return False
            
            # Mark job as starred
            job.mark_starred(notes)
            
            # Add to starred jobs
            starred_job_data = {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "starred_at": job.starred_at.isoformat() if job.starred_at else datetime.now().isoformat(),
                "starred_notes": notes,
                "source": job.source.name if job.source else "Unknown",
                "score": getattr(job, 'score', 0)
            }
            
            starred_jobs.append(starred_job_data)
            self._save_starred_jobs(starred_jobs)
            
            logging.info(f"Starred job: {job.title} at {job.company}")
            return True
            
        except Exception as e:
            logging.error(f"Error starring job: {e}")
            return False
    
    def unstar_job(self, job: Job) -> bool:
        """Unstar a job"""
        try:
            starred_jobs = self._load_starred_jobs()
            
            # Remove from starred jobs
            starred_jobs = [j for j in starred_jobs if j["id"] != job.id]
            self._save_starred_jobs(starred_jobs)
            
            # Update job object
            job.unstar()
            
            logging.info(f"Unstarred job: {job.title} at {job.company}")
            return True
            
        except Exception as e:
            logging.error(f"Error unstarring job: {e}")
            return False
    
    def get_starred_jobs(self) -> List[Dict[str, Any]]:
        """Get all starred jobs"""
        return self._load_starred_jobs()
    
    def update_starred_job_notes(self, job: Job, notes: str) -> bool:
        """Update notes for a starred job"""
        try:
            starred_jobs = self._load_starred_jobs()
            
            for starred_job in starred_jobs:
                if starred_job["id"] == job.id:
                    starred_job["starred_notes"] = notes
                    self._save_starred_jobs(starred_jobs)
                    job.starred_notes = notes
                    logging.info(f"Updated notes for starred job: {job.title}")
                    return True
            
            return False
            
        except Exception as e:
            logging.error(f"Error updating starred job notes: {e}")
            return False
    
    def mark_jobs_starred_status(self, jobs: List[Job]) -> None:
        """Mark jobs with their starred status from saved data"""
        try:
            starred_jobs = self._load_starred_jobs()
            starred_ids = {j["id"] for j in starred_jobs}
            starred_dict = {j["id"]: j for j in starred_jobs}
            
            for job in jobs:
                if job.id in starred_ids:
                    starred_data = starred_dict[job.id]
                    job.starred = True
                    job.starred_notes = starred_data.get("starred_notes")
                    if starred_data.get("starred_at"):
                        job.starred_at = datetime.fromisoformat(starred_data["starred_at"])
                        
        except Exception as e:
            logging.warning(f"Error marking starred status: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get starring statistics"""
        try:
            starred_jobs = self._load_starred_jobs()
            
            if not starred_jobs:
                return {
                    "total_starred": 0,
                    "sources": {},
                    "recent_starred": 0
                }
            
            # Count by source
            sources = {}
            for job in starred_jobs:
                source = job.get("source", "Unknown")
                sources[source] = sources.get(source, 0) + 1
            
            # Count recent (last 7 days)
            from datetime import timedelta
            week_ago = datetime.now() - timedelta(days=7)
            recent_count = 0
            
            for job in starred_jobs:
                starred_at_str = job.get("starred_at")
                if starred_at_str:
                    try:
                        starred_at = datetime.fromisoformat(starred_at_str)
                        if starred_at >= week_ago:
                            recent_count += 1
                    except:
                        pass
            
            return {
                "total_starred": len(starred_jobs),
                "sources": sources,
                "recent_starred": recent_count,
                "top_source": max(sources.items(), key=lambda x: x[1]) if sources else None
            }
            
        except Exception as e:
            logging.error(f"Error getting starred stats: {e}")
            return {"total_starred": 0, "sources": {}, "recent_starred": 0}
    
    def export_starred_jobs(self, format: str) -> Optional[Path]:
        """Export starred jobs to specified format"""
        try:
            starred_jobs = self._load_starred_jobs()
            
            if not starred_jobs:
                return None
            
            export_file = Path(self.config.output_dir) / f"starred_jobs.{format}"
            
            if format.lower() == "json":
                with open(export_file, 'w', encoding='utf-8') as f:
                    json.dump(starred_jobs, f, indent=2)
            elif format.lower() == "csv":
                import csv
                with open(export_file, 'w', newline='', encoding='utf-8') as f:
                    if starred_jobs:
                        writer = csv.DictWriter(f, fieldnames=starred_jobs[0].keys())
                        writer.writeheader()
                        writer.writerows(starred_jobs)
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            logging.info(f"Exported {len(starred_jobs)} starred jobs to {export_file}")
            return export_file
            
        except Exception as e:
            logging.error(f"Error exporting starred jobs: {e}")
            return None
    
    def _load_starred_jobs(self) -> List[Dict[str, Any]]:
        """Load starred jobs from file"""
        try:
            if self.starred_file.exists():
                with open(self.starred_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logging.warning(f"Error loading starred jobs: {e}")
            return []
    
    def _save_starred_jobs(self, starred_jobs: List[Dict[str, Any]]) -> None:
        """Save starred jobs to file"""
        try:
            with open(self.starred_file, 'w', encoding='utf-8') as f:
                json.dump(starred_jobs, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving starred jobs: {e}")


class PaginationManager:
    """Manages job pagination for the dashboard"""
    
    def __init__(self, config: AppConfig, page_size: int = 20):
        self.config = config
        self.page_size = page_size
        self.jobs_cache = []
        self.filtered_cache = {}
    
    def load_jobs_for_pagination(self, jobs: List[Job]) -> int:
        """Load jobs into pagination cache"""
        self.jobs_cache = jobs
        self.filtered_cache = {}  # Clear filters when loading new data
        return len(jobs)
    
    def refresh_cache(self, jobs: List[Job]) -> None:
        """Refresh the jobs cache"""
        self.jobs_cache = jobs
        self.filtered_cache = {}
    
    def update_page_size(self, new_size: int) -> None:
        """Update page size"""
        self.page_size = new_size
        self.filtered_cache = {}  # Clear cache when page size changes
    
    def get_page(self, page: int, filters: Dict[str, Any] = None) -> tuple:
        """Get a specific page of jobs with optional filtering"""
        from .models import Priority
        
        if filters is None:
            filters = {}
        
        # Create cache key from filters
        cache_key = str(sorted(filters.items()))
        
        # Check if we have cached filtered results
        if cache_key not in self.filtered_cache:
            filtered_jobs = self._apply_filters(self.jobs_cache, filters)
            self.filtered_cache[cache_key] = filtered_jobs
        else:
            filtered_jobs = self.filtered_cache[cache_key]
        
        total_items = len(filtered_jobs)
        total_pages = (total_items + self.page_size - 1) // self.page_size if total_items > 0 else 1
        
        # Validate page number
        page = max(1, min(page, total_pages))
        
        start_index = (page - 1) * self.page_size
        end_index = min(start_index + self.page_size, total_items)
        
        page_jobs = filtered_jobs[start_index:end_index]
        
        # Convert jobs to dictionaries for JSON serialization
        jobs_data = []
        for job in page_jobs:
            job_dict = {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "description": job.description[:500] + "..." if len(job.description) > 500 else job.description,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "source": job.source.name if job.source else "Unknown",
                "url": job.url,
                "remote_friendly": job.remote_friendly,
                "score": getattr(job, 'score', 0),
                "priority": job.priority.value if hasattr(job, 'priority') and job.priority else "MEDIUM",
                "starred": getattr(job, 'starred', False),
                "starred_notes": getattr(job, 'starred_notes', None),
                "scraped_at": job.scraped_at.isoformat() if job.scraped_at else None,
                "has_bullets": getattr(job, 'has_bullets', False)
            }
            jobs_data.append(job_dict)
        
        # Pagination info
        pagination_info = type('PaginationInfo', (), {
            'current_page': page,
            'total_pages': total_pages,
            'page_size': self.page_size,
            'total_items': total_items,
            'has_next': page < total_pages,
            'has_previous': page > 1,
            'start_index': start_index + 1 if total_items > 0 else 0,
            'end_index': end_index
        })()
        
        return jobs_data, pagination_info
    
    def _apply_filters(self, jobs: List[Job], filters: Dict[str, Any]) -> List[Job]:
        """Apply filters to jobs list"""
        filtered_jobs = jobs.copy()
        
        # Priority filter
        if filters.get('priority') and filters['priority'] != 'all':
            if filters['priority'] == 'STARRED':
                filtered_jobs = [job for job in filtered_jobs if getattr(job, 'starred', False)]
            else:
                filtered_jobs = [job for job in filtered_jobs 
                               if hasattr(job, 'priority') and job.priority and job.priority.value == filters['priority']]
        
        # Source filter
        if filters.get('source') and filters['source'] != 'all':
            filtered_jobs = [job for job in filtered_jobs 
                           if job.source and job.source.name == filters['source']]
        
        # Remote filter
        if filters.get('remote') and filters['remote'] != 'all':
            if filters['remote'] == 'remote':
                filtered_jobs = [job for job in filtered_jobs if job.remote_friendly]
            elif filters['remote'] == 'onsite':
                filtered_jobs = [job for job in filtered_jobs if not job.remote_friendly]
        
        # Search filter
        if filters.get('search'):
            search_term = filters['search'].lower()
            filtered_jobs = [job for job in filtered_jobs 
                           if search_term in job.title.lower() or 
                              search_term in job.company.lower() or 
                              search_term in job.location.lower() or
                              search_term in job.description.lower()]
        
        return filtered_jobs