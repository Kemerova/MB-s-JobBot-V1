"""
Enhanced job analysis module with smart description processing and lazy loading
"""

import os
import time
import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI

from .models import Job, Priority
from .config import AppConfig
from .utils import cache_result


class JobAnalyzer:
    """Analyze jobs with AI-powered scoring, resume tailoring, and smart descriptions"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=config.analysis.llm_temperature
        )
        
        # Simple description processing without external dependency
        
        # Create specialized agents
        self.scorer = Agent(
            role="Senior Technical Recruiter",
            goal="Score job opportunities based on candidate fit and market value",
            backstory="""Expert recruiter with 15+ years placing technical professionals. 
            Specializes in matching candidates with roles based on skills, experience, 
            location preferences, and career growth potential.""",
            llm=self.llm
        )
        
        self.tailor = Agent(
            role="Executive Resume Writer",
            goal="Create compelling resume bullets that highlight relevant achievements",
            backstory="""Certified resume writer with expertise in technical roles. 
            Specializes in quantifying achievements and translating technical work 
            into business impact for hiring managers.""",
            llm=self.llm
        )
        
        # Load resume
        self.resume_text = self._load_resume()
        
        # Analysis cache
        self.analysis_cache = {}
    
    def _load_resume(self) -> str:
        """Load resume with multiple fallback options"""
        resume_paths = [
            self.config.user.resume_path,
            "resume/base_resume.txt",
            "base_resume.txt",
            "resume.txt"
        ]
        
        for path in resume_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        logging.info(f"Resume loaded from {path}")
                        return content
            except FileNotFoundError:
                continue
        
        # Create sample resume if none found
        logging.warning("No resume file found. Creating sample resume...")
        self._create_sample_resume()
        return self._get_default_resume()
    
    def _create_sample_resume(self):
        """Create sample resume file"""
        resume_dir = Path("resume")
        resume_dir.mkdir(exist_ok=True)
        
        sample_resume = self._get_default_resume()
        
        with open("resume/base_resume.txt", "w", encoding="utf-8") as f:
            f.write(sample_resume)
        
        logging.info("Sample resume created at resume/base_resume.txt")
    
    def _get_default_resume(self) -> str:
        """Get default resume template"""
        return f"""{self.config.user.name}
{self.config.user.target_industry} Professional

Professional {self.config.user.experience_level.lower()} with 5+ years experience in {self.config.user.target_industry.lower()}.

TECHNICAL SKILLS:
• Programming: Python, JavaScript, SQL
• Cloud: AWS, Azure, Google Cloud Platform
• Tools: Docker, Git, Jenkins
• Databases: PostgreSQL, MongoDB

EXPERIENCE:
{self.config.user.experience_level} Engineer | Tech Company (2020-Present)
• Developed scalable applications serving 100k+ users
• Implemented automation reducing manual work by 50%
• Led team of 5 engineers on critical projects
• Delivered $2M cost savings through optimization

EDUCATION:
Bachelor of Science in Computer Science
University, 2020

