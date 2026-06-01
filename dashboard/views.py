from django.db.models import Avg
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView, ListView

from courses.models import Course
from jobs.models import JobAdvert
from analysis.models import AnalysisRun, GapResult, SkillMatrix, TaskRecord
# Plain functions now — no .delay(), no Celery
from analysis.tasks import (
    run_gap_analysis_task,
    import_csv_task,
    fetch_adzuna_task,
    start_continuous_adzuna_task,
    start_continuous_job_task,
    stop_task,
)


def task_debug_hint(notes):
    text = (notes or "").lower()
    if "no courses found" in text:
        return "Create a course, add at least one module with content, then start the live pipeline again."
    if "no job adverts found" in text:
        return "Import jobs or let the live pipeline fetch jobs before queueing analysis."
    if "missing adzuna credentials" in text:
        return "Add ADZUNA_APP_ID and ADZUNA_APP_KEY to your .env file, then restart the server."
    if "adzuna api limit reached" in text or "http 429" in text:
        return "The app will retry automatically. Increase the wait interval if this repeats."
    if "adzuna authentication error" in text:
        return "Check ADZUNA_APP_ID and ADZUNA_APP_KEY in .env, then restart the server."
    if "adzuna request error" in text:
        return "Check the keyword, location, and Adzuna country setting."
    if "adzuna network error" in text or "adzuna server error" in text:
        return "This is usually temporary. The jobs-only loop retries automatically."
    if "no text documents" in text:
        return "Add module and job descriptions with enough text for Word2Vec training."
    return "Open Background Tasks for the full task history and check the latest task notes."


def bounded_int(value, default, minimum, maximum):
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


class DashboardView(TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["course_count"] = Course.objects.count()
        ctx["module_count"] = sum(c.modules.count() for c in Course.objects.prefetch_related("modules"))
        ctx["job_count"] = JobAdvert.objects.count()
        ctx["last_run"] = AnalysisRun.objects.first()
        ctx["pending_tasks"] = TaskRecord.objects.filter(status__in=["PENDING", "STARTED"]).count()
        ctx["live_task"] = (
            TaskRecord.objects
            .filter(run_name__startswith="Jobs Only", status__in=["PENDING", "STARTED"])
            .first()
            or TaskRecord.objects
            .filter(run_name__startswith="Live Pipeline", status__in=["PENDING", "STARTED"])
            .first()
        )
        latest_jobs_only = TaskRecord.objects.filter(run_name__startswith="Jobs Only").order_by("-created_at").first()
        ctx["should_autostart_jobs"] = not ctx["live_task"] and not (latest_jobs_only and latest_jobs_only.status == "STOPPED")
        ctx["avg_score"] = (GapResult.objects.aggregate(v=Avg("similarity_score"))["v"] or 0) * 100
        ctx["latest_results"] = GapResult.objects.select_related("course", "job").order_by("-run__created_at", "-similarity_score")[:8]
        return ctx


class JobUploadView(View):
    template_name = "jobs/upload.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        t = request.POST.get("upload_type", "csv")

        if t == "csv":
            f = request.FILES.get("csv_file")
            if not f:
                messages.error(request, "Select a CSV file first.")
                return render(request, self.template_name)
            raw = f.read()          # bytes — passed directly, no list() conversion needed
            record = TaskRecord.objects.create(run_name=f"CSV: {f.name}")
            import_csv_task(raw, record_id=record.id)   # fires thread, returns immediately
            messages.success(request, f"'{f.name}' is being imported in the background — track progress under Tasks.")
            return redirect("task-list")

        elif t == "adzuna":
            kw = request.POST.get("keyword", "").strip()
            loc = request.POST.get("location", "south africa").strip()
            n = int(request.POST.get("max_results", 50))
            if not kw:
                messages.error(request, "Enter a keyword.")
                return render(request, self.template_name)
            record = TaskRecord.objects.create(run_name=f"Adzuna: {kw}")
            fetch_adzuna_task(kw, loc, n, record_id=record.id)
            messages.success(request, f"Fetching '{kw}' jobs in the background.")
            return redirect("task-list")

        elif t == "manual":
            title = request.POST.get("title", "").strip()
            desc = request.POST.get("description", "").strip()
            if not title or not desc:
                messages.error(request, "Title and description are required.")
                return render(request, self.template_name)
            JobAdvert.objects.create(
                title=title,
                company=request.POST.get("company", "").strip(),
                location=request.POST.get("location", "").strip(),
                description=desc,
                source="upload",
            )
            messages.success(request, f"Job '{title}' added.")
            return redirect("job-list")

        return redirect("job-list")


class JobListView(ListView):
    model = JobAdvert
    template_name = "jobs/list.html"
    context_object_name = "jobs"
    paginate_by = 30


class JobDeleteView(View):
    def post(self, request, pk):
        get_object_or_404(JobAdvert, pk=pk).delete()
        messages.success(request, "Job deleted.")
        return redirect("job-list")


class RunAnalysisView(View):
    def post(self, request):
        name = request.POST.get("run_name", "Analysis Run")
        record = TaskRecord.objects.create(run_name=name)
        run_gap_analysis_task(run_name=name, record_id=record.id)   # fires thread
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "task_id": record.id,
                "status_url": reverse("task-status-api", args=[record.id]),
                "task_url": reverse("task-list"),
            })
        messages.success(request, f"Analysis '{name}' started in the background.")
        return redirect("task-list")


