"""
CLI Commands for Starred Jobs functionality
Handles command-line interface for starring/unstarring jobs.
"""
import sys
import json
import logging
from typing import List, Optional
from pathlib import Path
from .starred_jobs import StarredJobsManager
from .models import Job, JobSource
from .config import AppConfig


def add_starred_args(parser):
    """Add starring-related arguments to argument parser"""
    
    # Subcommands for starring functionality
    subparsers = parser.add_subparsers(dest='command', help='Starring commands')
    
    # List starred jobs
    list_parser = subparsers.add_parser('list-starred', help='List all starred jobs')
    list_parser.add_argument('--format', choices=['table', 'json'], default='table',
                           help='Output format')
    
    # Star jobs interactively
    star_parser = subparsers.add_parser('star', help='Star jobs interactively')
    star_parser.add_argument('--search', help='Search for jobs to star')
    star_parser.add_argument('--source', help='Filter by job source')
    
    # Unstar jobs
    unstar_parser = subparsers.add_parser('unstar', help='Unstar jobs interactively')
    
    # Export starred jobs
    export_parser = subparsers.add_parser('export-starred', help='Export starred jobs')
    export_parser.add_argument('format', choices=['csv', 'json'], help='Export format')
    export_parser.add_argument('--output', help='Output file path')
    
    # Starred jobs statistics
    stats_parser = subparsers.add_parser('starred-stats', help='Show starring statistics')
    

def handle_starred_commands(args, config: AppConfig) -> bool:
    """Handle starring-related commands. Returns True if command was handled."""
    
    if not hasattr(args, 'command') or args.command is None:
        return False
    
    starred_manager = StarredJobsManager(config)
    
    try:
        if args.command == 'list-starred':
            return _handle_list_starred(starred_manager, args)
        elif args.command == 'star':
            return _handle_star_jobs(starred_manager, config, args)
        elif args.command == 'unstar':
            return _handle_unstar_jobs(starred_manager, config)
        elif args.command == 'export-starred':
            return _handle_export_starred(starred_manager, args)
        elif args.command == 'starred-stats':
            return _handle_starred_stats(starred_manager)
        else:
            return False
            
    except KeyboardInterrupt:
        print("\n👋 Operation cancelled by user")
        return True
    except Exception as e:
        logging.error(f"Error handling starred command: {e}")
        print(f"❌ Error: {e}")
        return True


def _handle_list_starred(starred_manager: StarredJobsManager, args) -> bool:
    """Handle list-starred command"""
    starred_jobs = starred_manager.get_starred_jobs()
    
    if not starred_jobs:
        print("📭 No starred jobs found.")
        print("   Use 'python main.py star' to star some jobs!")
        return True
    
    if args.format == 'json':
        print(json.dumps(starred_jobs, indent=2))
    else:
        print(f"\n⭐ STARRED JOBS ({len(starred_jobs)} total)")
        print("=" * 60)
        
        for i, job in enumerate(starred_jobs, 1):
            print(f"\n{i}. {job['title']}")
            print(f"   🏢 {job['company']}")
            print(f"   📍 {job['location']}")
            print(f"   🔗 {job['url']}")
            print(f"   📊 Score: {job.get('score', 'N/A')}")
            print(f"   📅 Starred: {job.get('starred_at', 'Unknown')[:10]}")
            
            if job.get('starred_notes'):
                print(f"   📝 Notes: {job['starred_notes']}")
    
    return True


def _handle_star_jobs(starred_manager: StarredJobsManager, config: AppConfig, args) -> bool:
    """Handle star command - interactive job starring"""
    
    # Load recent jobs
    jobs_file = Path(config.output_dir) / "jobs_data.json"
    if not jobs_file.exists():
        print("❌ No recent job data found. Run a job search first!")
        return True
    
    try:
        with open(jobs_file, 'r', encoding='utf-8') as f:
            jobs_data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading jobs data: {e}")
        return True
    
    # Filter jobs if search/source specified
    filtered_jobs = jobs_data
    
    if args.search:
        search_term = args.search.lower()
        filtered_jobs = [
            job for job in filtered_jobs
            if search_term in job.get('title', '').lower() or
               search_term in job.get('company', '').lower() or
               search_term in job.get('description', '').lower()
        ]
    
    if args.source:
        filtered_jobs = [
            job for job in filtered_jobs
            if job.get('source', '').lower() == args.source.lower()
        ]
    
    if not filtered_jobs:
        print("❌ No jobs found matching your criteria.")
        return True
    
    # Show jobs and allow starring
    print(f"\n🔍 Found {len(filtered_jobs)} jobs")
    print("=" * 50)
    
    for i, job_data in enumerate(filtered_jobs[:10], 1):  # Limit to 10 for usability
        print(f"\n{i}. {job_data.get('title', 'Unknown Title')}")
        print(f"   🏢 {job_data.get('company', 'Unknown Company')}")
        print(f"   📍 {job_data.get('location', 'Unknown Location')}")
        print(f"   📊 Score: {job_data.get('score', 'N/A')}")
        
        if job_data.get('starred'):
            print("   ⭐ Already starred")
        else:
            while True:
                choice = input(f"   ⭐ Star this job? (y/n/q to quit): ").strip().lower()
                if choice == 'q':
                    print("👋 Exiting...")
                    return True
                elif choice == 'y':
                    notes = input("   📝 Add notes (optional): ").strip()
                    
                    # Create Job object
                    job_obj = _dict_to_job_object(job_data)
                    
                    # Star the job
                    if starred_manager.star_job(job_obj, notes if notes else None):
                        print("   ✅ Job starred successfully!")
                    else:
                        print("   ❌ Failed to star job (might already be starred)")
                    break
                elif choice == 'n':
                    break
                else:
                    print("   Please enter 'y', 'n', or 'q'")
    
    return True


