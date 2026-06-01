from django.db import models


class ScrapeRun(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("done", "Done"),
        ("error", "Error"),
    ]

    school_name = models.CharField(max_length=255, blank=True)
    seed_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    pages_seen = models.PositiveIntegerField(default=0)
    courses_created = models.PositiveIntegerField(default=0)
    modules_created = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):   
        return f"{self.school_name or 'Course scrape'} - {self.status}"


class ScrapedCourseCandidate(models.Model):
    run = models.ForeignKey(ScrapeRun, on_delete=models.CASCADE, related_name="candidates")
    school_name = models.CharField(max_length=255)
    matched_alias = models.CharField(max_length=255, blank=True)
    source_url = models.URLField()
    course_name = models.CharField(max_length=255)
    course_code = models.CharField(max_length=80)
    confidence = models.FloatField(default=0)
    verified_by_gemini = models.BooleanField(default=False)
    imported_course_id = models.PositiveIntegerField(null=True, blank=True)
    extracted_modules = models.JSONField(default=list, blank=True)
    extracted_skills = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-confidence", "school_name"]

    def __str__(self):
        return f"{self.school_name}: {self.course_name}"
