from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from .models import ScrapeRun
from .school_urls import configured_schools
from .services import start_scrape_thread


class CourseScraperView(TemplateView):
    template_name = "course_scraper/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["schools"] = list(enumerate(configured_schools()))
        ctx["runs"] = ScrapeRun.objects.prefetch_related("candidates")[:12]
        ctx["running"] = ScrapeRun.objects.filter(status__in=["pending", "running"]).first()
        return ctx


class StartCourseScrapeView(View):
    def post(self, request):
        selected = request.POST.getlist("school")
        school_indexes = [int(value) for value in selected if value.isdigit()]
        schools = configured_schools()
        if not school_indexes:
            school_indexes = list(range(len(schools)))

        if ScrapeRun.objects.filter(status__in=["pending", "running"]).exists():
            messages.warning(request, "A course scrape is already running.")
            return redirect("course-scraper")

        label = schools[school_indexes[0]]["name"] if len(school_indexes) == 1 else "South African business schools"
        run = ScrapeRun.objects.create(school_name=label)
        start_scrape_thread(run.id, school_indexes)
        messages.success(request, f"Course scrape started for {label}.")
        return redirect("course-scraper")


def scrape_status_api(request):
    runs = []
    for run in ScrapeRun.objects.prefetch_related("candidates")[:8]:
        runs.append({
            "id": run.id,
            "school_name": run.school_name,
            "status": run.status,
            "pages_seen": run.pages_seen,
            "courses_created": run.courses_created,
            "modules_created": run.modules_created,
            "notes": run.notes,
            "candidates": run.candidates.count(),
        })
    return JsonResponse({"runs": runs})
