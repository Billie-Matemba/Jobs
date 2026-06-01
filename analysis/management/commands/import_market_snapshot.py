from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from analysis.models import AnalysisRun, GapResult, SkillMatrix, TaskRecord
from courses.models import Course, Module
from jobs.models import JobAdvert


COURSES = [
    {
        "code": "BDA301",
        "name": "Business Data Analytics",
        "description": "A practical programme for analysts who turn business data into evidence-based recommendations.",
        "modules": [
            {
                "name": "Data Wrangling with Python and SQL",
                "content": (
                    "Students build repeatable data pipelines using python, sql, postgresql, excel, and data analysis. "
                    "Topics include data cleaning, joins, aggregation, validation checks, and communication of data quality issues."
                ),
                "skills": ["python", "sql", "postgresql", "excel", "data analysis", "communication"],
            },
            {
                "name": "Dashboards and Business Reporting",
                "content": (
                    "Learners design dashboards in power bi and tableau, prepare financial reporting packs, and present "
                    "clear insights to stakeholders using presentation, storytelling, and stakeholder management."
                ),
                "skills": ["power bi", "tableau", "financial reporting", "presentation", "stakeholder management"],
            },
            {
                "name": "Predictive Analytics",
                "content": (
                    "The module covers statistics, machine learning, forecasting, quantitative analysis, and model evaluation "
                    "for sales, operations, and customer service scenarios."
                ),
                "skills": ["statistics", "machine learning", "forecasting", "quantitative analysis", "customer service"],
            },
        ],
    },
    {
        "code": "HRM210",
        "name": "Human Resource Management",
        "description": "A workplace-focused HR programme covering people operations, compliance, and organisational development.",
        "modules": [
            {
                "name": "Recruitment and Talent Operations",
                "content": (
                    "Students practise recruitment, onboarding, talent management, succession planning, communication, "
                    "negotiation, and use of microsoft office for structured hiring workflows."
                ),
                "skills": ["recruitment", "onboarding", "talent management", "succession planning", "communication", "microsoft office", "negotiation"],
            },
            {
                "name": "Employment Relations and Labour Law",
                "content": (
                    "This module introduces labour law, employment equity, payroll controls, performance management, "
                    "change management, and professional problem solving in South African workplaces."
                ),
                "skills": ["labour law", "employment equity", "payroll", "performance management", "change management", "problem solving"],
            },
            {
                "name": "Learning and Organisational Development",
                "content": (
                    "Learners design training and development interventions, measure organisational development impact, "
                    "and facilitate leadership, teamwork, and stakeholder management sessions."
                ),
                "skills": ["training and development", "organisational development", "leadership", "teamwork", "stakeholder management"],
            },
        ],
    },
    {
        "code": "FIN220",
        "name": "Applied Accounting and Finance",
        "description": "A finance course focused on reporting, controls, taxation, and management decision support.",
        "modules": [
            {
                "name": "Financial Accounting Practice",
                "content": (
                    "Students prepare accounting records, bookkeeping schedules, financial reporting packs, and reconciliations "
                    "using excel, ifrs, gaap, and professional communication."
                ),
                "skills": ["accounting", "bookkeeping", "financial reporting", "excel", "ifrs", "gaap", "communication"],
            },
            {
                "name": "Management Accounting and Forecasting",
                "content": (
                    "The module develops budgeting, forecasting, cost accounting, management accounting, financial modelling, "
                    "critical thinking, and presentation skills."
                ),
                "skills": ["budgeting", "forecasting", "cost accounting", "management accounting", "financial modelling", "critical thinking", "presentation"],
            },
            {
                "name": "Tax and Audit Readiness",
                "content": (
                    "Learners review tax calculations, auditing evidence, compliance checklists, risk notes, and time management "
                    "for month-end and year-end reporting cycles."
                ),
                "skills": ["tax", "auditing", "time management", "problem solving"],
            },
        ],
    },
    {
        "code": "DIG240",
        "name": "Digital Marketing and CRM",
        "description": "A commercial digital marketing course spanning campaign execution, analytics, and customer relationship tools.",
        "modules": [
            {
                "name": "Performance Marketing Fundamentals",
                "content": (
                    "Students plan digital marketing campaigns using seo, social media, email marketing, content creation, "
                    "google analytics, and project management practices."
                ),
                "skills": ["digital marketing", "seo", "social media", "email marketing", "content creation", "google analytics", "project management"],
            },
            {
                "name": "CRM and Sales Enablement",
                "content": (
                    "This module covers crm, salesforce, customer service, negotiation, stakeholder management, reporting, "
                    "and communication for sales and account teams."
                ),
                "skills": ["crm", "salesforce", "customer service", "negotiation", "stakeholder management", "communication"],
            },
        ],
    },
]