class StartContinuousJobsView(View):
    def post(self, request):
        live = TaskRecord.objects.filter(run_name__startswith="Live Pipeline", status__in=["PENDING", "STARTED"]).first()
        if live:
            return JsonResponse({
                "task_id": live.id,
                "status_url": reverse("task-status-api", args=[live.id]),
            })

        keyword = request.POST.get("keyword", "MBA").strip() or "MBA"
        location = request.POST.get("location", "south africa").strip() or "south africa"
        max_results = bounded_int(request.POST.get("max_results"), 50, 1, 50)
        interval = bounded_int(request.POST.get("interval_seconds"), 45, 10, 3600)
        record = TaskRecord.objects.create(run_name=f"Live Pipeline: {keyword}")
        start_continuous_job_task(keyword, location, max_results, interval, record_id=record.id)
        return JsonResponse({
            "task_id": record.id,
            "status_url": reverse("task-status-api", args=[record.id]),
        })


class StartJobsOnlyView(View):
    def post(self, request):
        live = TaskRecord.objects.filter(run_name__startswith="Jobs Only", status__in=["PENDING", "STARTED"]).first()
        if live:
            return JsonResponse({
                "task_id": live.id,
                "status_url": reverse("task-status-api", args=[live.id]),
            })

        keyword = request.POST.get("keyword", "MBA").strip() or "MBA"
        location = request.POST.get("location", "south africa").strip() or "south africa"
        max_results = bounded_int(request.POST.get("max_results"), 50, 1, 50)
        interval = bounded_int(request.POST.get("interval_seconds"), 45, 5, 3600)
        record = TaskRecord.objects.create(run_name=f"Jobs Only: {keyword}")
        start_continuous_adzuna_task(keyword, location, max_results, interval, record_id=record.id)
        return JsonResponse({
            "task_id": record.id,
            "status_url": reverse("task-status-api", args=[record.id]),
        })


class StopTaskView(View):
    def post(self, request, pk):
        stop_task(pk)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": True})
        messages.success(request, "Pause requested.")
        return redirect("home")


class AnalysisResultsView(TemplateView):
    template_name = "analysis/results.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        runs = AnalysisRun.objects.all()
        ctx["runs"] = runs

        run_id = self.request.GET.get("run")
        sel = None
        if run_id:
            sel = get_object_or_404(AnalysisRun, id=run_id)
        elif runs.exists():
            sel = runs.first()

        if sel:
            ctx["selected_run"] = sel
            ctx["results"] = (
                GapResult.objects
                .filter(run=sel)
                .select_related("course", "job")
                .order_by("-similarity_score")[:300]
            )
            ctx["job_skills"] = SkillMatrix.objects.filter(run=sel, source="jobs")[:20]
            ctx["course_skills"] = SkillMatrix.objects.filter(run=sel, source="courses")[:20]
        return ctx


class TaskListView(ListView):
    model = TaskRecord
    template_name = "analysis/tasks.html"
    context_object_name = "tasks"
    paginate_by = 40

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["has_running"] = TaskRecord.objects.filter(status__in=["PENDING", "STARTED"]).exists()
        return ctx


