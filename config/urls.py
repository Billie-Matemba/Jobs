from django.contrib import admin
from django.urls import path
from courses.views import (
    CourseListView, CourseCreateView, CourseDetailView,
    CourseEditView, CourseDeleteView,
    ModuleCreateView, ModuleEditView, ModuleDeleteView,
)
from dashboard.views import (
    DashboardView, JobUploadView, JobListView, JobDeleteView,
    RunAnalysisView, AnalysisResultsView,
    StartContinuousJobsView, StartJobsOnlyView, StopTaskView, TaskListView,
    task_status_api, results_json, dashboard_metrics, similarity_network,
)
from course_scraper.views import CourseScraperView, StartCourseScrapeView, scrape_status_api
from methodology.views import MethodologyView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Dashboard
    path("", DashboardView.as_view(), name="home"),

    # Courses
    path("courses/", CourseListView.as_view(), name="course-list"),
    path("courses/new/", CourseCreateView.as_view(), name="course-create"),
    path("courses/<int:pk>/", CourseDetailView.as_view(), name="course-detail"),
    path("courses/<int:pk>/edit/", CourseEditView.as_view(), name="course-edit"),
    path("courses/<int:pk>/delete/", CourseDeleteView.as_view(), name="course-delete"),
    path("course-scraper/", CourseScraperView.as_view(), name="course-scraper"),
    path("course-scraper/start/", StartCourseScrapeView.as_view(), name="course-scraper-start"),

    # Modules
    path("courses/<int:course_pk>/modules/add/", ModuleCreateView.as_view(), name="module-create"),
    path("modules/<int:pk>/edit/", ModuleEditView.as_view(), name="module-edit"),
    path("modules/<int:pk>/delete/", ModuleDeleteView.as_view(), name="module-delete"),

    # Jobs
    path("jobs/", JobListView.as_view(), name="job-list"),
    path("jobs/upload/", JobUploadView.as_view(), name="job-upload"),
    path("jobs/<int:pk>/delete/", JobDeleteView.as_view(), name="job-delete"),

    # Analysis
    path("analysis/run/", RunAnalysisView.as_view(), name="run-analysis"),
    path("analysis/live/start/", StartContinuousJobsView.as_view(), name="start-live-jobs"),
    path("jobs/fetch-only/start/", StartJobsOnlyView.as_view(), name="start-jobs-only"),
    path("tasks/<int:pk>/stop/", StopTaskView.as_view(), name="stop-task"),
    path("analysis/results/", AnalysisResultsView.as_view(), name="analysis-results"),
    path("methodology/", MethodologyView.as_view(), name="methodology"),

    # Tasks
    path("tasks/", TaskListView.as_view(), name="task-list"),
    path("api/task/<int:pk>/", task_status_api, name="task-status-api"),
    path("api/results/", results_json, name="results-json"),
    path("api/dashboard/metrics/", dashboard_metrics, name="dashboard-metrics"),
    path("api/dashboard/network/", similarity_network, name="similarity-network"),
    path("api/course-scraper/status/", scrape_status_api, name="course-scraper-status"),
]
