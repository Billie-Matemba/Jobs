from unittest.mock import patch

from django.test import SimpleTestCase

from .ingestion import fetch_from_adzuna


class AdzunaIngestionTests(SimpleTestCase):
    @patch("jobs.ingestion.fetch_adzuna_page")
    def test_fetch_from_adzuna_passes_progress_callback(self, fetch_page):
        calls = []

        def progress_callback(progress):
            calls.append(progress)

        fetch_page.return_value = {
            "page": 1,
            "saved": 0,
            "duplicates": 0,
            "seen": 0,
            "total_count": 0,
            "db_total": 0,
            "has_more": False,
        }

        saved = fetch_from_adzuna("MBA", "south africa", max_results=50, progress_callback=progress_callback)

        self.assertEqual(saved, 0)
        fetch_page.assert_called_once()
        self.assertIs(fetch_page.call_args.kwargs["progress_callback"], progress_callback)