{f"CLEARANCE: {self.config.user.clearance_level}" if self.config.user.clearance_level else ""}
"""
    
    def quick_score(self, job: Job) -> int:
        """Quick scoring without full AI analysis for initial filtering"""
        score = 0
        
        # Location scoring (25 points)
        if any(loc.lower() in job.location.lower() for loc in self.config.location.target_locations):
            score += 25
        elif 'remote' in job.location.lower():
            score += 20
        else:
            score += 10
        
        # Title/role match (25 points)
        title_lower = job.title.lower()
        if any(target.lower() in title_lower for target in self.config.jobs.target_titles):
            score += 25
        elif any(keyword in title_lower for keyword in ['engineer', 'developer', 'analyst']):
            score += 15
        else:
            score += 10
        
        # Salary scoring (20 points)
        if job.salary_min and job.salary_min >= self.config.jobs.min_salary:
            score += 20
        elif job.salary and any(indicator in job.salary.lower() for indicator in ['competitive', '100k', '120k', '140k']):
            score += 15
        else:
            score += 10
        
        # Company quality (15 points)
        if any(company.lower() in job.company.lower() for company in self.config.jobs.target_companies):
            score += 15
        elif any(indicator in job.company.lower() for indicator in ['tech', 'software', 'systems']):
            score += 12
        else:
            score += 8
        
        # Source reliability (15 points)
        source_scores = {
            'Manual': 15,
            'LinkedIn': 12,
            'ClearanceJobs': 12,
            'Indeed': 10,
            'Dice': 10
        }
        score += source_scores.get(job.source.value, 8)
        
        return min(score, 100)
    
    def _create_scoring_prompt(self, job: Job) -> str:
        """Create focused scoring prompt for AI analysis"""
        return f"""
        Analyze this job opportunity for fit assessment:
        
        CANDIDATE PROFILE:
        - Experience Level: {self.config.user.experience_level}
        - Target Industry: {self.config.user.target_industry}
        - Location Preference: {', '.join(self.config.location.target_locations)}
        - Minimum Salary: ${self.config.jobs.min_salary:,}
        {f"- Clearance Level: {self.config.user.clearance_level}" if self.config.user.clearance_level else ""}
        
        JOB DETAILS:
        Title: {job.title}
        Company: {job.company}
        Location: {job.location}
        Salary: {job.salary or 'Not specified'}
        {f"Clearance Required: {job.clearance_required}" if job.clearance_required else ""}
        
        Description: {job.description[:500] if job.description else 'See job posting for details'}
        
        SCORING CRITERIA (Total 100 points):
        1. Role Fit (30 points): How well does this role match experience and career goals?
        2. Location Match (25 points): Location preference alignment
        3. Compensation (20 points): Salary competitiveness and total package
        4. Company/Growth (15 points): Company reputation and career growth potential
        5. Requirements Match (10 points): Skills and experience alignment
        
        Provide:
        SCORE: [number 0-100]
        RATIONALE: [2-3 sentences explaining the score, focusing on strongest fit factors]
        CONCERNS: [1-2 potential concerns or gaps, if any]
        """
    
    def _create_bullets_prompt(self, job: Job) -> str:
        """Create focused bullet generation prompt using processed job description"""
        # Use processed description for better targeting
        processed = self.description_processor.process_description(job)
        job_summary = processed.get('enhanced') or processed.get('truncated')
        return f"""
Create 3 tailored resume bullets for this role using my resume and the job summary below.

CANDIDATE BACKGROUND:
{self.resume_text[:800]}

JOB SUMMARY:
{job_summary}

KEY REQUIREMENTS (brief):
{(job.description[:300] + '...') if job.description else 'See full job posting'}

Please craft bullets with distinct focuses:
1. TECHNICAL ACHIEVEMENT: Highlight a technical accomplishment using relevant tools/metrics.
2. LEADERSHIP IMPACT: Showcase team leadership, mentoring, or cross-functional collaboration.
3. BUSINESS VALUE: Emphasize strategic impact, cost savings, or efficiency gains.

Format each bullet as:
• [Action verb] [accomplishment] [quantified result] [context]