JOBS = [
    {
        "title": "Junior Data Analyst",
        "company": "Nexa Retail Group",
        "location": "Johannesburg, Gauteng",
        "salary_min": 260000,
        "salary_max": 360000,
        "date_offset": 4,
        "skills": ["python", "sql", "excel", "power bi", "data analysis", "communication", "problem solving"],
        "description": (
            "Nexa Retail Group is hiring a Junior Data Analyst to clean sales data, write sql queries, automate excel reports, "
            "and build power bi dashboards. The role needs python, data analysis, communication, and strong problem solving."
        ),
    },
    {
        "title": "People Operations Coordinator",
        "company": "Ubuntu Health Services",
        "location": "Cape Town, Western Cape",
        "salary_min": 220000,
        "salary_max": 310000,
        "date_offset": 7,
        "skills": ["human resources", "recruitment", "onboarding", "payroll", "microsoft office", "communication", "labour law"],
        "description": (
            "Support human resources administration, recruitment scheduling, onboarding packs, payroll inputs, and labour law "
            "documentation. Candidates should be confident with microsoft office and employee communication."
        ),
    },
    {
        "title": "Assistant Accountant",
        "company": "Karoo Foods",
        "location": "Stellenbosch, Western Cape",
        "salary_min": 240000,
        "salary_max": 340000,
        "date_offset": 11,
        "skills": ["accounting", "bookkeeping", "excel", "tax", "financial reporting", "auditing", "time management"],
        "description": (
            "Assist with accounting journals, bookkeeping, excel reconciliations, tax schedules, financial reporting, and audit "
            "file preparation. The team values accuracy, auditing discipline, and time management."
        ),
    },
    {
        "title": "Digital Marketing Specialist",
        "company": "Blue Crane Travel",
        "location": "Durban, KwaZulu-Natal",
        "salary_min": 300000,
        "salary_max": 430000,
        "date_offset": 2,
        "skills": ["digital marketing", "seo", "social media", "content creation", "google analytics", "email marketing", "crm"],
        "description": (
            "Own digital marketing execution across seo, social media, email marketing, and content creation. The specialist "
            "will monitor google analytics, maintain crm segments, and report campaign performance weekly."
        ),
    },
    {
        "title": "Business Intelligence Analyst",
        "company": "Metsi Logistics",
        "location": "Pretoria, Gauteng",
        "salary_min": 420000,
        "salary_max": 580000,
        "date_offset": 14,
        "skills": ["sql", "power bi", "tableau", "statistics", "forecasting", "stakeholder management", "presentation"],
        "description": (
            "Build sql models, power bi dashboards, and tableau prototypes for logistics performance. The role uses statistics, "
            "forecasting, stakeholder management, and presentation skills to guide operational decisions."
        ),
    },
    {
        "title": "HR Business Partner",
        "company": "Sisonke Manufacturing",
        "location": "Gqeberha, Eastern Cape",
        "salary_min": 480000,
        "salary_max": 680000,
        "date_offset": 19,
        "skills": ["human resources", "performance management", "employment equity", "change management", "leadership", "negotiation"],
        "description": (
            "Partner with plant leaders on human resources planning, performance management, employment equity reporting, "
            "change management, leadership coaching, and union negotiation preparation."
        ),
    },
    {
        "title": "Graduate Financial Analyst",
        "company": "Amani Renewables",
        "location": "Midrand, Gauteng",
        "salary_min": 320000,
        "salary_max": 450000,
        "date_offset": 5,
        "skills": ["budgeting", "forecasting", "financial modelling", "excel", "quantitative analysis", "presentation"],
        "description": (
            "Prepare budgeting models, forecasting packs, financial modelling scenarios, and excel variance analysis. "
            "The graduate will use quantitative analysis and presentation skills in investment committee updates."
        ),
    },
    {
        "title": "CRM Campaign Coordinator",
        "company": "Mzansi Mobile",
        "location": "Remote, South Africa",
        "salary_min": 280000,
        "salary_max": 390000,
        "date_offset": 9,
        "skills": ["crm", "salesforce", "email marketing", "customer service", "data analytics", "communication"],
        "description": (
            "Coordinate crm journeys in salesforce, segment customers for email marketing, review customer service feedback, "
            "and use data analytics to improve retention communication."
        ),
    },
]


