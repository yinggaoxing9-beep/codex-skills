#!/usr/bin/env python3
"""Bounded, read-only Open Library metadata lookup; Python standard library only."""
import argparse
from datetime import datetime, timezone
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://openlibrary.org"
MAX_BYTES = 4 * 1024 * 1024
FIELDS = ",".join([
    "key", "title", "author_name", "author_key", "first_publish_year",
    "editions", "editions.key", "editions.title", "editions.language",
    "editions.ebook_access",
])


class BookError(Exception):
    pass


def normalize_isbn(value):
    """Validate ISBN-10/13 and return canonical ISBN-13; never infer allocation."""
    value = re.sub(r"^ISBN(?:-1[03])?:?\s*", "", value.strip(), flags=re.I)
    value = re.sub(r"[\s-]", "", value).upper()
    if re.fullmatch(r"[0-9]{9}[0-9X]", value):
        digits = [int(c) if c != "X" else 10 for c in value]
        if sum((10 - i) * n for i, n in enumerate(digits)) % 11:
            raise BookError("Invalid ISBN-10 checksum")
        stem = "978" + value[:9]
        check = (-sum(int(c) * (1 if i % 2 == 0 else 3)
                      for i, c in enumerate(stem))) % 10
        return stem + str(check)
    if re.fullmatch(r"97[89][0-9]{10}", value):
        if sum(int(c) * (1 if i % 2 == 0 else 3)
               for i, c in enumerate(value)) % 10:
            raise BookError("Invalid ISBN-13 checksum")
        return value
    raise BookError("Expected an ISBN-10 or a 978/979 ISBN-13")


def ol_key(value, kind):
    """Accept identifiers only; never convert upstream text into arbitrary URLs."""
    if not isinstance(value, str):
        return None
    value = value.rsplit("/", 1)[-1]
    suffix = {"works": "W", "books": "M", "authors": "A"}[kind]
    return "/" + kind + "/" + value if re.fullmatch(r"OL[0-9]+" + suffix, value) else None


def strings(value):
    return [x for x in value if isinstance(x, str)] if isinstance(value, list) else []


def fetch_json(url, missing_ok=False):
    contact = os.environ.get("BOOK_DISCOVERY_CONTACT", "").strip()
    agent = "book-discovery/1" + (f" ({contact})" if contact else "")
    req = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": agent,
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise BookError("Response exceeds bounded metadata size")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise BookError("Expected a JSON object")
        return data
    except urllib.error.HTTPError as error:
        if error.code == 404 and missing_ok:
            return None
        raise BookError(f"Open Library HTTP {error.code}; no automatic retry") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise BookError("Network request failed; access is unverified") from None
    except (ValueError, UnicodeError):
        raise BookError("Invalid JSON response; not a valid empty search") from None


def access(provider_access=None):
    return {"provider_access": provider_access, "observed": "metadata_only",
            "full_text_verified": False}


def work_record(doc, request_url):
    key = ol_key(doc.get("key"), "works")
    if not key or not isinstance(doc.get("title"), str):
        raise BookError("Malformed work record")
    editions = doc.get("editions", {})
    rows = editions.get("docs", []) if isinstance(editions, dict) else []
    if not isinstance(rows, list):
        raise BookError("Malformed edition candidates")
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            raise BookError("Malformed edition candidate")
        eid = ol_key(row.get("key"), "books")
        if eid:
            candidates.append({
                "key": eid, "title": row.get("title"),
                "languages": strings(row.get("language")),
                "provider_access": row.get("ebook_access"),
            })
    return {
        "record_type": "book_work", "title": doc["title"],
        "authors": strings(doc.get("author_name")),
        "author_keys": strings(doc.get("author_key")),
        "identifiers": {"openlibrary_work": key},
        "first_publish_year": doc.get("first_publish_year"),
        "edition_candidates": candidates,
        "source_url": BASE + key, "access": access(),
        "verification": "candidate",
        "provenance": {"provider": "openlibrary", "request_url": request_url},
    }


