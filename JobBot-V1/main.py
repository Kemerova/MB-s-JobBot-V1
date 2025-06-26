#!/usr/bin/env python3
"""
Enhanced Job Hunter - Updated main entry point with starring functionality
"""

# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Check OPENAI_API_KEY early
if not os.getenv("OPENAI_API_KEY"):
    print("⚠️  WARNING: OPENAI_API_KEY environment variable not set!")
    print("   AI analysis features will not work without this key.")
    print("   Please add OPENAI_API_KEY=your_key_here to your .env file")

# Now import the rest
from V1 import (
    Job, JobSource, Priority,
    AppConfig, ConfigManager,
    setup_logging, make_unique, filter_stale_jobs, validate_environment
)
from V1.error_handling import (
    handle_errors, UserFriendlyError, progress_context, 
    global_error_handler, ErrorCategory
)
from V1.finder import JobFinder
from V1.async_finder import AsyncJobFinder
from V1.analyzer import JobAnalyzer
from V1.reporting import CSVReporter, InteractiveHTMLReporter
from V1.starred_jobs import StarredJobsManager
from V1.cli_commands import add_starred_args, handle_starred_commands

def parse_args():
    """Parse command line arguments with starring functionality"""
    parser = argparse.ArgumentParser(
        description="🎯 AI-Powered Job Hunting System with Starring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           # Run with default settings
  python main.py --sources LinkedIn Indeed # Use specific job boards
  python main.py --quick                   # Quick search (fewer pages)
  python main.py --config my-config.yaml   # Use custom config
  
Starring Commands:
  python main.py list-starred              # Show all starred jobs
  python main.py star --search "python"    # Star jobs interactively
  python main.py unstar                    # Unstar jobs interactively
  python main.py export-starred csv        # Export starred jobs
  python main.py starred-stats             # Show starring statistics
        """
    )
    
    # Main arguments
    parser.add_argument('--config', '-c', 
                      help='Path to configuration file', 
                      default='config.yaml')
    
    parser.add_argument('--sources', '-s', nargs='+',
                      help='Specific job sources to use (overrides config)')
    
    parser.add_argument('--pages', '-p', type=int,
                      help='Pages per source to scrape')
    
    parser.add_argument('--threshold', '-t', type=int,
                      help='Minimum score threshold')
    
    parser.add_argument('--output-dir', '-o',
                      help='Output directory for results')
    
    parser.add_argument('--log-level', '-l',
                      choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                      help='Logging level')
    
    parser.add_argument('--analyze-only', action='store_true',
                      help='Only analyze previously found jobs (no scraping)')
    
    parser.add_argument('--lazy', action='store_true',
                      help='Use lazy analysis (generate bullets on-demand)')
    
    parser.add_argument('--quick', action='store_true',
                      help='Quick search mode (1 page per source)')
    
    parser.add_argument('--list-sources', action='store_true',
                      help='List available job sources and exit')
    
    parser.add_argument('--setup-config', action='store_true',
                      help='Create sample configuration file and exit')
    parser.add_argument('--profile', '-P',
                      help='Select user profile name (for multiple resumes)')
    
    parser.add_argument('--concurrent', action='store_true',
                      help='Use concurrent async scraping for 3x faster searches')
    
    # Add starring functionality arguments
    add_starred_args(parser)
    
    return parser.parse_args()

def print_available_sources():
    """Print available job sources"""
    print("\n🔍 Available Job Sources:")
    print("=" * 50)
    
    sources = [
        ("Manual", "Manually curated high-quality positions", True),
        ("LinkedIn", "LinkedIn job postings", True),
        ("Indeed", "Indeed job board", True),
        ("Dice", "Dice technology job board", False),
        ("ClearanceJobs", "Security clearance positions", False),
    ]
    
    for name, description, enabled_default in sources:
        status = "✅ Enabled by default" if enabled_default else "❌ Disabled by default"
        print(f"  {name:<15} - {description} ({status})")
    
    print(f"\n💡 Use --sources to select specific sources:")
    print(f"   python main.py --sources LinkedIn Indeed Dice")
    print()

@handle_errors(context="main", show_user_message=True)
def main():
    """Main application entry point with starring support"""
    try:
        args = parse_args()

        # Handle special modes
        if args.list_sources:
            print_available_sources()
            return 0

        if args.setup_config:
            from V1.config import create_sample_config
            create_sample_config(args.config)
            return 0
    except Exception as e:
        if isinstance(e, UserFriendlyError):
            print(e.format_for_cli())
            return 1
        else:
            friendly_error = global_error_handler.handle_error(e, "argument_parsing")
            return 1

    # Load configuration
    try:
        config_manager = ConfigManager(args.config)
        config = config_manager.load_config()
        # Apply --profile override
        if args.profile:
            if args.profile not in config.profiles:
                raise UserFriendlyError(
                    title="Profile Not Found",
                    message=f"Profile '{args.profile}' not found in configuration",
                    category=ErrorCategory.CONFIGURATION,
                    solution=f"Available profiles: {', '.join(config.profiles.keys()) if config.profiles else 'None'}",
                    help_link="/setup"
                )
            config.active_profile = args.profile
            config.user = config.profiles[args.profile]
    except UserFriendlyError:
        raise
    except Exception as e:
        raise UserFriendlyError(
            title="Configuration Error",
            message="Failed to load configuration file",
            category=ErrorCategory.CONFIGURATION,
            solution="Check your config.yaml file or run 'python main.py --setup-config' to create a new one",
            help_link="/setup",
            technical_details=str(e)
        )

    # Handle starring commands first
    if handle_starred_commands(args, config):
        return 0
     
    # --- VALIDATE AND SYNC SOURCES ---
    # Validate CLI sources before applying
    if args.sources:
        # Validate sources using config's method
        invalid_sources = []
        if hasattr(config.scraping, "validate_sources"):
            invalid_sources = config.scraping.validate_sources(args.sources)
        else:
            valid_sources = {"Manual", "LinkedIn", "Indeed", "Dice", "ClearanceJobs"}
            invalid_sources = [s for s in args.sources if s not in valid_sources]

        if invalid_sources:
            print(f"❌ Invalid job source(s): {', '.join(invalid_sources)}")
            print_available_sources()
            return 1

        print(f"🔍 Using job sources: {', '.join(args.sources)}")
        config.scraping.enabled_sources = args.sources
        config.scraping.job_boards = config.scraping._create_job_boards_from_list()
        # Always sync after manual changes
        if hasattr(config.scraping, "sync_enabled_sources_and_boards"):
            config.scraping.sync_enabled_sources_and_boards()

    # Always sync after any CLI override
    if hasattr(config.scraping, "sync_enabled_sources_and_boards"):
        config.scraping.sync_enabled_sources_and_boards()

    if args.pages:
        for board in config.scraping.job_boards.values():
            board.pages_per_search = args.pages
        config.scraping.pages_per_source = args.pages

    if args.quick:
        for board in config.scraping.job_boards.values():
            board.pages_per_search = 1
        config.scraping.pages_per_source = 1
        config.analysis.batch_size = 3

    if args.threshold:
        config.analysis.score_threshold = args.threshold

    if args.output_dir:
        config.output_dir = args.output_dir

    if args.log_level:
        config.log_level = args.log_level

    if args.lazy:
        config.analysis.lazy_analysis = True

    # Setup logging
    setup_logging(config.log_level, config.output_dir)

    # Validate environment
    errors = validate_environment()
    if errors:
        for error in errors:
            logging.error(f"Environment error: {error}")
        print("⚠️  Some features may not work due to missing dependencies")

    # Initialize components
    if args.concurrent:
        logging.info("🚀 Using concurrent async scraping for faster searches")
        job_finder = AsyncJobFinder(config)
    else:
        job_finder = JobFinder(config)
    job_analyzer = JobAnalyzer(config)
    csv_reporter = CSVReporter(config)
    html_reporter = InteractiveHTMLReporter(config)
    starred_manager = StarredJobsManager(config)

    # Find jobs (unless --analyze-only)
    all_jobs = []

    if not args.analyze_only:
        enabled_boards = config.scraping.enabled_boards
        if not enabled_boards:
            logging.error("❌ No job sources enabled. Please check your configuration.")
            return 1

        logging.info(f"🚀 Starting job search with {len(enabled_boards)} job sources:")
        for board in enabled_boards:
            source_icon = "🤖" if board.type.value == "api" else "🕷️" if board.type.value == "scraper" else "✋"
            logging.info(f"   {source_icon} {board.name} (Priority: {board.priority})")

        # --- JOB SCRAPING ---
        try:
            if args.concurrent and isinstance(job_finder, AsyncJobFinder):
                # Use concurrent async scraping
                logging.info("🚀 Starting concurrent job scraping...")
                start_time = datetime.now()
                
                with progress_context(len(enabled_boards), "Concurrent scraping") as progress:
                    all_jobs = job_finder.find_jobs()
                    progress.update(len(enabled_boards), "All sources completed")
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                logging.info(f"⚡ Concurrent scraping completed in {duration:.1f} seconds")
            else:
                # Use traditional sequential scraping with enhanced progress tracking
                keywords = config.jobs.target_titles[:3]
                locations = config.location.primary_locations[:2] + ["Remote"]
                
                # Calculate total operations for progress tracking
                total_operations = sum(
                    len(keywords) * len(locations) for board in enabled_boards
                )
                
                all_jobs = []
                with progress_context(total_operations, "Sequential scraping") as progress:
                    for board in enabled_boards:
                        try:
                            board_jobs = []
                            if hasattr(job_finder, "scrapers") and board.name in job_finder.scrapers:
                                scraper = job_finder.scrapers[board.name]
                                for keyword in keywords:
                                    for location in locations:
                                        try:
                                            jobs = scraper.search_jobs(keyword, location, pages=board.pages_per_search)
                                            board_jobs.extend(jobs)
                                            progress.update(1, f"{board.name}: {keyword} in {location}")
                                        except Exception as e:
                                            progress.add_error(e, f"{board.name}: {keyword} in {location}")
                                            logging.warning(f"Failed to scrape {board.name} for {keyword} in {location}: {e}")
                            
                            all_jobs.extend(board_jobs)
                            logging.info(f"✅ {board.name}: {len(board_jobs)} jobs found")
                        except Exception as e:
                            progress.add_error(e, f"{board.name} (entire board)")
                            logging.error(f"❌ Error scraping {board.name}: {e}")
                            
                            # Continue with other boards
                            continue
        except Exception as e:
            raise UserFriendlyError(
                title="Job Scraping Failed",
                message="Failed to search for jobs from the enabled sources",
                category=ErrorCategory.SCRAPING,
                solution="Check your internet connection and try again. Some job boards may be temporarily unavailable",
                technical_details=str(e),
                recoverable=True
            )

        logging.info(f"📊 Found {len(all_jobs)} total jobs from all sources")

        if not all_jobs:
            logging.warning("⚠️  No jobs found. Check your configuration and enabled sources.")
            print("\n💡 Troubleshooting tips:")
            print("   1. Check your internet connection")
            print("   2. Try different job sources: python main.py --sources LinkedIn Indeed")
            print("   3. Verify your target titles in config.yaml")
            print("   4. Check if job boards are blocking requests (try --quick mode)")
            return 1

        # Save raw jobs to timestamped CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_reporter.generate_report(all_jobs, f"all_raw_jobs_{timestamp}.csv")

        # Deduplication and filtering
        unique_jobs = make_unique(all_jobs)
        logging.info(f"🔄 After deduplication: {len(unique_jobs)} unique jobs")

        fresh_jobs = filter_stale_jobs(unique_jobs, config.jobs.max_age_days)
        logging.info(f"📅 After filtering stale jobs: {len(fresh_jobs)} jobs to analyze")

        all_jobs = fresh_jobs
    else:
        # Load jobs from most recent CSV for analysis-only mode
        all_jobs = load_jobs_from_csv(config.output_dir)
        if not all_jobs:
            logging.error("❌ No jobs found for analysis. Run without --analyze-only first.")
            sys.exit(1)
        logging.info(f"📄 Loaded {len(all_jobs)} jobs from previous run")

    # Mark jobs with their starred status before analysis
    starred_manager.mark_jobs_starred_status(all_jobs)

    # Analyze jobs
    analysis_mode = "lazy" if config.analysis.lazy_analysis else "full"
    logging.info(f"🤖 Starting {analysis_mode} job analysis...")

    try:
        analyzed_jobs = job_analyzer.analyze_batch(
            all_jobs, 
            full_analysis=not config.analysis.lazy_analysis
        )
    except Exception as e:
        logging.error(f"❌ Analysis failed: {e}")
        print("⚠️  Analysis failed, but continuing with basic scoring...")
        # Use jobs without full analysis
        analyzed_jobs = all_jobs
        for job in analyzed_jobs:
            if not job.score:
                job.score = 50  # Default score

    # Generate reports
    logging.info("📄 Generating reports...")

    # Filter by priority
    high_priority_jobs = [job for job in analyzed_jobs if job.priority == Priority.HIGH]
    premium_jobs = [job for job in analyzed_jobs if job.score >= 86]
    starred_jobs = [job for job in analyzed_jobs if job.starred]

    # Generate timestamped reports
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # CSV Reports
    csv_reporter.generate_report(analyzed_jobs, f"all_jobs_{timestamp}.csv")

    if high_priority_jobs:
        csv_reporter.generate_report(high_priority_jobs, f"high_priority_{timestamp}.csv")

    if premium_jobs:
        csv_reporter.generate_report(premium_jobs, f"premium_jobs_{timestamp}.csv")

    if starred_jobs:
        csv_reporter.generate_report(starred_jobs, f"starred_jobs_{timestamp}.csv")

    # Interactive HTML Dashboard
    logging.info(f"🎨 Generating interactive dashboard with {len(analyzed_jobs)} jobs...")

    try:
        html_file = html_reporter.generate_report(analyzed_jobs, "job_dashboard.html")

        if html_file:
            logging.info("✅ Dashboard generated successfully")

            # Check if JSON was created
            json_path = os.path.join(config.output_dir, "jobs_data.json")
            if os.path.exists(json_path):
                logging.info("✅ Job data JSON created successfully")
            else:
                logging.error("❌ Job data JSON NOT created")

    except Exception as e:
        logging.error(f"❌ Dashboard generation failed: {e}")
        import traceback
        traceback.print_exc()
        html_file = None

    # Print comprehensive summary
    print_job_summary(analyzed_jobs, high_priority_jobs, premium_jobs, starred_jobs, config, html_file, starred_manager)

    return 0

def load_jobs_from_csv(output_dir: str):
    """Load jobs from most recent CSV file"""
    try:
        import csv
        import glob
        
        # Find most recent raw jobs file
        pattern = os.path.join(output_dir, "all_raw_jobs_*.csv")
        files = glob.glob(pattern)
        
        if not files:
            return []
        
        jobs_file = max(files, key=os.path.getctime)
        all_jobs = []
        
        with open(jobs_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    job = Job(
                        title=row['Title'],
                        company=row['Company'],
                        location=row['Location'],
                        source=JobSource(row['Source']),
                        url=row['URL'] if row['URL'] else None,
                        salary=row['Salary'] if row['Salary'] else None,
                        scraped_at=datetime.fromisoformat(row['Date_Found']) if row['Date_Found'] else datetime.now()
                    )
                    all_jobs.append(job)
                except Exception as e:
                    logging.warning(f"Skipping invalid job row: {e}")
                    continue
        
        return all_jobs
        
    except Exception as e:
        logging.error(f"Failed to load jobs from CSV: {e}")
        return []

def print_job_summary(analyzed_jobs, high_priority_jobs, premium_jobs, starred_jobs, config, html_file, starred_manager):
    """Print comprehensive job search summary with starring info"""
    enabled_boards = [board.name for board in config.scraping.enabled_boards]
    
    print(f"\n{'='*70}")
    print(f"🎯 JOB HUNT SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    
    # Job statistics
    print(f"📊 RESULTS OVERVIEW:")
    print(f"   📋 Total Jobs Found: {len(analyzed_jobs)}")
    print(f"   🔥 High Priority Jobs: {len(high_priority_jobs)}")
    print(f"   ⭐ Premium Jobs (86+): {len(premium_jobs)}")
    print(f"   ⭐ Starred Jobs: {len(starred_jobs)}")
    print(f"   📈 Average Score: {sum(j.score for j in analyzed_jobs) / len(analyzed_jobs):.1f}/100" if analyzed_jobs else "   📈 Average Score: 0/100")
    
    # Configuration summary
    print(f"\n⚙️  SEARCH CONFIGURATION:")
    print(f"   🔍 Job Boards Used: {', '.join(enabled_boards)}")
    print(f"   🤖 Analysis Mode: {'Lazy (on-demand bullets)' if config.analysis.lazy_analysis else 'Full (pre-generated bullets)'}")
    print(f"   🎯 Score Threshold: {config.analysis.score_threshold}")
    print(f"   💰 Min Salary: ${config.jobs.min_salary:,}")
    
    # Starring statistics
    starring_stats = starred_manager.get_stats()
    print(f"\n⭐ STARRING STATISTICS:")
    print(f"   📊 Total Starred: {starring_stats['total_starred']}")
    print(f"   📅 Starred This Week: {starring_stats['recent_week']}")
    if starring_stats['by_source']:
        top_source = max(starring_stats['by_source'].items(), key=lambda x: x[1])
        print(f"   🥇 Top Source: {top_source[0]} ({top_source[1]} starred)")
    
    # Output information
    print(f"\n📁 OUTPUT FILES:")
    print(f"   📄 Reports Directory: {config.output_dir}")
    
    if html_file:
        print(f"   🎨 Interactive Dashboard: {html_file}")
        print(f"   🌐 Open this file in your browser to view and interact with results")
        print(f"   💡 Use the 'I'm Interested' button to generate tailored resume bullets")
        print(f"   ⭐ Use the 'Star Job' button to save jobs for later")
    
    # Top jobs preview
    if premium_jobs:
        print(f"\n⭐ TOP {min(3, len(premium_jobs))} PREMIUM JOBS (86+ Score):")
        print("-" * 60)
        for i, job in enumerate(sorted(premium_jobs, key=lambda x: x.score, reverse=True)[:3], 1):
            star_indicator = "⭐" if job.starred else "☆"
            print(f"   {i}. {star_indicator} {job.title} at {job.company}")
            print(f"      💯 Score: {job.score}/100 | 📍 Location: {job.location}")
            print(f"      💰 Salary: {job.salary or 'Competitive'}")
            if job.starred and job.starred_notes:
                print(f"      📝 Notes: {job.starred_notes}")
            if job.url:
                print(f"      🔗 Apply: {job.url}")
            print()
    
    elif high_priority_jobs:
        print(f"\n🔥 TOP {min(3, len(high_priority_jobs))} HIGH PRIORITY JOBS:")
        print("-" * 60)
        for i, job in enumerate(sorted(high_priority_jobs, key=lambda x: x.score, reverse=True)[:3], 1):
            star_indicator = "⭐" if job.starred else "☆"
            print(f"   {i}. {star_indicator} {job.title} at {job.company}")
            print(f"      💯 Score: {job.score}/100 | 📍 Location: {job.location}")
            print(f"      💰 Salary: {job.salary or 'Competitive'}")
            if job.starred and job.starred_notes:
                print(f"      📝 Notes: {job.starred_notes}")
            if job.url:
                print(f"      🔗 Apply: {job.url}")
            print()
    
    # Starred jobs preview
    if starred_jobs:
        print(f"\n⭐ STARRED JOBS ({len(starred_jobs)} total):")
        print("-" * 60)
        for i, job in enumerate(sorted(starred_jobs, key=lambda x: x.starred_at or datetime.min, reverse=True)[:3], 1):
            print(f"   {i}. ⭐ {job.title} at {job.company}")
            print(f"      💯 Score: {job.score}/100 | 📍 Location: {job.location}")
            if job.starred_notes:
                print(f"      📝 Notes: {job.starred_notes}")
            if job.url:
                print(f"      🔗 Apply: {job.url}")
            print()
    
    # Next steps
    print(f"🚀 NEXT STEPS:")
    if html_file:
        print(f"   1. Open the dashboard: {html_file}")
        print(f"   2. Review high-priority jobs and star your favorites")
        print(f"   3. Click 'I'm Interested' for tailored resume bullets")
        print(f"   4. Apply to your top matches!")
    else:
        print(f"   1. Check the CSV reports in {config.output_dir}")
        print(f"   2. Run the dashboard server: python dashboard_server.py")
        print(f"   3. Star your favorite jobs and apply!")
    
    # CLI commands help
    print(f"\n💡 STARRING COMMANDS:")
    print(f"   python main.py list-starred              # View all starred jobs")
    print(f"   python main.py star --search 'python'    # Star jobs interactively")
    print(f"   python main.py export-starred csv        # Export starred jobs")
    print(f"   python main.py starred-stats             # View starring statistics")
    
    if config.analysis.lazy_analysis:
        print(f"\n💡 TIP: Using lazy analysis saves time and AI credits.")
        print(f"   Resume bullets are generated only when you show interest in a job.")
    
    print(f"{'='*70}")

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n👋 Job search interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logging.exception("Unexpected error occurred")
        sys.exit(1)