def _handle_unstar_jobs(starred_manager: StarredJobsManager, config: AppConfig) -> bool:
    """Handle unstar command - interactive job unstarring"""
    
    starred_jobs = starred_manager.get_starred_jobs()
    
    if not starred_jobs:
        print("📭 No starred jobs to unstar.")
        return True
    
    print(f"\n⭐ STARRED JOBS ({len(starred_jobs)} total)")
    print("=" * 50)
    
    for i, job in enumerate(starred_jobs, 1):
        print(f"\n{i}. {job['title']}")
        print(f"   🏢 {job['company']}")
        print(f"   📍 {job['location']}")
        if job.get('starred_notes'):
            print(f"   📝 Notes: {job['starred_notes']}")
        
        while True:
            choice = input(f"   ❌ Unstar this job? (y/n/q to quit): ").strip().lower()
            if choice == 'q':
                print("👋 Exiting...")
                return True
            elif choice == 'y':
                # Create Job object
                job_obj = _dict_to_job_object(job)
                
                # Unstar the job
                if starred_manager.unstar_job(job_obj):
                    print("   ✅ Job unstarred successfully!")
                else:
                    print("   ❌ Failed to unstar job")
                break
            elif choice == 'n':
                break
            else:
                print("   Please enter 'y', 'n', or 'q'")
    
    return True


def _handle_export_starred(starred_manager: StarredJobsManager, args) -> bool:
    """Handle export-starred command"""
    
    starred_jobs = starred_manager.get_starred_jobs()
    
    if not starred_jobs:
        print("📭 No starred jobs to export.")
        return True
    
    try:
        export_path = starred_manager.export_starred_jobs(args.format)
        
        if export_path:
            if args.output:
                # Move to specified output path
                import shutil
                final_path = Path(args.output)
                shutil.move(str(export_path), str(final_path))
                print(f"✅ Exported {len(starred_jobs)} starred jobs to {final_path}")
            else:
                print(f"✅ Exported {len(starred_jobs)} starred jobs to {export_path}")
        else:
            print("❌ Failed to export starred jobs")
            
    except Exception as e:
        print(f"❌ Export error: {e}")
    
    return True


def _handle_starred_stats(starred_manager: StarredJobsManager) -> bool:
    """Handle starred-stats command"""
    
    stats = starred_manager.get_stats()
    
    print("\n📊 STARRING STATISTICS")
    print("=" * 30)
    print(f"Total Starred Jobs: {stats['total_starred']}")
    print(f"Recently Starred (7 days): {stats['recent_starred']}")
    
    if stats['sources']:
        print(f"\nBy Source:")
        for source, count in sorted(stats['sources'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {source}: {count}")
    
    if stats.get('top_source'):
        top_source, count = stats['top_source']
        print(f"\nTop Source: {top_source} ({count} starred)")
    
    return True


def _dict_to_job_object(job_data: dict) -> Job:
    """Convert job dictionary to Job object"""
    from .models import JobSource, Priority
    from datetime import datetime
    
    # Handle source
    source_name = job_data.get('source', 'Unknown')
    source = JobSource(source_name, job_data.get('source_url', ''))
    
    # Handle priority
    priority_str = job_data.get('priority', 'MEDIUM')
    try:
        priority = Priority(priority_str)
    except ValueError:
        priority = Priority.MEDIUM
    
    # Handle dates
    scraped_at = None
    if job_data.get('scraped_at'):
        try:
            scraped_at = datetime.fromisoformat(job_data['scraped_at'])
        except:
            scraped_at = datetime.now()
    
    starred_at = None
    if job_data.get('starred_at'):
        try:
            starred_at = datetime.fromisoformat(job_data['starred_at'])
        except:
            pass
    
    # Create Job object
    job = Job(
        id=job_data.get('id', 0),
        title=job_data.get('title', ''),
        company=job_data.get('company', ''),
        location=job_data.get('location', ''),
        description=job_data.get('description', ''),
        source=source,
        url=job_data.get('url', ''),
        salary_min=job_data.get('salary_min'),
        salary_max=job_data.get('salary_max'),
        score=job_data.get('score', 0),
        priority=priority,
        remote_friendly=job_data.get('remote_friendly', False),
        clearance_required=job_data.get('clearance_required'),
        job_type=job_data.get('job_type'),
        search_keywords=job_data.get('search_keywords'),
        scraped_at=scraped_at,
        starred=job_data.get('starred', False),
        starred_at=starred_at,
        starred_notes=job_data.get('starred_notes')
    )
    
    return job