def edition_record(doc, request_url, requested_isbn=None, requested_olid=None):
    key = ol_key(doc.get("key"), "books")
    if not key or not isinstance(doc.get("title"), str):
        raise BookError("Malformed edition record")
    identifiers = {"openlibrary_edition": key,
                   "isbn_10": strings(doc.get("isbn_10")),
                   "isbn_13": strings(doc.get("isbn_13"))}
    works = doc.get("works", [])
    if isinstance(works, list):
        identifiers["openlibrary_work"] = [
            k for row in works if isinstance(row, dict)
            if (k := ol_key(row.get("key"), "works"))
        ]
    status = "record_retrieved"
    warnings = []
    if requested_isbn:
        canonical = set()
        for value in identifiers["isbn_10"] + identifiers["isbn_13"]:
            try:
                canonical.add(normalize_isbn(value))
            except BookError:
                warnings.append("Provider returned an invalid ISBN; retained as reported")
        if not canonical:
            status = "identifier_unconfirmed"
            warnings.append("Edition has no valid ISBN to confirm the requested identifier")
        elif requested_isbn in canonical:
            status = "identifier_match"
        else:
            status = "identifier_mismatch"
            warnings.append("Returned edition ISBN does not match the requested ISBN")
    if requested_olid and key != requested_olid:
        status = "identifier_mismatch"
        warnings.append("Returned edition key does not match the requested OLID")
    authors = doc.get("authors", [])
    languages = doc.get("languages", [])
    return {
        "record_type": "book_edition", "title": doc["title"], "authors": [],
        "author_keys": [row["key"] for row in authors
                        if isinstance(row, dict) and isinstance(row.get("key"), str)]
                       if isinstance(authors, list) else [],
        "by_statement": doc.get("by_statement"),
        "identifiers": identifiers, "publish_date": doc.get("publish_date"),
        "publishers": strings(doc.get("publishers")),
        "edition_name": doc.get("edition_name"),
        "physical_format": doc.get("physical_format"),
        "number_of_pages": doc.get("number_of_pages"),
        "languages": [row["key"].rsplit("/", 1)[-1] for row in languages
                      if isinstance(row, dict) and isinstance(row.get("key"), str)]
                     if isinstance(languages, list) else [],
        "contributors": doc.get("contributions", []),
        "source_url": BASE + key, "access": access(),
        "verification": status,
        "provenance": {"provider": "openlibrary", "request_url": request_url},
    }, warnings


def envelope(operation, query, records, warnings, status="ok"):
    return {
        "schema_version": "book-discovery/1", "operation": operation,
        "query": query, "provider": "openlibrary",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "status": status, "records": records, "warnings": warnings,
    }


def run(args):
    if args.operation == "search":
        query = {k: getattr(args, k) for k in ("query", "title", "author", "language")
                 if getattr(args, k)}
        if not any(query.get(k, "").strip() for k in ("query", "title", "author")):
            raise BookError("Provide a non-empty query, title or author")
        if not 1 <= args.limit <= 20:
            raise BookError("limit must be between 1 and 20")
        if args.language and not re.fullmatch(r"[a-z]{3}", args.language):
            raise BookError("language must be a three-letter MARC code")
        q = args.query.strip() if args.query else ""
        if args.language:
            q = f"({q}) AND language:{args.language}" if q else "language:" + args.language
        params = {"fields": FIELDS, "limit": args.limit}
        for field, value in (("q", q), ("title", args.title), ("author", args.author)):
            if value:
                params[field] = value
        url = BASE + "/search.json?" + urllib.parse.urlencode(params)
        payload = fetch_json(url)
        docs = payload.get("docs")
        if not isinstance(docs, list) or not all(isinstance(x, dict) for x in docs):
            raise BookError("Search response has no valid docs array")
        records = [work_record(doc, url) for doc in docs[:args.limit]]
        return envelope("search", query, records, [
            "Work matches are candidates; edition and full text remain unverified"
        ])
    isbn = normalize_isbn(args.isbn) if args.isbn else None
    olid = ol_key(args.olid, "books") if args.olid else None
    if args.olid and not olid:
        raise BookError("Expected an edition OLID ending in M")
    query = {"isbn": isbn} if isbn else {"olid": olid}
    url = BASE + ("/isbn/" + isbn if isbn else olid) + ".json"
    payload = fetch_json(url, missing_ok=True)
    if payload is None:
        return envelope("lookup", query, [], ["Not found in Open Library"], "not_found")
    record, warnings = edition_record(payload, url, isbn, olid)
    warnings.append("Directory record only; full text, authors and edition details may need cross-checking")
    status = "inconsistent" if record["verification"] == "identifier_mismatch" else "ok"
    return envelope("lookup", query, [record], warnings, status)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    search = commands.add_parser("search", help="Find work and edition candidates")
    search.add_argument("--query")
    search.add_argument("--title")
    search.add_argument("--author")
    search.add_argument("--language")
    search.add_argument("--limit", type=int, default=5)
    lookup = commands.add_parser("lookup", help="Read one edition record")
    identifiers = lookup.add_mutually_exclusive_group(required=True)
    identifiers.add_argument("--isbn")
    identifiers.add_argument("--olid")
    args = parser.parse_args(argv)
    try:
        result = run(args)
        code = 1 if result["status"] == "inconsistent" else 0
    except BookError as error:
        query = {k: v for k, v in vars(args).items() if k != "operation" and v is not None}
        result = envelope(args.operation, query, [], [str(error)], "error")
        code = 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