def overlap_score(course_skills, job_skills):
    course_set = set(course_skills)
    job_set = set(job_skills)
    if not course_set or not job_set:
        return 0.0
    coverage = len(course_set & job_set) / len(job_set)
    breadth = len(course_set & job_set) / len(course_set | job_set)
    return round(min(0.96, 0.35 + coverage * 0.45 + breadth * 0.2), 2)


def compute_gap(course_skills, job_skills):
    course_set = set(course_skills)
    job_set = set(job_skills)
    return sorted(course_set & job_set), sorted(job_set - course_set), sorted(course_set - job_set)


class Command(BaseCommand):
    help = "Seed the database with realistic courses, job adverts, and analysis results."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove existing courses, jobs, analysis runs, and task records before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            TaskRecord.objects.all().delete()
            AnalysisRun.objects.all().delete()
            JobAdvert.objects.all().delete()
            Course.objects.all().delete()

        AnalysisRun.objects.filter(name="Market Alignment Snapshot").delete()
        TaskRecord.objects.filter(task_id="market-snapshot-import").delete()

        course_objects = []
        for course_data in COURSES:
            course, _ = Course.objects.update_or_create(
                code=course_data["code"],
                defaults={
                    "name": course_data["name"],
                    "description": course_data["description"],
                },
            )
            course.modules.all().delete()
            for order, module_data in enumerate(course_data["modules"], start=1):
                Module.objects.create(
                    course=course,
                    name=module_data["name"],
                    content=module_data["content"],
                    skills_extracted=module_data["skills"],
                    order=order,
                )
            course.seed_skills = sorted({skill for module in course_data["modules"] for skill in module["skills"]})
            course_objects.append(course)

        today = timezone.localdate()
        job_objects = []
        for index, job_data in enumerate(JOBS, start=1):
            job, _ = JobAdvert.objects.update_or_create(
                external_id=f"market-posting-{today:%Y%m%d}-{index:03d}",
                source="csv",
                defaults={
                    "title": job_data["title"],
                    "company": job_data["company"],
                    "location": job_data["location"],
                    "description": job_data["description"],
                    "salary_min": job_data["salary_min"],
                    "salary_max": job_data["salary_max"],
                    "skills_extracted": job_data["skills"],
                    "date_posted": today - timedelta(days=job_data["date_offset"]),
                    "url": f"https://careers.curriculummatch.local/jobs/market-posting-{today:%Y%m%d}-{index:03d}",
                },
            )
            job.seed_skills = job_data["skills"]
            job_objects.append(job)

        run_name = "Market Alignment Snapshot"
        AnalysisRun.objects.filter(name=run_name).delete()
        run = AnalysisRun.objects.create(
            name=run_name,
            status="done",
            notes="Baseline analysis using current curriculum and job-market skill overlap.",
        )

        results = []
        for course in course_objects:
            for job in job_objects:
                matched, missing, extra = compute_gap(course.seed_skills, job.seed_skills)
                results.append(
                    GapResult(
                        run=run,
                        course=course,
                        job=job,
                        similarity_score=overlap_score(course.seed_skills, job.seed_skills),
                        matched_skills=matched,
                        missing_skills=missing,
                        extra_skills=extra,
                    )
                )
        GapResult.objects.bulk_create(results)

        job_skill_counts = {}
        for job in job_objects:
            for skill in job.seed_skills:
                job_skill_counts[skill] = job_skill_counts.get(skill, 0) + 1

        course_skill_counts = {}
        for course in course_objects:
            for skill in course.seed_skills:
                course_skill_counts[skill] = course_skill_counts.get(skill, 0) + 1

        SkillMatrix.objects.bulk_create(
            [
                SkillMatrix(run=run, source="jobs", skill=skill, frequency=frequency)
                for skill, frequency in sorted(job_skill_counts.items(), key=lambda item: (-item[1], item[0]))
            ]
        )
        SkillMatrix.objects.bulk_create(
            [
                SkillMatrix(run=run, source="courses", skill=skill, frequency=frequency)
                for skill, frequency in sorted(course_skill_counts.items(), key=lambda item: (-item[1], item[0]))
            ]
        )

        TaskRecord.objects.update_or_create(
            task_id="market-snapshot-import",
            defaults={
                "run_name": run_name,
                "status": "SUCCESS",
                "progress": 100,
                "notes": "Market snapshot imported successfully.",
                "finished_at": timezone.now(),
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(course_objects)} courses, "
                f"{sum(course.modules.count() for course in course_objects)} modules, "
                f"{len(job_objects)} jobs, and {len(results)} gap results."
            )
        )
