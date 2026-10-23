"""Synthetic protocol fixtures; no downloads, secrets, or live network."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error

path = Path(__file__).resolve().parents[1] / "scripts" / "bookctl.py"
spec = importlib.util.spec_from_file_location("bookctl", path)
bookctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bookctl)


class BookTests(unittest.TestCase):
    def test_isbn10_x_matches_isbn13(self):
        self.assertEqual(bookctl.normalize_isbn("ISBN-10: 0-8044-2957-X"), "9780804429573")

    def test_979_and_invalid_checksums(self):
        self.assertEqual(bookctl.normalize_isbn("9791090636071"), "9791090636071")
        for value in ("9780804429574", "0804429570", "123", "978080442957X"):
            with self.subTest(value=value), self.assertRaises(bookctl.BookError):
                bookctl.normalize_isbn(value)

    def test_work_does_not_invent_edition_metadata_or_fulltext(self):
        doc = {"key": "OL1W", "title": "Synthetic work", "first_publish_year": 1900,
               "isbn": ["9780804429573"], "publisher": ["Unmatched aggregate"],
               "editions": {"docs": [{"key": "/books/OL2M", "title": "Translation",
                                     "language": ["eng"], "ebook_access": "public"}]}}
        result = bookctl.work_record(doc, "https://openlibrary.org/search.json")
        self.assertNotIn("isbn_13", result["identifiers"])
        self.assertNotIn("publish_date", result)
        self.assertFalse(result["access"]["full_text_verified"])
        self.assertEqual(result["edition_candidates"][0]["title"], "Translation")

    def test_lookup_matches_equivalent_isbn_and_preserves_edition_date(self):
        doc = {"key": "/books/OL2M", "title": "Synthetic edition",
               "isbn_10": ["080442957X"], "publish_date": "Revised 2001",
               "physical_format": "Audio"}
        result, _ = bookctl.edition_record(doc, "url", "9780804429573")
        self.assertEqual(result["verification"], "identifier_match")
        self.assertEqual(result["publish_date"], "Revised 2001")
        self.assertEqual(result["physical_format"], "Audio")
        self.assertFalse(result["access"]["full_text_verified"])

    def test_mismatch_and_missing_identifiers_are_not_verified(self):
        doc = {"key": "/books/OL2M", "title": "Synthetic edition",
               "isbn_13": ["9791090636071"]}
        result, _ = bookctl.edition_record(doc, "url", "9780804429573")
        self.assertEqual(result["verification"], "identifier_mismatch")
        doc.pop("isbn_13")
        result, _ = bookctl.edition_record(doc, "url", "9780804429573")
        self.assertEqual(result["verification"], "identifier_unconfirmed")
        result, _ = bookctl.edition_record(doc, "url", requested_olid="/books/OL3M")
        self.assertEqual(result["verification"], "identifier_mismatch")

    def test_language_constraint_and_limit(self):
        with patch.object(bookctl, "fetch_json", return_value={"docs": []}) as fetch:
            with contextlib.redirect_stdout(io.StringIO()):
                code = bookctl.main(["search", "--query", "alpha OR beta",
                                     "--language", "chi", "--limit", "3"])
        self.assertEqual(code, 0)
        from urllib.parse import parse_qs, urlsplit
        params = parse_qs(urlsplit(fetch.call_args.args[0]).query)
        self.assertEqual(params["q"], ["(alpha OR beta) AND language:chi"])
        self.assertEqual(params["limit"], ["3"])

    def test_protocol_failure_is_not_empty_success(self):
        for data in ({}, {"docs": "bad"}, {"docs": [{"key": "OL1W"}]}):
            with self.subTest(data=data), patch.object(bookctl, "fetch_json", return_value=data):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = bookctl.main(["search", "--title", "Synthetic"])
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(output.getvalue())["status"], "error")

    def test_error_and_not_found_are_distinct(self):
        for result, status, code in ((None, "not_found", 0), (bookctl.BookError("HTTP 429"), "error", 2)):
            kwargs = {"side_effect": result} if isinstance(result, Exception) else {"return_value": result}
            with patch.object(bookctl, "fetch_json", **kwargs):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    actual = bookctl.main(["lookup", "--isbn", "9780804429573"])
                self.assertEqual(actual, code)
                self.assertEqual(json.loads(output.getvalue())["status"], status)
                self.assertEqual(json.loads(output.getvalue())["query"]["isbn"], "9780804429573")

    def test_http_404_only_is_normal_missing(self):
        for status in (404, 403, 429, 503):
            error = urllib.error.HTTPError("url", status, "test", {}, None)
            with patch.object(bookctl.urllib.request, "urlopen", side_effect=error):
                if status == 404:
                    self.assertIsNone(bookctl.fetch_json("https://openlibrary.org/x", True))
                else:
                    with self.assertRaises(bookctl.BookError):
                        bookctl.fetch_json("https://openlibrary.org/x", True)

    def test_invalid_input_does_not_make_request(self):
        for argv in (["lookup", "--isbn", "bad"], ["lookup", "--olid", "OL1W"],
                     ["search", "--query", "  "], ["search", "--title", "x", "--limit", "21"]):
            with self.subTest(argv=argv), patch.object(bookctl, "fetch_json") as fetch:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(bookctl.main(argv), 2)
                fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