def task_status_api(request, pk):
    r = get_object_or_404(TaskRecord, pk=pk)
    return JsonResponse({
        "id": r.id,
        "run_name": r.run_name,
        "status": r.status,
        "progress": r.progress,
        "notes": r.notes,
        "debug_hint": task_debug_hint(r.notes) if r.status == "FAILURE" else "",
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    })


def dashboard_metrics(request):
    last_run = AnalysisRun.objects.first()
    results = GapResult.objects.filter(run=last_run).select_related("course", "job") if last_run else GapResult.objects.none()
    score_values = list(results.values_list("similarity_score", flat=True))
    buckets = [0, 0, 0, 0, 0]
    for score in score_values:
        idx = min(4, int(max(0, score) * 5))
        buckets[idx] += 1

    job_skills = []
    course_skills = []
    if last_run:
        job_skills = list(SkillMatrix.objects.filter(run=last_run, source="jobs").values("skill", "frequency")[:10])
        course_skills = list(SkillMatrix.objects.filter(run=last_run, source="courses").values("skill", "frequency")[:10])

    recent_tasks = []
    for task in TaskRecord.objects.order_by("-created_at").values("id", "run_name", "status", "progress", "notes")[:8]:
        task["debug_hint"] = task_debug_hint(task.get("notes")) if task["status"] == "FAILURE" else ""
        recent_tasks.append(task)
    return JsonResponse({
        "counts": {
            "courses": Course.objects.count(),
            "modules": sum(c.modules.count() for c in Course.objects.prefetch_related("modules")),
            "jobs": JobAdvert.objects.count(),
            "runs": AnalysisRun.objects.count(),
        },
        "last_run": {
            "id": last_run.id,
            "status": last_run.status,
            "name": last_run.name,
        } if last_run else None,
        "average_score": round((sum(score_values) / len(score_values)) * 100, 1) if score_values else 0,
        "score_buckets": buckets,
        "score_labels": ["0-20", "20-40", "40-60", "60-80", "80-100"],
        "job_skills": job_skills,
        "course_skills": course_skills,
        "recent_tasks": recent_tasks,
    })


def similarity_network(request):
    try:
        import networkx as nx
    except ImportError:
        nx = None

    last_run = AnalysisRun.objects.first()
    qs = GapResult.objects.filter(run=last_run).select_related("course", "job").order_by("-similarity_score")[:40] if last_run else []
    if nx:
        graph = nx.Graph()
        for r in qs:
            course_id = f"course-{r.course_id}"
            job_id = f"job-{r.job_id}"
            graph.add_node(course_id, label=r.course.code or r.course.name, group="course", title=r.course.name)
            graph.add_node(job_id, label=r.job.title[:28], group="job", title=r.job.title)
            graph.add_edge(course_id, job_id, value=max(1, r.similarity_percent), title=f"Cosine similarity: {r.similarity_score:.4f}")
        nodes = [{"id": n, **attrs} for n, attrs in graph.nodes(data=True)]
        edges = [{"from": u, "to": v, **attrs} for u, v, attrs in graph.edges(data=True)]
    else:
        nodes, edges, seen = [], [], set()
        for r in qs:
            course_id = f"course-{r.course_id}"
            job_id = f"job-{r.job_id}"
            if course_id not in seen:
                nodes.append({"id": course_id, "label": r.course.code or r.course.name, "group": "course", "title": r.course.name})
                seen.add(course_id)
            if job_id not in seen:
                nodes.append({"id": job_id, "label": r.job.title[:28], "group": "job", "title": r.job.title})
                seen.add(job_id)
            edges.append({"from": course_id, "to": job_id, "value": max(1, r.similarity_percent), "title": f"Cosine similarity: {r.similarity_score:.4f}"})
    return JsonResponse({"nodes": nodes, "edges": edges})


def results_json(request):
    run_id = request.GET.get("run")
    if not run_id:
        return JsonResponse({"error": "run param required"}, status=400)
    qs = GapResult.objects.filter(run_id=run_id).select_related("course", "job")
    return JsonResponse({"results": [
        {
            "course": r.course.name,
            "job": r.job.title,
            "company": r.job.company,
            "score": round(r.similarity_score * 100, 1),
            "matched": r.matched_skills,
            "missing": r.missing_skills,
        } for r in qs
    ]})
