from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from .services import crawl_programme_pages, discover_sitemap_page_urls


class SitemapDiscoveryTests(SimpleTestCase):
    def test_discovers_only_relevant_same_domain_urls(self):
        responses = {
            "https://example.edu/sitemap.xml": Mock(
                ok=True,
                content=b"""
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                  <url><loc>https://example.edu/programmes/mba/</loc></url>
                  <url><loc>https://example.edu/news/campus-open-day/</loc></url>
                  <url><loc>https://other.edu/programmes/mba/</loc></url>
                  <url><loc>https://example.edu/courses/leadership/</loc></url>
                </urlset>
                """,
            ),
            "https://example.edu/sitemap_index.xml": Mock(
                ok=True,
                content=b"<sitemapindex></sitemapindex>",
            ),
            "https://example.edu/robots.txt": Mock(ok=True, text=""),
        }

        session = Mock()
        session.get.side_effect = lambda url, timeout: responses[url]

        urls = discover_sitemap_page_urls("https://example.edu/mba/", session, max_urls=10)

        self.assertEqual(
            urls,
            [
                "https://example.edu/programmes/mba/",
                "https://example.edu/courses/leadership/",
            ],
        )

    @patch("course_scraper.services.requests.Session")
    def test_seed_url_is_crawled_even_before_text_relevance_matches(self, session_class):
        session = Mock()
        session_class.return_value = session

        responses = {
            "https://example.edu/robots.txt": Mock(ok=True, text=""),
            "https://example.edu/sitemap.xml": Mock(
                ok=True,
                content=b"<urlset></urlset>",
            ),
            "https://example.edu/sitemap_index.xml": Mock(
                ok=True,
                content=b"<sitemapindex></sitemapindex>",
            ),
            "https://example.edu/mba/": Mock(
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><title>Admissions</title><h1>Admissions</h1><p>Overview</p></html>",
            ),
        }
        for response in responses.values():
            response.raise_for_status = Mock()
        session.get.side_effect = lambda url, timeout: responses[url]

        pages = crawl_programme_pages("https://example.edu/mba/", max_pages=8)

        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].url, "https://example.edu/mba/")