BULLET 1: 
BULLET 2: 
BULLET 3:
"""
    
    @cache_result(ttl_seconds=3600)
    def analyze_job_full(self, job: Job) -> Job:
        """Perform full AI analysis of a job (expensive operation)"""
        try:
            # Create analysis tasks
            score_task = Task(
                description=self._create_scoring_prompt(job),
                expected_output="Score (0-100), rationale, and concerns for job fit",
                agent=self.scorer
            )
            
            # Only generate bullets if not using lazy analysis or score is high enough
            should_generate_bullets = (
                not self.config.analysis.lazy_analysis or 
                job.score >= self.config.analysis.score_threshold
            )
            
            tasks = [score_task]
            agents = [self.scorer]
            
            if should_generate_bullets:
                bullets_task = Task(
                    description=self._create_bullets_prompt(job),
                    expected_output="Three tailored resume bullets in specified format",
                    agent=self.tailor
                )
                tasks.append(bullets_task)
                agents.append(self.tailor)
            
            # Run analysis
            crew = Crew(
                agents=agents,
                tasks=tasks,
                verbose=False
            )
            
            results = crew.kickoff()
            
            # Parse results
            if hasattr(results, 'tasks_output') and len(results.tasks_output) >= 1:
                self._parse_scoring_results(job, str(results.tasks_output[0].raw))
                
                if len(results.tasks_output) >= 2:
                    self._parse_bullets_results(job, str(results.tasks_output[1].raw))
                else:
                    # Set placeholder bullets for lazy analysis
                    job.tailored_bullets = ["Quick assessment - full analysis available on request"]
            else:
                # Fallback parsing
                result_text = str(results)
                self._parse_scoring_results(job, result_text)
                if should_generate_bullets:
                    self._parse_bullets_results(job, result_text)
                else:
                    job.tailored_bullets = ["Quick assessment - full analysis available on request"]
            
            # Process description based on score
            if job.score >= 86:
                try:
                    description_data = self.description_processor.process_description(job)
                    job.enhanced_description = description_data.get("enhanced")
                    job.description_type = description_data.get("type", "basic")
                except Exception as e:
                    logging.warning(f"Enhanced description processing failed for {job.title}: {e}")
                    job.description_type = "basic"
            
            # Set priority based on score
            if job.score >= self.config.analysis.score_threshold:
                job.priority = Priority.HIGH
            elif job.score >= 60:
                job.priority = Priority.NORMAL
            else:
                job.priority = Priority.LOW
            
            job.analyzed_at = datetime.now()
            
            logging.info(f"Full analysis completed for {job.title}: {job.score}/100 - {job.priority.value}")
            return job
            
        except Exception as e:
            logging.error(f"Full analysis failed for {job.title}: {e}")
            # Use quick score as fallback
            job.score = self.quick_score(job)
            job.score_rationale = f"Full analysis failed, using quick score. Error: {str(e)[:100]}"
            job.tailored_bullets = self._get_generic_bullets()
            job.priority = Priority.NORMAL if job.score >= 60 else Priority.LOW
            job.analyzed_at = datetime.now()
            return job
    
    def _parse_scoring_results(self, job: Job, score_output: str):
        """Parse scoring results from AI output"""
        import re
        
        try:
            # Extract score
            score_patterns = [
                r'SCORE:\s*(\d+)',
                r'Score:\s*(\d+)',
                r'(\d+)/100',
                r'(\d+)\s*out of 100'
            ]
            
            for pattern in score_patterns:
                match = re.search(pattern, score_output, re.IGNORECASE)
                if match:
                    score_value = int(match.group(1))
                    if 0 <= score_value <= 100:
                        job.score = score_value
                        break
            else:
                job.score = self.quick_score(job)
            
            # Extract rationale
            rationale_match = re.search(
                r'RATIONALE:\s*(.+?)(?=CONCERNS|BULLET|$)', 
                score_output, 
                re.IGNORECASE | re.DOTALL
            )
            if rationale_match:
                job.score_rationale = rationale_match.group(1).strip()
            else:
                job.score_rationale = "AI analysis completed with standard scoring criteria"
                
        except Exception as e:
            logging.warning(f"Could not parse scoring results: {e}")
            job.score = self.quick_score(job)
            job.score_rationale = "Scoring analysis completed"
    
    def _parse_bullets_results(self, job: Job, bullets_output: str):
        """Parse bullet results from AI output"""
        import re
        
        try:
            # Extract bullets using patterns
            bullet_patterns = [
                r'BULLET\s*\d+:\s*(.+?)(?=BULLET\s*\d+:|$)',
                r'•\s*(.+?)(?=•|$)',
                r'^\d+\.\s*(.+?)(?=^\d+\.|$)'
            ]
            
            bullets = []
            for pattern in bullet_patterns:
                matches = re.findall(pattern, bullets_output, re.MULTILINE | re.IGNORECASE)
                if matches and len(matches) >= 2:
                    bullets = [match.strip() for match in matches if len(match.strip()) > 20][:3]
                    break
            
            if not bullets:
                # Fallback: split by newlines and filter
                lines = bullets_output.split('\n')
                bullets = [line.strip().lstrip('•-*').strip() for line in lines 
                          if len(line.strip()) > 30 and not line.strip().startswith(('BULLET', 'Format'))][:3]
            
            job.tailored_bullets = bullets if bullets else self._get_generic_bullets()
            
        except Exception as e:
            logging.warning(f"Could not parse bullets: {e}")
            job.tailored_bullets = self._get_generic_bullets()

    def generate_bullets(self, job_obj):
        """
        Generate tailored resume bullets for a given Job object.
        """
        # If job already has bullets, return them
        if getattr(job_obj, "tailored_bullets", None) and len(job_obj.tailored_bullets) > 0 and job_obj.tailored_bullets[0] != "Quick assessment - full analysis available on request":
            return job_obj.tailored_bullets

        try:
            bullets_task = Task(
                description=self._create_bullets_prompt(job_obj),
                expected_output="Three tailored resume bullets in specified format",
                agent=self.tailor
            )
            crew = Crew(
                agents=[self.tailor],
                tasks=[bullets_task],
                verbose=False
            )
            results = crew.kickoff()
            # Parse bullets
            if hasattr(results, 'tasks_output') and len(results.tasks_output) >= 1:
                self._parse_bullets_results(job_obj, str(results.tasks_output[0].raw))
            else:
                self._parse_bullets_results(job_obj, str(results))
            return job_obj.tailored_bullets
        except Exception as e:
            logging.error(f"Bullet generation failed for job: {job_obj.title}: {e}")
            return self._get_generic_bullets()
            
    def _get_generic_bullets(self) -> List[str]:
        """Get generic resume bullets as fallback"""
        return [
            "Led technical initiatives resulting in measurable performance improvements",
            "Collaborated with cross-functional teams to deliver high-impact solutions",
            "Implemented best practices driving operational efficiency and cost optimization"
        ]
    
    def analyze_job_lazy(self, job: Job) -> Job:
        """Analyze job with lazy loading - only quick score initially"""
        if not job.score:
            job.score = self.quick_score(job)
            
            # Set priority based on quick score
            if job.score >= self.config.analysis.score_threshold:
                job.priority = Priority.HIGH
            elif job.score >= 60:
                job.priority = Priority.NORMAL
            else:
                job.priority = Priority.LOW
                
            job.score_rationale = "Quick assessment - full analysis available on request"
            job.analyzed_at = datetime.now()
        
        return job
    
    def analyze_batch(self, jobs: List[Job], full_analysis: bool = None) -> List[Job]:
        """Analyze jobs in batch with configurable depth"""
        if full_analysis is None:
            full_analysis = not self.config.analysis.lazy_analysis
        
        analyzed_jobs = []
        
        if full_analysis:
            # Full analysis for all jobs
            batch_size = self.config.analysis.batch_size
            for i in range(0, len(jobs), batch_size):
                batch = jobs[i:i + batch_size]
                logging.info(f"Full analysis batch {i//batch_size + 1}/{(len(jobs)-1)//batch_size + 1}")
                
                for job in batch:
                    analyzed_job = self.analyze_job_full(job)
                    analyzed_jobs.append(analyzed_job)
                
                # Brief pause between batches
                if i + batch_size < len(jobs):
                    time.sleep(2)
        else:
            # Lazy analysis - quick scores only
            for job in jobs:
                analyzed_job = self.analyze_job_lazy(job)
                analyzed_jobs.append(analyzed_job)
            
            logging.info(f"Quick analysis completed for {len(jobs)} jobs")
        
        return analyzed_jobs
    
    def generate_bullets_for_job(self, job_id: int, jobs: List[Job]) -> List[str]:
        """Generate resume bullets for a specific job (API endpoint)"""
        if job_id < 0 or job_id >= len(jobs):
            return self._get_generic_bullets()
            
        job = jobs[job_id]
        
        # If job already has bullets, return them
        if job.tailored_bullets and len(job.tailored_bullets) > 0 and job.tailored_bullets[0] != "Quick assessment - full analysis available on request":
            return job.tailored_bullets
            
        try:
            # Create bullet generation task
            bullets_task = Task(
                description=self._create_bullets_prompt(job),
                expected_output="Three tailored resume bullets in specified format",
                agent=self.tailor
            )
            
            # Run analysis
            crew = Crew(
                agents=[self.tailor],
                tasks=[bullets_task],
                verbose=False
            )
            
            results = crew.kickoff()
            
            # Parse bullets
            if hasattr(results, 'tasks_output') and len(results.tasks_output) >= 1:
                self._parse_bullets_results(job, str(results.tasks_output[0].raw))
            else:
                self._parse_bullets_results(job, str(results))
            
            return job.tailored_bullets
            
        except Exception as e:
            logging.error(f"Bullet generation failed for job_id {job_id}: {e}")
            return self._get_generic_bullets()
    
    def get_analysis_stats(self, jobs: List[Job]) -> Dict:
        """Get analysis statistics"""
        analyzed_jobs = [j for j in jobs if j.analyzed_at]
        full_analysis_jobs = [j for j in jobs if j.tailored_bullets and len(j.tailored_bullets) > 0 and j.tailored_bullets[0] != "Quick assessment - full analysis available on request"]
        premium_jobs = [j for j in jobs if j.score >= 86]
        
        return {
            "total_jobs": len(jobs),
            "analyzed_jobs": len(analyzed_jobs),
            "full_analysis_jobs": len(full_analysis_jobs),
            "premium_jobs": len(premium_jobs),
            "high_priority": len([j for j in jobs if j.priority == Priority.HIGH]),
            "avg_score": sum(j.score for j in jobs) / len(jobs) if jobs else 0,
            "analysis_coverage": len(analyzed_jobs) / len(jobs) * 100 if jobs else 0
        }