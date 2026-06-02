from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .file_parsing import parse_uploaded_files
from .models import Course, Module


class ModuleFileUploadTests(TestCase):
    def test_text_file_upload_is_parsed_into_module_content(self):
        course = Course.objects.create(code="MBA101", name="MBA")
        uploaded_file = SimpleUploadedFile(
            "syllabus.txt",
            b"Strategy\nLeadership\nAnalytics",
            content_type="text/plain",
        )

        response = self.client.post(
            reverse("module-create", args=[course.pk]),
            {
                "name": "Business Strategy",
                "content": "Pasted overview",
                "order": "1",
                "content_files": [uploaded_file],
            },
        )

        self.assertRedirects(response, reverse("course-detail", args=[course.pk]))
        module = Module.objects.get(course=course)
        self.assertIn("Pasted overview", module.content)
        self.assertIn("--- syllabus.txt ---", module.content)
        self.assertIn("Leadership", module.content)

    def test_upload_parser_rejects_unsupported_file_type(self):
        uploaded_file = SimpleUploadedFile(
            "syllabus.csv",
            b"Strategy,Leadership",
            content_type="text/csv",
        )

        with self.assertRaisesMessage(Exception, "unsupported file type"):
            parse_uploaded_files([uploaded_file])


class CourseFilterTests(TestCase):
    def test_course_list_filters_by_module_university_and_country(self):
        matching_course = Course.objects.create(code="MBA101", name="MBA")
        other_course = Course.objects.create(code="CS101", name="Computer Science")
        matching_course.university_name = "Johannesburg Business School"
        matching_course.country = "South Africa"
        matching_course.save(update_fields=["university_name", "country"])
        other_course.university_name = "Other School"
        other_course.country = "Namibia"
        other_course.save(update_fields=["university_name", "country"])
        Module.objects.create(
            course=matching_course,
            name="Strategy",
            content="Leadership strategy",
        )
        Module.objects.create(
            course=other_course,
            name="Programming",
            content="Python programming",
            university_name="Other School",
            country="Namibia",
        )

        response = self.client.get(
            reverse("course-list"),
            {"university": "Johannesburg Business School", "country": "South Africa"},
        )

        self.assertContains(response, "MBA")
        self.assertContains(response, "Johannesburg Business School")
        self.assertNotContains(response, "Computer Science")

    def test_module_create_inherits_course_university_and_country(self):
        course = Course.objects.create(
            code="MBA102",
            name="MBA",
            university_name="University of Johannesburg",
            country="South Africa",
        )

        response = self.client.post(
            reverse("module-create", args=[course.pk]),
            {
                "name": "Leadership",
                "content": "Leadership and strategy",
                "order": "1",
            },
        )

        self.assertRedirects(response, reverse("course-detail", args=[course.pk]))
        module = Module.objects.get(course=course)
        self.assertEqual(module.university_name, "University of Johannesburg")
        self.assertEqual(module.country, "South Africa")
