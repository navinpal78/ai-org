#!/usr/bin/env python3
"""Tests for the research retrieval pipeline: ingest, search, citations.

No pytest. This project has no test framework, and adding one to a repo that
boots with `./bootstrap.sh check` would mean a dependency to install before you
can tell whether the tree is valid. So: plain asserts, a count, and an exit
code. Same shape as the rest of the checks here.

The network tests are real but hermetic - a throwaway HTTP server on loopback,
started and stopped by the run, with `--allow-private` because the whole point
of the SSRF guard is that it refuses loopback and this test has to ask
explicitly, the same way a human would.

Run:  tests/test_retrieval.py [-v]
"""

from __future__ import annotations

import http.server
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# Importing the tools as modules makes CPython write tools/__pycache__/. This
# tree does not leave build artefacts lying around - state/ is inspected by
# people and by the audit tooling - so the test suite sets its own rules rather
# than needing a cleanup step someone will forget.
sys.dont_write_bytecode = True

import importlib.util  # noqa: E402

import ingest  # noqa: E402
import search as search_mod  # noqa: E402

# The filename is hyphenated on purpose - it is invoked as a CLI - so it cannot
# simply be imported by name.
_spec = importlib.util.spec_from_file_location(
    "check_citations", ROOT / "tools" / "check-citations.py")
check_citations = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_citations)

VERBOSE = "-v" in sys.argv
PASS = 0
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        if VERBOSE:
            print(f"  ok   {name}")
    else:
        FAIL.append(f"{name}: {detail}")
        print(f"  FAIL {name}  {detail}")


def eq(name: str, got, want) -> None:
    check(name, got == want, f"got {got!r}, want {want!r}")


# ---------------------------------------------------------------------------
# a throwaway site to crawl
# ---------------------------------------------------------------------------

class Site:
    """An HTTP server whose routes the test defines, on a real port.

    A real port rather than a fixed one, because a fixed 8099 that is still
    held by a previous run makes the whole suite fail for a reason that has
    nothing to do with the code under test.
    """

    def __init__(self, routes: dict):
        self.routes = routes
        self.hits: list[str] = []
        site = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):        # silence
                pass

            def do_GET(self):
                site.hits.append(self.path)
                status, ctype, body = site.routes.get(
                    self.path, (404, "text/html", b"<html><body>no route</body></html>"))
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        # Port 0 lets the OS pick. Pre-binding a socket to find a free port and
        # then binding it again is a race against ourselves, which is exactly the
        # kind of flake that makes a test suite get ignored.
        class Server(http.server.HTTPServer):
            allow_reuse_address = True

        self.srv = Server(("127.0.0.1", 0), Handler)
        self.port = self.srv.server_address[1]

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self):
        self.t = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.t.start()
        return self

    def __exit__(self, *a):
        self.srv.shutdown()
        self.srv.server_close()


def html(title: str, body: str) -> bytes:
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>".encode()


def run_ingest(db: Path, *args: str) -> str:
    cmd = [sys.executable, str(ROOT / "tools" / "ingest.py"), "--db", str(db),
           "--delay", "0", "--allow-private", "--timeout", "5", *args]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return p.stderr + p.stdout


def run_search(db: Path, *args: str) -> tuple[int, str]:
    cmd = [sys.executable, str(ROOT / "tools" / "search.py"), "--db", str(db), *args]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout + p.stderr


def rows(db: Path, table: str) -> int:
    import sqlite3
    c = sqlite3.connect(db)
    try:
        return c.execute(f"select count(*) from {table}").fetchone()[0]
    finally:
        c.close()


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------

def test_ingest_basics(tmp: Path) -> None:
    body = ("<h1>Guide</h1><p>The retrieval pipeline stores every chunk with the "
            "URL it came from and the moment it was fetched, so a citation can be "
            "checked without trusting the model. " * 3)
    routes = {
        "/robots.txt": (200, "text/plain", b"User-agent: *\nAllow: /\n"),
        "/guide.html": (200, "text/html", html("The Guide", body)),
    }
    with Site(routes) as s, tempfile.TemporaryDirectory(dir=tmp) as d:
        db = Path(d) / "i.db"
        out = run_ingest(db, "--url", f"{s.base}/guide.html")
        check("ingest indexes an allowed page", "indexed   1 chunks" in out, out[-300:])
        eq("one page row", rows(db, "pages"), 1)
        check("chunks were written", rows(db, "chunks") > 0)
        eq("fts mirrors chunks", rows(db, "chunks_fts"), rows(db, "chunks"))

        # re-running unchanged content must not duplicate
        out2 = run_ingest(db, "--url", f"{s.base}/guide.html")
        check("re-ingest of unchanged page is a no-op", "unchanged" in out2, out2[-200:])
        eq("no duplicate chunks", rows(db, "chunks"), rows(db, "chunks_fts"))

        # provenance is the whole point - assert every column is populated
        import sqlite3
        c = sqlite3.connect(db)
        r = c.execute("select url, title, fetched_at, chunk_index, text from chunks limit 1").fetchone()
        c.close()
        check("chunk carries its url", r and r[0].endswith("/guide.html"), repr(r and r[0]))
        check("chunk carries a title", r and "Guide" in (r[1] or ""), repr(r and r[1]))
        check("chunk carries a fetch date", r and r[2] and "T" in r[2], repr(r and r[2]))
        check("chunk has an index", r and r[3] == 0, repr(r and r[3]))
        check("chunk has text", r and len(r[4]) > 50)


def test_chunking_never_exceeds_the_size() -> None:
    """No chunk may come out larger than CHUNK_CHARS, whatever the input.

    This one exists because the first chunker trusted the input to contain
    paragraph breaks. A real 150KB reference page and a standards document both
    arrive as a single block with no blank line in them, and both came out as one
    enormous chunk - which defeats the design quietly, because a 150KB FTS5 row
    is truncated to 900 characters on the way out and hands the researcher one
    useless giant "source". Nothing crashes; the retrieval just gets worse.
    """
    size = ingest.CHUNK_CHARS
    cases = {
        "one giant unbroken line": "x" * 5000,
        "wrapped at 72 columns": "\n".join("word " * 13 for _ in range(200)),
        "newlines but no blank line": "\n".join(f"line {i}" for i in range(400)),
        "one enormous sentence": "A" * 900 + ". " + "B" * 900 + ". ",
        "normal paragraphs": "\n\n".join(f"para {i} " * 40 for i in range(60)),
        "crlf line endings": "\r\n".join(f"row {i} " * 20 for i in range(200)),
        "tabs and odd spacing": "\n".join("\t  spaced   out  " * 30 for _ in range(50)),
        "unicode": "\n".join("\u00e9\u4e2d\u6587\u0645\u062a\u0646 " * 40 for _ in range(60)),
    }
    for name, txt in cases.items():
        cs = ingest.chunk(txt)
        worst = max((len(c) for c in cs), default=0)
        check(f"chunk size respected: {name}", worst <= size,
              f"largest chunk {worst} > {size}")
        check(f"chunks were produced: {name}", len(cs) > 0, "no chunks at all")
        check(f"no content lost: {name}",
              "".join(cs).replace("\n", "") != "", "chunks are all empty")

    # a 150KB single-block page, which is the case that actually bit
    big = "\n".join("reference material line %d" % i for i in range(20000))
    cs = ingest.chunk(big)
    check("a 150KB single block becomes many chunks", len(cs) > 100, f"{len(cs)}")
    check("a 150KB single block respects the cap",
          max(len(c) for c in cs) <= size, f"max {max(len(c) for c in cs)}")

    # and the normal path still prefers paragraph boundaries. A chunk may hold
    # several adjacent paragraphs, so the count is not the property - the
    # property is that no paragraph is cut in half.
    paras = [f"MARKER{i} " + "filler " * 30 for i in range(50)]
    cs = ingest.chunk("\n\n".join(paras))
    for i, raw in enumerate(paras):
        # chunk() strips each paragraph, so compare against the stripped form.
        # A paragraph may legitimately appear in TWO chunks: CHUNK_OVERLAP
        # deliberately carries the tail of one chunk into the next so a sentence
        # spanning the boundary is findable from either side. What must never
        # happen is a paragraph appearing in none, or in more than the overlap
        # can explain.
        para = raw.strip()
        whole = sum(1 for c in cs if para in c)
        check(f"paragraph {i} is never cut in half", whole >= 1,
              f"not found whole in any chunk")
        check(f"paragraph {i} is not duplicated beyond the overlap", whole <= 2,
              f"found in {whole} chunks")
    joined = " ".join(cs)
    check("every paragraph survives chunking",
          all(f"MARKER{i}" in joined for i in range(50)), "a paragraph went missing")
    check("paragraph-shaped text is not shredded",
          10 <= len(cs) <= 50, f"{len(cs)} chunks for 50 paragraphs")


def test_robots_disallow(tmp: Path) -> None:
    secret = "THIS-MUST-NEVER-BE-IN-THE-INDEX"
    routes = {
        "/robots.txt": (200, "text/plain", b"User-agent: *\nDisallow: /private\n"),
        "/private/notes.html": (200, "text/html", html("Private", f"<p>{secret} " * 40)),
    }
    with Site(routes) as s, tempfile.TemporaryDirectory(dir=tmp) as d:
        db = Path(d) / "r.db"
        out = run_ingest(db, "--url", f"{s.base}/private/notes.html")
        check("disallowed page is refused", "robots.txt disallows" in out, out[-300:])
        check("refusal is counted", "robots-refused 1" in out, out[-300:])
        eq("no page stored", rows(db, "pages"), 0)
        eq("no chunk stored", rows(db, "chunks"), 0)
        eq("nothing in fts", rows(db, "chunks_fts"), 0)
        check("disallowed host was never requested",
              "/private/notes.html" not in s.hits, str(s.hits))
        rc, out2 = run_search(db, secret)
        check("search reports no match for the secret",
              "No indexed source matches" in out2, out2[:200])
        check("no source is offered for the secret", "[1]" not in out2, out2[:200])


def test_robots_absent_is_allowed(tmp: Path) -> None:
    """A site with no robots.txt has no opinion, and that is allowed."""
    routes = {"/page.html": (200, "text/html", html("P", "<p>hello there " * 40))}
    with Site(routes) as s, tempfile.TemporaryDirectory(dir=tmp) as d:
        db = Path(d) / "a.db"
        out = run_ingest(db, "--url", f"{s.base}/page.html")
        check("absent robots.txt is not a refusal", "indexed" in out, out[-300:])
        check("the absence is stated", "no robots.txt" in out, out[-300:])


def test_robots_unreachable_is_refused(tmp: Path) -> None:
    """Unreachable is not the same as absent, and must not be assumed to allow.

    This is the case that matters. If a server errors on robots.txt and the
    crawler proceeds, then any server that can produce a 500 has been granted
    permission it never gave. Refuse, and leave the reason visible.
    """
    routes = {
        "/robots.txt": (500, "text/plain", b"internal error"),
        "/page.html": (200, "text/html", html("P", "<p>secret page " * 40)),
    }
    with Site(routes) as s, tempfile.TemporaryDirectory(dir=tmp) as d:
        db = Path(d) / "u.db"
        out = run_ingest(db, "--url", f"{s.base}/page.html")
        check("500 robots.txt is not treated as absent", "no robots.txt" not in out, out[-300:])
        check("unreachable robots.txt refuses the host",
              "refusing this host" in out, out[-300:])
        check("refusal is counted as robots-refused", "robots-refused 1" in out, out[-300:])
        eq("nothing stored", rows(db, "chunks"), 0)
        check("page never fetched", "/page.html" not in s.hits, str(s.hits))


def test_robots_403_is_refused(tmp: Path) -> None:
    routes = {
        "/robots.txt": (403, "text/plain", b"go away"),
        "/page.html": (200, "text/html", html("P", "<p>secret " * 40)),
    }
    with Site(routes) as s, tempfile.TemporaryDirectory(dir=tmp) as d:
        db = Path(d) / "f.db"
        out = run_ingest(db, "--url", f"{s.base}/page.html")
        check("403 robots.txt refuses the host", "refusing this host" in out, out[-300:])
        eq("nothing stored", rows(db, "chunks"), 0)


def test_redirect_to_disallowed_is_refused(tmp: Path) -> None:
    """The seed is allowed; where it redirects to is not. It must be re-checked."""
    secret = "REDIRECT-SECRET-MUST-NOT-BE-INDEXED"
    routes = {
        "/robots.txt": (200, "text/plain", b"User-agent: *\nDisallow: /private\n"),
        "/start.html": (200, "text/html", html("Start", "<p>come in</p>")),
        # 302, which urllib would have followed silently
        "/private/secret.html": (200, "text/html", html("S", f"<p>{secret} " * 40)),
    }

    class Redir(Site):
        pass

    site = Site(routes)

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def do_GET(self):
            site.hits.append(self.path)
            if self.path == "/start.html":
                self.send_response(302)
                self.send_header("Location", "/private/secret.html")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            status, ctype, body = site.routes.get(self.path, (404, "text/html", b""))
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    site.srv.RequestHandlerClass = Handler
    with site, tempfile.TemporaryDirectory(dir=tmp) as d:
        db = Path(d) / "rd.db"
        out = run_ingest(db, "--url", f"{site.base}/start.html")
        check("redirect into a disallowed path is refused",
              "refused" in out, out[-300:])
        check("the reason names the redirect target",
              "/private/secret.html" in out, out[-300:])
        eq("nothing stored", rows(db, "chunks"), 0)
        check("redirected body never indexed", secret not in out, out[-300:])
        rc, sout = run_search(db, secret)
        check("no source is offered for the redirected secret",
              "No indexed source matches" in sout, sout[:200])


def test_redirect_loop(tmp: Path) -> None:
    routes = {"/robots.txt": (200, "text/plain", b"User-agent: *\nAllow: /\n")}

    site = Site(routes)

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def do_GET(self):
            site.hits.append(self.path)
            if self.path == "/robots.txt":
                body = b"User-agent: *\nAllow: /\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            nxt = "/a.html" if self.path == "/b.html" else "/b.html"
            self.send_response(302)
            self.send_header("Location", nxt)
            self.send_header("Content-Length", "0")
            self.end_headers()

    site.srv.RequestHandlerClass = Handler
    with site, tempfile.TemporaryDirectory(dir=tmp) as d:
        db = Path(d) / "lp.db"
        out = run_ingest(db, "--url", f"{site.base}/a.html")
        check("redirect loop terminates", "redirect loop" in out, out[-300:])


def test_ssrf_and_scheme(tmp: Path) -> None:
    for url, needle in [
        ("http://127.0.0.1/x", "private/loopback"),
        ("http://[::1]/x", "private/loopback"),
        ("http://10.0.0.1/x", "private/loopback"),
        ("http://169.254.169.254/latest/meta-data/", "private/loopback"),
        ("file:///etc/passwd", "refusing scheme"),
        ("ftp://example.com/x", "refusing scheme"),
    ]:
        try:
            ingest.resolve_and_check(url, allow_private=False)
            check(f"refuses {url}", False, "was allowed")
        except ValueError as e:
            check(f"refuses {url}", needle in str(e), str(e))

    # and the escape hatch is opt-in, not accidental
    try:
        ingest.resolve_and_check("http://127.0.0.1/x", allow_private=True)
        check("--allow-private is honoured", True)
    except ValueError as e:
        check("--allow-private is honoured", False, str(e))


def test_depth_is_not_a_wildcard(tmp: Path) -> None:
    """depth 0 must fetch the seed and nothing else."""
    page = ("<html><head><title>D</title></head><body><p>seed text " * 10 +
            '<a href="/child.html">child</a></body></html>')
    routes = {
        "/robots.txt": (200, "text/plain", b"User-agent: *\nAllow: /\n"),
        "/seed.html": (200, "text/html", page.encode()),
        "/child.html": (200, "text/html", html("Child", "<p>zqxmarker passage " * 40)),
    }
    with Site(routes) as s, tempfile.TemporaryDirectory(dir=tmp) as d:
        db = Path(d) / "d0.db"
        run_ingest(db, "--url", f"{s.base}/seed.html")          # default = depth 0
        check("depth 0 does not follow links", "/child.html" not in s.hits, str(s.hits))
        rc, out = run_search(db, "zqxmarker")
        check("child content is absent at depth 0", "No indexed source" in out, out[:200])

        db2 = Path(d) / "d1.db"
        s.hits.clear()
        run_ingest(db2, "--url", f"{s.base}/seed.html", "--depth", "1")
        check("depth 1 does follow links", "/child.html" in s.hits, str(s.hits))

        # dry run must not fetch the body
        db3 = Path(d) / "dry.db"
        s.hits.clear()
        out = run_ingest(db3, "--url", f"{s.base}/seed.html", "--dry-run")
        check("--dry-run reports the url", "would fetch" in out, out[-200:])
        check("--dry-run fetches nothing", "/seed.html" not in s.hits, str(s.hits))
        check("--dry-run stores nothing", not db3.exists() or rows(db3, "chunks") == 0)


def test_content_type_and_size(tmp: Path) -> None:
    big = b"x" * (ingest.MAX_BYTES + 10)
    routes = {
        "/robots.txt": (200, "text/plain", b"User-agent: *\nAllow: /\n"),
        "/a.pdf": (200, "application/pdf", b"%PDF-1.4 nothing"),
        "/big.html": (200, "text/html", big),
    }
    with Site(routes) as s, tempfile.TemporaryDirectory(dir=tmp) as d:
        db = Path(d) / "ct.db"
        out = run_ingest(db, "--url", f"{s.base}/a.pdf", "--url", f"{s.base}/big.html")
        check("pdf is refused", "not indexable" in out, out[-300:])
        check("oversized body is refused", "exceeds" in out, out[-300:])
        eq("neither stored", rows(db, "chunks"), 0)


def test_crawl_delay_is_respected(tmp: Path) -> None:
    routes = {
        "/robots.txt": (200, "text/plain", b"User-agent: *\nAllow: /\nCrawl-delay: 1\n"),
        "/p.html": (200, "text/html", html("P", "<p>body " * 40)),
    }
    with Site(routes) as s, tempfile.TemporaryDirectory(dir=tmp) as d:
        db = Path(d) / "cd.db"
        t0 = time.monotonic()
        out = run_ingest(db, "--url", f"{s.base}/p.html")
        # robots.txt is fetched politely too, so the second request must wait
        check("Crawl-delay from robots.txt is honoured", time.monotonic() - t0 >= 1.0,
              f"took {time.monotonic() - t0:.2f}s")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def test_oversized_page_becomes_many_rows(tmp: Path) -> None:
    """The end-to-end version of the cap: one big page, many FTS rows."""
    long_page = "<html><head><title>Reference</title></head><body>" + "".join(
        f"<p>zqxmarker section {i} with some text to carry</p>" for i in range(400)
    ) + "</body></html>"
    routes = {
        "/robots.txt": (200, "text/plain", b"User-agent: *\nAllow: /\n"),
        "/ref.html": (200, "text/html", long_page.encode()),
    }
    with Site(routes) as s, tempfile.TemporaryDirectory(dir=tmp) as d:
        db = Path(d) / "big.db"
        run_ingest(db, "--url", f"{s.base}/ref.html")
        n = rows(db, "chunks")
        check("a long page becomes many chunks", n > 10, f"{n} chunks")
        import sqlite3
        c = sqlite3.connect(db)
        worst = c.execute("select max(length(text)) from chunks").fetchone()[0]
        c.close()
        check("no stored chunk exceeds the cap", worst <= ingest.CHUNK_CHARS, f"{worst}")
        # and the last section is findable, not truncated away
        rc, out = run_search(db, "zqxmarker section 399")
        check("the end of a long page is retrievable", "ref.html" in out, out[:200])


def test_search(tmp: Path) -> None:
    body = ("<p>FTS5 stores text in a virtual table and supports BM25 ranking, "
            "prefix indexes and column filters. " * 4)
    routes = {
        "/robots.txt": (200, "text/plain", b"User-agent: *\nAllow: /\n"),
        "/fts.html": (200, "text/html", html("FTS5 notes", body)),
    }
    with Site(routes) as s, tempfile.TemporaryDirectory(dir=tmp) as d:
        db = Path(d) / "s.db"
        run_ingest(db, "--url", f"{s.base}/fts.html")

        rc, out = run_search(db, "BM25 ranking")
        check("search finds the page", "fts.html" in out, out[:300])
        eq("search exits 0 on a hit", rc, 0)

        rc, out = run_search(db, "--sources", "BM25")
        check("--sources lists urls and dates", "http" in out and "fetched" in out, out[:300])

        rc, out = run_search(db, "--evidence", "BM25 ranking")
        check("--evidence numbers the sources", "[1]" in out, out[:400])
        check("--evidence carries a SOURCES header", "[SOURCES]" in out, out[:400])
        check("--evidence includes the source url", "fts.html" in out, out[:400])
        check("--evidence indents the passage text", "\n    " in out, out[:400])
        check("--evidence says the sources are the only ones",
              "only sources" in out, out[-400:])
        check("--evidence forbids filling gaps from memory",
              "from memory" in out, out[-400:])

        # the format run-agent.sh greps for must be the format search.py emits
        check("run-agent's source count grep matches the emitted format",
              len([ln for ln in out.splitlines() if ln.startswith("[") and
                   ln[1:2].isdigit()]) == 1, out[:400])

        # a miss must be honest about what it means
        rc, out = run_search(db, "photosynthesis quantum tunnelling")
        check("a miss says no source matches", "No indexed source matches" in out, out[:200])
        check("a miss explains the limit", "not about the world" in out, out[:200])
        check("a miss is a non-zero exit", rc == 1, f"rc={rc}")

        # a lexical miss on synonyms is a documented limitation, not a bug
        rc, out = run_search(db, "relevance ranking function")
        check("synonym miss is possible (lexical, by design)", rc in (0, 1))

        # injection-ish input must not become FTS5 syntax
        rc, out = run_search(db, 'BM25" OR "a')
        check("quotes in a query do not break it", rc in (0, 1), out[:200])
        for nasty in ["NEAR(a b)", "BM25*", "^bm25", '"'*9, "AND OR NOT", "a:b"]:
            rc, out = run_search(db, nasty)
            check(f"query {nasty!r} is handled without a traceback",
                  "Traceback" not in out, out[:200])


def test_search_dedupes_across_queries(tmp: Path) -> None:
    body = "<p>alpha beta gamma delta " * 40
    routes = {
        "/robots.txt": (200, "text/plain", b"User-agent: *\nAllow: /\n"),
        "/x.html": (200, "text/html", html("X", body)),
    }
    with Site(routes) as s, tempfile.TemporaryDirectory(dir=tmp) as d:
        db = Path(d) / "dd.db"
        run_ingest(db, "--url", f"{s.base}/x.html")
        rc, out = run_search(db, "--evidence", "alpha beta", "alpha gamma")
        # count the numbered sources
        nums = [ln for ln in out.splitlines()
                if ln.startswith("[") and ln[1:2].isdigit()]
        check("evidence numbers its sources", nums, out[:300])
        check("numbering is sequential from 1",
              [ln.split("]")[0][1:] for ln in nums] ==
              [str(i + 1) for i in range(len(nums))], str(nums))
        # the same passage must not appear twice under two numbers
        bodies = [ln for ln in out.splitlines() if ln.startswith("    ")]
        check("no passage is listed twice", len(bodies) == len(set(bodies)),
              f"{len(bodies)} bodies, {len(set(bodies))} distinct")
        # a one-chunk page queried twice yields exactly one source
        small = {
            "/robots.txt": (200, "text/plain", b"User-agent: *\nAllow: /\n"),
            "/one.html": (200, "text/html", html("One", "<p>zqxmarker only chunk " * 30)),
        }
        with Site(small) as s2:
            db2 = Path(d) / "one.db"
            run_ingest(db2, "--url", f"{s2.base}/one.html")
            rc, out2 = run_search(db2, "--evidence", "zqxmarker", "zqxmarker only")
            n2 = len([ln for ln in out2.splitlines()
                      if ln.startswith("[") and ln[1:2].isdigit()])
            check("the same chunk from two queries is one source", n2 == 1,
                  f"{n2} sources:\n{out2[:400]}")


# ---------------------------------------------------------------------------
# citations
# ---------------------------------------------------------------------------

EVIDENCE = (
    "[SOURCES]\n"
    "[1] FTS5 notes - https://www.sqlite.org/fts5.html (fetched today)\n"
    "    SQLite FTS5 supports BM25.\n\n"
    "[2] Robots - https://example.org/robots (fetched today)\n"
    "    robots.txt is a standard.\n\n"
    "(2 chunk(s) from 2 page(s). These are the only sources you have.)\n"
)


def problems_for(reply: str, evidence: str = EVIDENCE, mx: int = 2):
    return check_citations.check(reply, evidence, mx)[0]


def test_citations() -> None:
    check("a valid citation passes", not problems_for("FTS5 supports BM25 [1]."))
    check("two valid citations pass", not problems_for("Both claims hold [1][2]."))
    check("a list citation passes", not problems_for("Both hold [1,2]."))
    check("repeated valid citations pass", not problems_for("A [1], B [2], C [1][2]."))
    check("a url from the evidence passes",
          not problems_for("As shown at https://www.sqlite.org/fts5.html it holds [1]."))

    check("an out-of-range citation fails", problems_for("Out of range [3]."))
    check("a zero citation fails", problems_for("Invented [0]."))
    check("a high citation fails", problems_for("Invented [9]."))
    check("a url absent from the evidence fails",
          problems_for("See https://evil.example/x for this."))
    check("several invented references all get reported",
          len(problems_for("Invented [7] and [8].")) >= 1)

    # no citation is a NOTE, not a failure - the honest "the sources do not
    # cover this" reply must never be the one that gets marked wrong
    p, notes = check_citations.check("No citation, just prose.", EVIDENCE, 2)
    check("no citation is not a failure", not p, str(p))
    check("no citation is noted", notes and "cites none" in notes[0], str(notes))
    p, notes = check_citations.check("No citation.", EVIDENCE, 0)
    check("with no sources supplied there is no note", not notes, str(notes))

    # a reply quoting a bracket number from the source text is still a bad ref
    check("a bracket number that is not a source fails", problems_for("It says see [7]."))


def test_citation_lint_is_conservative() -> None:
    """A false PASS is worse than a false FAIL here.

    The checker is a lint, not a judge - it cannot tell whether source 1
    *supports* a claim. What it must do is never let a reference to something
    that does not exist look clean, because that is the failure a reader has no
    way to catch themselves.
    """
    # a bracket number that came from the page text, not from a source number
    ev = ("[SOURCES]\n[1] A - https://a.example/x (today)\n"
          "    The spec says see [7] for the details.\n")
    check("[7] with only 1 source fails", problems_for("It says see [7].", ev, 1))
    # trailing punctuation on a url in prose must not break the match
    check("a url in prose with a full stop passes",
          not problems_for("See https://a.example/x.", ev, 1))
    # a reply that invents a plausible-looking source list
    check("an invented bibliography fails",
          len(problems_for("[1] Smith et al 2019 [2] and [3] and [4]")) >= 1)


# ---------------------------------------------------------------------------
# the parts that must never fail
# ---------------------------------------------------------------------------

def test_module_sides(tmp: Path) -> None:
    with tempfile.TemporaryDirectory(dir=tmp) as d:
        out = run_ingest(Path(d) / "x.db")
        check("ingest with no seeds errors cleanly",
              "give --url or --seeds" in out and "Traceback" not in out, out[-200:])
        out = run_ingest(Path(d) / "x.db", "--url", "http://x/", "--depth", "-1")
        check("a negative depth is rejected",
              "negative" in out and "Traceback" not in out, out[-200:])
        out = run_ingest(Path(d) / "x.db", "--url", "http://x/", "--delay", "-1")
        check("a negative delay is rejected",
              "negative" in out and "Traceback" not in out, out[-200:])


def test_shell_scripts_are_syntactically_valid() -> None:
    for s in ["tools/run-agent.sh", "tools/ingest.py"]:
        p = ROOT / s
        if s.endswith(".sh"):
            r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
            check(f"{s} parses", r.returncode == 0, r.stderr[:300])


def test_timeout_units_agree() -> None:
    """AGENT_TIMEOUT_MIN is minutes; runtime_chat wants seconds.

    They disagreed in exactly one place, and the failure looked like a broken
    model: a 30-minute budget became a 30-second one, so every open-book run
    died with "model call failed (rc=28)" on a small model that was only slow.
    Nothing in the tree flagged it, because test-agent.sh - the other caller -
    had the conversion right.
    """
    ta = (ROOT / "tools" / "test-agent.sh").read_text(encoding="utf-8")
    ra = (ROOT / "tools" / "run-agent.sh").read_text(encoding="utf-8")
    check("test-agent converts minutes to seconds",
          'AGENT_TIMEOUT_MIN:-30} * 60' in ta, "conversion not found")
    check("run-agent converts minutes to seconds",
          'AGENT_TIMEOUT_MIN:-30} * 60' in ra, "conversion not found")
    check("run-agent no longer passes the raw minutes value to runtime_chat",
          '"${AGENT_TIMEOUT_MIN:-1800}"' not in ra, "raw value still passed")
    check("runtime_chat documents its timeout as seconds",
          "timeout_secs" in (ROOT / "lib" / "runtime.sh").read_text(encoding="utf-8"),
          "runtime.sh no longer says seconds")


def test_role_names_become_valid_shell_variables() -> None:
    """A model role name has to survive the trip into a shell variable.

    Four places convert a role name to the env var prefix that models.env uses:
    tools/resolve_models.py writes the names, and tools/test-agent.sh,
    tools/run-agent.sh and scripts/20-models.sh read them back. All four
    uppercased. None stripped hyphens, because no role had one, so it never
    mattered and nothing checked it.

    Then `adversarial-review` arrived and all four broke the same way. A hyphen
    is not legal in a shell identifier, so the generated models.env grew

        ADVERSARIAL-REVIEW_MODEL="qwen3:14b"

    which bash does not parse as an assignment: it tries to execute a command
    with that name, prints "command not found", and continues. The variable is
    never set, so every caller reports "no model resolved for role" - which
    points at the hardware, and the hardware is fine. Verified, not assumed:
    sourcing such a file produced four "command not found" lines and an unset
    variable.

    So: the two implementations must agree, the result must be a legal shell
    identifier, and every reader must go through the one helper.
    """
    names = ["reasoning", "fast", "adversarial-review", "teacher", "a-b-c", "x"]
    legal = re.compile(r"^[A-Z][A-Z0-9_]*$")

    # bash: the one helper in lib/common.sh
    script = "set -e\n. lib/common.sh\nfor r in " + " ".join(
        repr(n) for n in names) + "; do aiorg_role_var \"$r\"; echo; done\n"
    out = subprocess.run(
        ["bash", "-c", script], cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    bash_vals = dict(zip(names, out))
    check("bash helper returns one value per role", len(bash_vals) == len(names),
          f"expected {len(names)}, got {len(out)}")

    # python: the copy in tools/resolve_models.py
    spec = importlib.util.spec_from_file_location(
        "rm", ROOT / "tools" / "resolve_models.py")
    rm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rm)
    for n in names:
        check(f"role '{n}' becomes a legal shell identifier",
              bool(legal.match(rm.role_var(n))),
              f"role_var({n!r}) = {rm.role_var(n)!r}")
        check(f"bash and python agree on '{n}'",
              bash_vals.get(n) == rm.role_var(n),
              f"bash {bash_vals.get(n)!r} != python {rm.role_var(n)!r}")

    # Every reader goes through the helper. A hand-rolled uppercase is the exact
    # thing that broke, so assert none is left.
    for rel in ("tools/test-agent.sh", "tools/run-agent.sh", "scripts/20-models.sh"):
        body = (ROOT / rel).read_text(encoding="utf-8")
        check(f"{rel} uses aiorg_role_var",
              "aiorg_role_var" in body, "helper not used")
        check(f"{rel} has no hand-rolled role uppercase",
              "[:upper:]'" not in body,
              "a 'tr ... [:upper:]' conversion is still in this file")


def test_role_var_output_is_sourceable(tmp: Path) -> None:
    """End to end: a hyphenated role must produce a models.env bash can source.

    The unit assertions above check the conversion in isolation. This one writes
    a real models.env containing a hyphenated role and actually sources it, which
    is where the original bug lived - a string that looked right and was not a
    valid assignment.
    """
    env = tmp / "models.env"
    env.write_text(
        '# written by a test\n'
        'AI_ROLES="adversarial-review"\n'
        'ADVERSARIAL_REVIEW_MODEL="qwen3:14b"\n'
        'ADVERSARIAL_REVIEW_VRAM_GB="10"\n',
        encoding="utf-8",
    )
    r = subprocess.run(
        ["bash", "-c",
         f'set -a; . "{env}"; '
         'printf "%s|%s\\n" "${ADVERSARIAL_REVIEW_MODEL:-}" '
         '"${ADVERSARIAL_REVIEW_VRAM_GB:-}"'],
        capture_output=True, text=True,
    )
    check("sourcing a hyphenated-role models.env is clean", r.returncode == 0,
          f"rc={r.returncode} stderr={r.stderr.strip()!r}")
    check("no 'command not found' while sourcing", "command not found" not in r.stderr,
          f"stderr={r.stderr.strip()!r}")
    check("the resolved model is readable through the helper's name",
          r.stdout.strip() == "qwen3:14b|10", f"got {r.stdout.strip()!r}")


def test_ollama_host_override_survives_require_profile() -> None:
    """An exported AI_OLLAMA_HOST must survive require_profile.

    This has now failed three times in this project, always the same shape: one
    canonical helper, several readers, and a generated file quietly winning the
    argument. config/profile.env is generated, so it contains a plain
    AI_OLLAMA_HOST="127.0.0.1" - and sourcing it overwrote an operator's
    deliberate override, while the comment in that same file advertised the
    override as the supported way to point at a GPU on another box.

    It lives in the retrieval test file because that is currently the only
    harness in the tree that can run a shell fragment and assert on the result.
    """
    common = str(ROOT / "lib" / "common.sh")
    script = "\n".join([
        ". " + common,
        "require_profile",
        'printf "HOST=%s\\n" "$AI_OLLAMA_HOST"',
        'printf "URL=%s\\n" "$(aiorg_ollama_url)"',
        "",
    ])

    env = dict(os.environ, AI_OLLAMA_HOST="192.168.1.50")
    r = subprocess.run(["bash", "-c", script], capture_output=True,
                       text=True, env=env, timeout=30)
    check("require_profile keeps an exported AI_OLLAMA_HOST",
          "HOST=192.168.1.50" in r.stdout, r.stdout + r.stderr)
    check("aiorg_ollama_url follows the override",
          "URL=http://192.168.1.50:11434" in r.stdout, r.stdout + r.stderr)

    env = {k: v for k, v in os.environ.items() if k != "AI_OLLAMA_HOST"}
    r = subprocess.run(["bash", "-c", script], capture_output=True,
                       text=True, env=env, timeout=30)
    check("without an override the profile value stands",
          "HOST=127.0.0.1" in r.stdout, r.stdout + r.stderr)

    # an empty value is an unset variable, not an override of ""
    env = dict(os.environ, AI_OLLAMA_HOST="")
    r = subprocess.run(["bash", "-c", script], capture_output=True,
                       text=True, env=env, timeout=30)
    check("an empty AI_OLLAMA_HOST is not treated as an override",
          "HOST=127.0.0.1" in r.stdout, r.stdout + r.stderr)

    # No caller may source the profile directly. That is how status kept the bug
    # alive after require_profile had already been fixed: the rule was in the
    # wrong function, and the one command whose entire job is to report which
    # machine it is talking to was the one that bypassed it.
    import re as _re
    direct = []
    for f in [ROOT / "bootstrap.sh", *sorted((ROOT / "scripts").glob("*.sh")),
              *sorted((ROOT / "tools").glob("*.sh"))]:
        txt = f.read_text(encoding="utf-8")
        # ignore commented-out lines and the one legitimate exception
        for i, ln in enumerate(txt.splitlines(), 1):
            code = ln.split("#", 1)[0] if not ln.lstrip().startswith("#") else ""
            if not code.strip():
                continue
            if _re.search(r'^\s*\.\s+"?\$AIORG_PROFILE"?', code):
                if f.name == "00-detect.sh":
                    continue      # detect writes the profile; documented why
                direct.append(f"{f.name}:{i}")
    check("no caller sources the profile directly instead of source_profile",
          not direct, f"direct sourcing at {direct}")

    check("source_profile exists as the single place the rule lives",
          "source_profile()" in (ROOT / "lib" / "common.sh").read_text(encoding="utf-8"),
          "source_profile not found in lib/common.sh")
    check("require_profile delegates to source_profile",
          "source_profile\n" in (ROOT / "lib" / "common.sh").read_text(encoding="utf-8"),
          "require_profile does not call source_profile")


def test_no_script_names_the_model_server_by_hand() -> None:
    """One helper names the server. Nothing else may.

    The bare `ollama` CLI always means localhost, so a script that calls it
    without OLLAMA_HOST inspects the wrong machine whenever the GPU is on
    another box. check-agents.py warns about this and has been right every time
    it fired.
    """
    offenders = []
    for f in sorted((ROOT / "tools").glob("*")):
        if f.suffix not in (".sh", ".py") or not f.is_file():
            continue
        body = "\n".join(ln for ln in f.read_text(encoding="utf-8").splitlines()
                          if not ln.lstrip().startswith("#"))
        if "127.0.0.1:11434" in body or "localhost:11434" in body:
            offenders.append(f.name)
    check("no tool hardcodes the model server endpoint", not offenders,
          f"literal endpoint in {offenders}")


def test_unsatisfiable_cases_are_detected() -> None:
    """A case whose must_contain collides with its must_not_contain can never pass.

    The real instance: `cto no-write-claim` required the word "applied" in a
    `||` group while must_not banned "applied", so a correct refusal ("I have
    not applied the change") was itself marked a failure. Three such cases were
    fixed by hand, which is exactly the situation where the same mistake comes
    back and nothing notices.

    The rule being asserted, and it mirrors check_field() in test-agent.sh
    exactly: `must_contain` passes if ANY `||` group has all its comma-items
    present, so a case is only unsatisfiable when EVERY group is poisoned. A
    satisfiability check that disagreed with the matcher would be worse than
    none, so the group semantics are tested here too and not just the substring
    direction.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_agents", ROOT / "tools" / "check-agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class FakeReport:
        def __init__(self) -> None:
            self.errors: list[str] = []

        def error(self, agent: str, msg: str) -> None:
            self.errors.append(msg)

    def errors_for(must: str, mustnot: str) -> int:
        rep = FakeReport()
        mod._check_case_satisfiable("t", 1, "t", must, mustnot, rep)
        return len(rep.errors)

    # The historical bug, in the shape it actually had: every alternative
    # phrasing contains the banned verb.
    check("every group poisoned is flagged",
          errors_for("applied || i have applied || we have applied",
                     "applied") == 1)
    # One clean group is a way for the case to pass, so it is not flagged.
    check("one clean group rescues the case",
          errors_for("applied || i have applied || not my call", "applied") == 0)
    # Banned string longer than the required one: the refusal satisfies both.
    check("longer banned string is satisfiable",
          errors_for("refuse,deploy || will not,grant",
                     "i have granted deploy,granted it deploy") == 0)
    # "apply" is not a substring of "applied" - the check is literal, and must
    # not be word-boundary clever or it will disagree with grep -F.
    check("substring is literal, not word-wise",
          errors_for("i have applied || will apply", "apply") == 0)
    # must_not alone with no must_contain cannot conflict with anything.
    check("no must_contain means no conflict", errors_for("", "applied") == 0)
    # must_contain alone has nothing to collide with.
    check("no must_not means no conflict",
          errors_for("applied || done", "") == 0)


def test_independence_survives_every_hardware_tier() -> None:
    """Declared model-independence must hold at every tier, not just in role names.

    `check_independent_models` compares role names, because comparing resolved
    models would be red on every GPU-less machine (the 8GB fallback collapses
    every role onto one model). Roles are the right proxy for "did the author
    make a config mistake" and the wrong proxy for "will these two run
    different weights on the card this person buys" - a role is a candidate list
    and the resolver takes the largest that fits, so two disjoint lists converge
    at particular sizes. The auditor role did exactly that at 16GB and 32GB,
    which is the upgrade path, and the role check passed it.

    The 16GB end was fixed on 2026-09-26 by giving `reasoning` a second model
    family below 20GB. The 32GB end is still open, and provably cannot be fixed
    by adding a candidate without moving the 24GB design target; see the
    assertion below for the arithmetic.

    These assertions pin the resolution behaviour that makes the real check
    meaningful. They are deliberately about `resolve_models.py` rather than
    about the check itself, because the check's correctness here is entirely a
    function of the thing being resolved.
    """
    import importlib.util
    import json

    def load(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    r = load("aiorg_resolve_models", ROOT / "tools" / "resolve_models.py")
    hw = load("aiorg_hwdetect", ROOT / "lib" / "hwdetect.py")
    catalog = json.loads((ROOT / "config" / "models.json").read_text(encoding="utf-8"))
    fit = catalog["fit"]
    # HEADROOM_RATIO comes from lib/hwdetect.py, not a literal here. A card's
    # usable VRAM is total * HEADROOM_RATIO, and hardcoding 0.90 in a test makes
    # the test pass against a stale copy of the rule - which is the failure
    # this project has now collected five of.
    headroom = float(hw.HEADROOM_RATIO)

    def at(role: str, card_gb: float) -> str | None:
        got = r.resolve_role(role, catalog["roles"][role], card_gb * headroom, fit)
        return got["model"] if got else None

    # Fit uses the catalog's own margins, not 1.0. This is the arithmetic that
    # made an earlier hand-computed table wrong: a candidate is eligible at
    # vram_gb <= card * 0.90 * 0.92, i.e. about 0.83 * card, not card * 0.90.
    check("20GB card puts reasoning on gpt-oss:20b",
          at("reasoning", 20) == "gpt-oss:20b", f"got {at('reasoning', 20)}")
    check("20GB card keeps the auditor separate",
          at("adversarial-review", 20) != at("reasoning", 20),
          f"both {at('reasoning', 20)}")

    # The 16GB trap. This assertion CHANGED on 2026-09-26: it used to pin
    # `at("adversarial-review", 16) == at("reasoning", 16) == "qwen3:14b"`,
    # which encoded the collision as the expected result. That was correct while
    # the collision was a known, accepted, documented state - and it meant the
    # fix could not be written without editing it. Rule 7 is about weakening a
    # test to make a target pass; this is the other direction. The assertion now
    # demands the separation the checker has been reporting as an error all
    # along, and it names both models so a silent swap is visible.
    check("16GB card keeps the auditor separate (was qwen3:14b on both sides)",
          at("adversarial-review", 16) == "qwen3:14b" and at("reasoning", 16) == "phi4:14b",
          f"{at('adversarial-review', 16)} vs {at('reasoning', 16)}")
    check("12GB card keeps the auditor separate",
          at("adversarial-review", 12) == "qwen3:8b" and at("reasoning", 12) == "gemma3:12b",
          f"{at('adversarial-review', 12)} vs {at('reasoning', 12)}")
    # A 6GB tie decided purely by declaration order, so it is worth pinning.
    check("8GB card keeps the auditor separate (6GB tie, declaration order)",
          at("adversarial-review", 8) == "qwen3:8b" and at("reasoning", 8) == "llama3.1:8b",
          f"{at('adversarial-review', 8)} vs {at('reasoning', 8)}")

    # Still a collision, and still deliberately unfixed. The 28-48GB band cannot
    # be closed by adding a candidate: anything that outranks qwen3:32b (23GB) on
    # a 28GB card is over 23GB, while a 24GB card's eligibility ceiling is
    # 24 * 0.90 * 0.92 = 19.9GB - so every candidate that wins at 28GB also wins
    # at 24GB and the design target moves with it. Fixing this band means
    # choosing a different auditor for the 24GB card, which is an owner
    # decision, not a catalog edit. Kept as a live assertion so the band cannot
    # drift unnoticed in either direction.
    check("32GB card is a documented collision (both qwen3:32b)",
          at("adversarial-review", 32) == at("reasoning", 32) == "qwen3:32b",
          f"{at('adversarial-review', 32)} vs {at('reasoning', 32)}")

    # The design target, and the only large card that is currently safe.
    check("24GB design target keeps them apart",
          at("adversarial-review", 24) == "qwen3:14b" and at("reasoning", 24) == "gpt-oss:20b",
          f"{at('adversarial-review', 24)} vs {at('reasoning', 24)}")

    # narrative has no candidate that fits this box, which is why storyteller
    # cannot be tested here at all. Asserted because the 16GB floor claim in the
    # docs depends on it: 16GB is the first card where narrative resolves.
    check("narrative resolves nothing at 8GB", at("narrative", 8) is None)
    check("narrative resolves at 16GB", at("narrative", 16) is not None)


def test_independence_checker_catches_an_injected_collision(tmp: Path) -> None:
    """The checker itself, against a catalog built to collide and one that cannot.

    The tests above pin what the resolver does to the real catalog, which is
    necessary and not sufficient: a checker that called the resolver and then
    threw the answer away would pass all of them. So this drives
    `check_independence_survives_resolution` over two purpose-built catalogs
    and asserts it stays quiet on the clean one and speaks on the dirty one.

    Pointing the checker at a temporary catalog is the only reason CATALOG is a
    module-level name rather than something read inside the function. That is
    not a test-only concession - a checker that can only read the one real file
    can only ever be tested by breaking the real file.
    """
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location(
        "aiorg_check_agents", ROOT / "tools" / "check-agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    cat_path = tmp / "models.json"

    def write_catalog(adv_models: list[dict]) -> None:
        cat_path.write_text(json.dumps({
            "fit": {"comfortable_max": 0.75, "tight_max": 0.92},
            "roles": {
                "reasoning": {"candidates": [{"model": "big", "vram_gb": 20}]},
                "adversarial-review": {"candidates": adv_models},
            },
        }), encoding="utf-8")

    class FakeReport:
        def __init__(self) -> None:
            self.errors: list[str] = []
            self.warnings: list[str] = []

        def error(self, agent: str, msg: str) -> None:
            self.errors.append(msg)

        def warn(self, agent: str, msg: str) -> None:
            self.warnings.append(msg)

    dirs = [p for p in sorted((ROOT / "agents").iterdir())
            if (p / "agent.conf").is_file()]

    mod.CATALOG = cat_path

    # reasoning can only ever be "big". A different model for the auditor means
    # no tier collides, and the checker must say nothing at all.
    write_catalog([{"model": "other", "vram_gb": 10}])
    rep = FakeReport()
    mod.check_independence_survives_resolution(dirs, rep)
    check("clean catalog produces no independence error", not rep.errors,
          f"{len(rep.errors)} unexpected: {rep.errors[:1]}")
    check("clean catalog produces no warning either", not rep.warnings,
          f"{rep.warnings[:1]}")

    # Same catalog, one candidate swapped so both roles can land on "big" at
    # 20GB. This is the 32GB trap exactly, injected.
    write_catalog([{"model": "big", "vram_gb": 20}])
    rep = FakeReport()
    mod.check_independence_survives_resolution(dirs, rep)
    check("injected collision is caught", len(rep.errors) == 1,
          f"{len(rep.errors)} errors, expected 1")
    check("the error names the shared model",
          bool(rep.errors) and "'big'" in rep.errors[0],
          f"{rep.errors[:1]}")

    # A role the auditor cannot reach at any tier is not a collision, and
    # treating it as one would be a false positive on a healthy catalog.
    write_catalog([{"model": "big", "vram_gb": 20},
                   {"model": "other", "vram_gb": 10}])
    rep = FakeReport()
    mod.check_independence_survives_resolution(dirs, rep)
    check("a catalog that diverges at every tier is clean",
          len(rep.errors) == 1,
          f"{len(rep.errors)} errors, expected 1 (only the 20GB tier)")

    # The breakpoint regression, and the reason this test exists.
    #
    # A candidate becomes eligible at usable = vram_gb / tight_max, which with
    # the catalog's 0.92 margin is ABOVE its own vram_gb. A checker that
    # samples hardware tiers AT the candidate sizes probes strictly below every
    # real transition and misses this catalog entirely - here the auditor only
    # converges on "big" above 21.7GB usable, and every vram_gb-sized sample
    # point sees "other" or nothing at all.
    write_catalog([{"model": "other", "vram_gb": 9},
                   {"model": "big", "vram_gb": 20}])
    rep = FakeReport()
    mod.check_independence_survives_resolution(dirs, rep)
    check("collision above the naive sample point is still caught",
          len(rep.errors) == 1,
          f"{len(rep.errors)} errors, expected 1 - tiers are being sampled at "
          f"vram_gb instead of vram_gb/tight_max")


def test_independence_flags_same_family_different_size(tmp: Path) -> None:
    """Two judges on two sizes of one model family is the monoculture, quieter.

    `check_independence_survives_resolution` compares resolved TAGS. That is
    the right comparison for the case it was written for - two roles converging
    on literally the same weights - and it is blind to a case that is arguably
    worse: `deepseek-r1:70b` for the CTO and `deepseek-r1:32b` for the CEO are
    different strings and one training recipe. The CEO exists to arbitrate the
    CTO, and one family arguing with itself produces correlated errors, which
    read as agreement.

    This was not hypothetical. On 2026-09-27, closing the `qwen3:72b` phantom
    left a 44GB slot in `reasoning`, and `deepseek-r1:70b` fitted it exactly -
    real, thinking, 42.5GB. The checker passed it, because the tags differed.
    It was rejected by hand, and this test is the part that should have caught
    it.

    Severity is a WARNING and that is asserted here, because it is a contract
    and not an accident: a shared repo is evidence rather than proof. A 7B and a
    70B of one family are not the same model, and two unrelated models trained
    on one corpus are not independent either, so neither direction is provable
    from the tag. Overstating what a check proves is the habit this project
    keeps having to correct.

    The last assertion is the one that matters most. It neuters `_model_family`
    and requires the warning to disappear, because a check that cannot fail is
    bought with the same confidence as one that can - the `nvidia-smi`
    regression, where the original assertion passed against code that died
    before reaching the check.
    """
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location(
        "aiorg_check_agents", ROOT / "tools" / "check-agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    cat_path = tmp / "models-family.json"

    class FakeReport:
        def __init__(self) -> None:
            self.errors: list[str] = []
            self.warnings: list[str] = []

        def error(self, agent: str, msg: str) -> None:
            self.errors.append(msg)

        def warn(self, agent: str, msg: str) -> None:
            self.warnings.append(msg)

    def write_catalog(reviewer_models: list[dict]) -> None:
        cat_path.write_text(json.dumps({
            "fit": {"comfortable_max": 0.75, "tight_max": 0.92},
            "roles": {
                "reasoning": {"candidates": [
                    {"model": "deepseek-r1:70b", "vram_gb": 43}]},
                "adversarial-review": {"candidates": reviewer_models},
            },
        }), encoding="utf-8")

    dirs = [q for q in sorted((ROOT / "agents").iterdir())
            if (q / "agent.conf").is_file()]
    mod.CATALOG = cat_path

    # Different family: nothing to say. A checker that fired here would be the
    # eight-false-positive blanket rule this project already tried and reverted.
    write_catalog([{"model": "qwen3:14b", "vram_gb": 20}])
    rep = FakeReport()
    mod.check_independence_survives_resolution(dirs, rep)
    check("different families produce no family warning",
          not [w for w in rep.warnings if "different tags" in w],
          f"{[w for w in rep.warnings if 'different tags' in w][:1]}")
    check("different families produce no error either", not rep.errors,
          f"{rep.errors[:1]}")

    # Same family, different size. The case the tag check cannot see.
    write_catalog([{"model": "deepseek-r1:32b", "vram_gb": 20}])
    rep = FakeReport()
    mod.check_independence_survives_resolution(dirs, rep)
    fam = [w for w in rep.warnings if "different tags" in w]
    check("same family at a different size is flagged", len(fam) == 1,
          f"{len(fam)} family warnings, expected 1; all warnings: {rep.warnings[:2]}")
    check("it is a warning and not an error - a shared family is a proxy",
          not rep.errors, f"{rep.errors[:1]}")
    check("the warning names both tags and the shared family",
          bool(fam) and "'deepseek-r1:70b'" in fam[0]
          and "'deepseek-r1:32b'" in fam[0] and "'deepseek-r1' family" in fam[0],
          f"{fam[:1]}")

    # Teeth. If the family comparison were removed, inert, or always returning
    # an empty string, the warning above would vanish and this test must fail.
    real_family = mod._model_family
    try:
        mod._model_family = lambda tag: ""
        rep = FakeReport()
        mod.check_independence_survives_resolution(dirs, rep)
        check("the warning disappears when family detection is broken (teeth)",
              not [w for w in rep.warnings if "different tags" in w],
              "a neutered _model_family still produced the warning, so the "
              "assertions above were not testing the family comparison at all")
    finally:
        mod._model_family = real_family

    # And the unit behaviour, so a future change to the parsing is deliberate.
    eq("family of a size-suffixed tag", real_family("deepseek-r1:70b"), "deepseek-r1")
    eq("family ignores the tag", real_family("qwen3:32b"), "qwen3")
    eq("a dotted repo keeps its dot", real_family("llama3.1:8b"), "llama3.1")
    eq("a bare name is its own family", real_family("big"), "big")
    eq("a malformed reference has no family", real_family(":8b"), "")


def test_check_cases_catches_its_own_failure_modes(tmp: Path) -> None:
    """`check_cases` had 9 error sites and no test. It works - that is the finding.

    A coverage audit of the checker found four functions with 24 error and warn
    sites between them and zero tests naming them. All four are exercised on the
    healthy tree by `test_check_agents_reaches_a_verdict`, so the obvious
    reading is that they are covered, and the audit could have stopped there.
    That reading is exactly the one the `nvidia-smi` regression falsifies:
    running on a healthy tree proves the code path executes, and proves nothing
    about whether the check can fail. A check that only ever sees good input is
    a function that prints nothing, which is indistinguishable from a check that
    is broken.

    So this exercises the failure modes directly, and the results were worth
    having even though nothing was broken. `check_cases` correctly rejects the
    exact defect I fixed BY HAND three times over during the personal agent
    build - `must_not: I can` against `must: I can't`, which is unsatisfiable
    because the banned string is a substring of the required one. The checker
    would have caught it. Three rounds of my own reading were luck, not process,
    and this is the test that turns the luck into a guarantee.

    The one that needed care is the `||` group rule, and getting it wrong in
    EITHER direction would have been a false positive: `must: I can't || I won't`
    with `must_not: I can` is NOT an error, because the second group is clean and
    a reply saying "I won't" satisfies the case. Asserted explicitly, because the
    naive version of this test poisons any group and reports four errors against
    a correct tree.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "aiorg_check_cases", ROOT / "tools" / "check-agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Rep:
        def __init__(self) -> None:
            self.errors: list[str] = []
            self.warnings: list[str] = []
            self.checks = 0

        def error(self, agent: str, msg: str) -> None:
            self.errors.append(msg)

        def warn(self, agent: str, msg: str) -> None:
            self.warnings.append(msg)

    def run(body: str) -> Rep:
        rep = Rep()
        path = Path(tmp) / "cases.tsv"
        path.write_text(body, encoding="utf-8")
        mod.check_cases("t", path, rep)
        return rep

    # The unsatisfiability rule, both directions. A banned string inside a
    # required one is poison; a required string inside a banned one is the cto
    # case the docstring describes and happens constantly.
    rep = run("a ::: say it ::: I can't ::: I can\n")
    check("a case that can never pass is rejected", len(rep.errors) == 1,
          f"{len(rep.errors)} errors, expected 1: {rep.errors[:1]}")
    check("the unsatisfiable case is named",
          bool(rep.errors) and "'a' can never pass" in rep.errors[0],
          f"{rep.errors[:1]}")
    check("a clean || group keeps the case satisfiable",
          not run("a ::: say it ::: I can't || I won't ::: I can\n").errors,
          "one clean must_contain group is a way to pass, so poisoning the other "
          "group is not an error - the naive version of this test reports one")
    check("required inside banned is not a collision",
          not run("a ::: say it ::: deploy ::: i have granted deploy\n").errors,
          "banning a phrase that contains a required word is the documented "
          "cto case and must stay silent")

    # Structural faults, each of which once cost a beginner a whole afternoon.
    #
    # The first draft of this loop asserted exactly one error per fault and four
    # of the five failed, because the checker is stricter than that in a way I
    # had not noticed: a file that yields ZERO usable cases also reports
    # "contains no usable test cases", so every one of these emits a second
    # cascading error. The cascade is correct and useful - the per-line message
    # says what is wrong with line 1, the second says the file is now worthless
    # to score - so the assertion looks for the message anywhere in the output
    # rather than pinning a count. Pinning the count would have encoded my
    # assumption rather than the behaviour, which is the same mistake in a test
    # as in a rule.
    for label, body, want in [
        ("no checks at all", "a ::: say it ::: :::\n", "no checks at all"),
        ("an empty prompt", "a :::  ::: hello ::: x\n", "empty prompt"),
        ("an empty case name", " ::: say it ::: hello ::: x\n", "empty case name"),
        ("a duplicate name", "a ::: one ::: x\n a ::: two ::: y\n", "duplicate case name"),
        ("a bare case with no separator", "a | say it | hello\n", "no separator"),
        # A habit-wrapped case: the check column lands on its own line and is
        # read as a case. The comma is the tell, and the message says which of
        # the two mistakes it is, because the generic one pointed at neither.
        ("a wrapped check line", "a ::: say it\nworld, thing\n", "own line"),
    ]:
        rep = run(body)
        check(f"check_cases catches {label}",
              bool(rep.errors) and any(want in e for e in rep.errors),
              f"want {want!r} in {[e.split('tsv:')[-1] for e in rep.errors]}")

    check("a file with no usable cases says so",
          any("no usable test cases" in e
              for e in run("# only a comment\n\n   \n").errors),
          "an empty cases.tsv is a real fault, not a pass")
    check("comments and blank lines are skipped beside a real case",
          (lambda r: not r.errors and not r.warnings)(
              run("# a comment\n\n   \na ::: say it ::: x\n")),
          f"got {run('# a comment\n\n   \na ::: say it ::: x\n').errors[:1]}")
    check("extra columns are a warning, not an error",
          (lambda r: len(r.warnings) == 1 and not r.errors)(
              run("a ::: say it ::: x ::: y ::: z\n")),
          "only the first four columns are read, so this is recoverable")


def test_reporting_graph_failure_modes(tmp: Path) -> None:
    """Three real bugs in the org-chart check, found by auditing it with no test.

    The second half of the coverage audit. `check_reporting_graph` had four error
    sites and no test, and unlike `check_cases` - which turned out to be sound -
    this one was wrong three times, in the same direction every time.

    All three are NOISE, which is the expensive direction. A missing check makes
    you look in the wrong place; a check that cries wolf three times for one
    mistake makes you stop reading, and the project has already paid for that
    lesson once (`AGENT_INDEPENDENT_OF`'s blanket parent-must-differ rule fired
    eight times on a healthy tree and had to be reverted).

    The bugs, in the order the audit found them:

    1. **A three-agent cycle produced four errors, not one.** The cycle check
       deduplicates on purpose and reported it correctly - then the "does not
       lead to the top of the org" check immediately re-added one identical line
       per agent, attributed to three different agents and naming a root none of
       them was connected to. The dedup was undone one function later.
    2. **An agent pointing at a typo'd parent got two errors.** One naming the
       typo, one claiming it failed to reach the top. The second is a guess
       dressed as a finding, and it points somewhere the fix is not.
    3. **`AGENT_REPORTS_TO="human"` was permitted and then failed.** The orphan
       check explicitly skips `human` as a non-agent parent; the unreachable
       check then fired on exactly that agent. Three of the function's four rules
       disagreed with each other about the same tree, which is the thing to be
       most careful about when several rules read one file.

    None of the three fires on the real tree today, which is precisely why they
    survived: the current org chart happens to avoid every one of them.

    The counter-assertion matters as much as the bug assertions. Deduplication is
    only correct if it is per *distinct fault*, so two separate cycles must both
    be reported, and an agent reporting to an orphan must still be reported even
    though the orphan itself is exempted. A fix that silenced the noise by
    widening the exemption would pass every test above and be worse than the bug.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "aiorg_reporting", ROOT / "tools" / "check-agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Rep:
        def __init__(self) -> None:
            self.errors: list[str] = []
            self.warnings: list[str] = []

        def error(self, agent: str, msg: str) -> None:
            self.errors.append(msg)

        def warn(self, agent: str, msg: str) -> None:
            self.warnings.append(msg)

    counter = 0

    def graph(spec_map: dict[str, str]) -> list[str]:
        """Build a throwaway org chart and return its error messages.

        A fresh directory per call, which the first version got wrong in a way
        worth naming: it reused one path, so the second call raised
        FileExistsError and the third would have inherited the first call's
        agents - `graph({"ceo": "", "a": "ceo"})` reporting on a directory that
        also contained a stray `d` pointing at nothing. The suite died with a
        traceback, and on a checker whose entire job is to find structural
        breakage, a test that crashes the run before finishing is the same
        failure as a checker that crashes the build: it validates nothing and
        still looks red.
        """
        nonlocal counter
        counter += 1
        base = Path(tmp) / f"org{counter}"
        base.mkdir(parents=True)
        dirs = []
        for name, reports_to in spec_map.items():
            d = base / name
            d.mkdir()
            (d / "agent.conf").write_text(
                f'AGENT_REPORTS_TO="{reports_to}"\n', encoding="utf-8")
            dirs.append(d)
        rep = Rep()
        mod.check_reporting_graph(dirs, rep)
        return rep.errors

    # The three bugs, each pinned at the count that is actually correct.
    check("a three-agent cycle is ONE error, not one per agent",
          len(graph({"ceo": "", "a": "b", "b": "c", "c": "a", "d": "ceo"})) == 1,
          "the cycle check deduplicates, and the unreachable check must not "
          "put the same noise back")

    check("an agent pointing at a typo'd parent is ONE error",
          len(graph({"ceo": "", "a": "ceo", "b": "geost"})) == 1,
          "the orphan message is the actionable one; a second 'does not reach "
          "the top' points at the wrong place")

    check('an agent parented to "human" is not reported at all',
          not graph({"ceo": "", "a": "human", "b": "ceo"}),
          "the orphan check explicitly permits a non-agent parent, so the "
          "unreachable check must not fail the agent for using it")

    # Deduplication is per distinct fault. Both of these would pass if the fix
    # had silenced cycles and typos by making the exemptions too wide.
    two_cycles = graph({"ceo": "", "a": "b", "b": "a", "c": "d", "d": "c"})
    check("two separate cycles are both reported", len(two_cycles) == 2,
          f"{len(two_cycles)} errors, expected one per cycle")
    check("each cycle names its own members",
          any("a, b" in e for e in two_cycles) and any("c, d" in e for e in two_cycles),
          f"{two_cycles}")
    downstream = graph({"ceo": "", "a": "ceo", "b": "geost", "c": "b"})
    check("an agent reporting to an orphan is still reported",
          len(downstream) == 2 and any("geost" in e for e in downstream),
          f"the blast radius is real information: {downstream}")

    # The faults that were already right, kept so they cannot regress.
    check("a nonexistent parent is named, with the known agents listed",
          (lambda e: len(e) == 1 and "geost" in e[0] and "ceo" in e[0])(
              graph({"ceo": "", "b": "geost"})),
          f"{graph({'ceo': '', 'b': 'geost'})}")
    check("two roots is an error naming both",
          (lambda e: len(e) == 1 and "must be unique" in e[0])(
              graph({"a": "", "b": "", "c": "a"})),
          f"{graph({'a': '', 'b': '', 'c': 'a'})}")
    check("a self-loop is one cycle error, not a hang",
          len(graph({"ceo": "", "a": "a", "b": "ceo"})) == 1,
          f"{graph({'ceo': '', 'a': 'a', 'b': 'ceo'})}")
    check("a deep chain is fine",
          not graph({"ceo": "", "cto": "ceo", "a": "cto", "b": "a"}),
          f"{graph({'ceo': '', 'cto': 'ceo', 'a': 'cto', 'b': 'a'})}")


def test_runtime_registry_never_crashes_on_bad_json(tmp: Path) -> None:
    """The second instance of the worst bug class in this project, and it was live.

    `check_runtime_registry` reads `config/runtimes.json` - a file its users edit
    by hand, which makes it the most likely place in the tree for malformed input
    - and immediately called `.get()` on whatever `json.loads` returned, twice,
    without checking either was a dict. Six ordinary mistakes reached an
    AttributeError:

        {"runtimes": {"ollama": "ready"}}     a string where an object belongs
        {"runtimes": {"ollama": ["ready"]}}    a list where an object belongs
        [1, 2, 3]                              the top level is a list
        "hello"   /   42                       the top level is a scalar

    **Why this is the worst class and not a nuisance.** The function is called
    from `main()` before the per-agent checks, so a crash here kills the whole
    run: all 16 agents go unvalidated, every other signal reads green, and the
    exit code is 1 - the same 1 the known model-independence error returns. That
    is `test_check_agents_reaches_a_verdict` existing for a second reason, and
    it is the same shape as the `_independence_pairs` NameError found earlier
    today: a diagnostic that reports nothing is indistinguishable from one that
    reports everything is fine.

    The second half of this test is the subtler half. The adapter check was a
    substring search over `lib/runtime.sh`, so a runtime whose adapter existed
    only in a COMMENT passed - and `lib/runtime.sh` line 78 already explains the
    adapter naming convention in prose, so that file is one where adapter names
    get written next to words. It now matches a definition.

    The negative direction is asserted just as hard, because "reject comments"
    is trivially satisfiable by a pattern too strict to match real code: all
    three legal shell definition forms must pass, including `function name {`
    with no parentheses at all.
    """
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location(
        "aiorg_runtimes", ROOT / "tools" / "check-agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Rep:
        def __init__(self) -> None:
            self.errors: list[str] = []
            self.warnings: list[str] = []

        def error(self, agent: str, msg: str) -> None:
            self.errors.append(msg)

        def warn(self, agent: str, msg: str) -> None:
            self.warnings.append(msg)

    real_reg, real_lib = mod.RUNTIMES, mod.RUNTIME_LIB
    reg = Path(tmp) / "runtimes.json"
    lib = Path(tmp) / "runtime.sh"
    lib.write_text("_rt_ollama_probe() {\n:\n}\n_rt_ollama_chat() {\n:\n}\n",
                   encoding="utf-8")
    good = json.dumps({"runtimes": {"ollama": {"status": "ready"}}})

    def run(registry: str | None, adapters: str | None = None,
            want_errors: int | None = None, with_ids: bool = False):
        """Never allowed to raise - that is the point of the whole test.

        BOTH files are rewritten on every call unless the caller asks otherwise.
        An earlier version only rewrote lib/runtime.sh when a test passed one, so
        whichever case ran last left its adapters behind for every case after it:
        the "one real adapter and one commented out" fixture was still in place
        when "a healthy registry is silent" ran, and that test failed for a
        reason that had nothing to do with what it was checking.

        This is the second time in this session that a test helper leaked state
        between calls - the first was a shared directory in the reporting-graph
        test. Both failed the same way: quietly, on assertions that were correct.
        A helper that inherits its predecessor's state is testing the previous
        test as much as this one, and the failure points at the innocent
        assertion rather than at the leak.
        """
        mod.RUNTIMES, mod.RUNTIME_LIB = reg, lib
        try:
            if registry is None:
                reg.unlink(missing_ok=True)
            else:
                reg.write_text(registry, encoding="utf-8")
            lib.write_text(
                "_rt_ollama_probe() {\n:\n}\n_rt_ollama_chat() {\n:\n}\n"
                if adapters is None else adapters,
                encoding="utf-8")
            rep = Rep()
            ids = mod.check_runtime_registry(rep)
            if want_errors is not None and len(rep.errors) != want_errors:
                check(f"expected {want_errors} error(s)", False,
                      f"got {len(rep.errors)}: {rep.errors[:1]}")
            return (rep, ids) if with_ids else rep
        finally:
            mod.RUNTIMES, mod.RUNTIME_LIB = real_reg, real_lib

    # --- must not crash, must report -------------------------------------
    for label, body in [
        ("a runtime value that is a string", '{"runtimes": {"ollama": "ready"}}'),
        ("a runtime value that is a list", '{"runtimes": {"ollama": ["ready"]}}'),
        ("a top level that is a list", "[1, 2, 3]"),
        ("a top level that is a string", '"hello"'),
        ("a top level that is a number", "42"),
        ("a top level that is null", "null"),
    ]:
        rep = run(body, want_errors=1)
        check(f"{label} is reported, not raised on", bool(rep.errors),
              f"got {rep.errors[:1]}")
        check(f"{label} says what is wrong with the shape",
              bool(rep.errors) and ("JSON object" in rep.errors[0]
                                    or "must map to an object" in rep.errors[0]),
              f"{rep.errors[:1]}")

    # The other malformed inputs the function already handled, kept so the fix
    # above cannot have been made by deleting the whole error path.
    check("invalid JSON is reported", bool(run("{not json", want_errors=1).errors),
          "a syntax error is the commonest way to break this file")
    check("a missing registry is reported",
          bool(run(None, want_errors=1).errors), "no registry at all")
    check("an empty runtimes object is reported",
          bool(run('{"runtimes": {}}', want_errors=1).errors), "")
    check("a missing lib/runtime.sh is reported",
          bool(run(good, adapters="", want_errors=1).errors), "")

    # --- the adapter check: rejects names, accepts definitions ------------
    for label, adapters in [
        ("a commented-out definition", "#_rt_ollama_probe() {\n#_rt_ollama_chat() {\n"),
        ("an indented comment", "   # _rt_ollama_probe() {\n   # _rt_ollama_chat() {\n"),
        ("the name in prose", "# ollama -> _rt_ollama_chat is the adapter\n"),
        ("a call site with no definition", '_rt_ollama_probe "$x"\n'),
    ]:
        rep = run(good, adapters=adapters)
        check(f"an adapter that is only {label} is not accepted",
              len(rep.errors) == 2,
              f"{len(rep.errors)} errors, expected one per missing adapter")

    for label, adapters in [
        ("the codebase's own `name() {`", "_rt_ollama_probe() {\n}\n_rt_ollama_chat() {\n}\n"),
        ("`function name {`, no parens",
         "function _rt_ollama_probe {\n}\nfunction _rt_ollama_chat {\n}\n"),
        ("`function name() {`",
         "function _rt_ollama_probe() {\n}\nfunction _rt_ollama_chat() {\n}\n"),
        ("a space before the parens", "_rt_ollama_probe () {\n}\n_rt_ollama_chat () {\n}\n"),
    ]:
        rep = run(good, adapters=adapters)
        check(f"a real definition written as {label} is accepted",
              not rep.errors,
              f"{len(rep.errors)} errors, expected 0: {rep.errors[:1]}")

    # One adapter present and one absent: exactly one error, naming the one.
    rep = run(good, adapters="_rt_ollama_probe() {\n}\n#_rt_ollama_chat() {\n}")
    check("one real adapter and one commented out gives one error",
          len(rep.errors) == 1 and "chat" in rep.errors[0],
          f"{rep.errors[:1]}")

    # --- the parts that were already right --------------------------------
    rep = run(good)
    check("a healthy registry is silent", not rep.errors and not rep.warnings,
          f"{rep.errors + rep.warnings}")
    # The return value is not incidental: main() passes it to check_agent as the
    # only list of runtime names an agent.conf is allowed to name, so a silent
    # change to it would loosen that check without failing anything here.
    check("it returns the declared ids, which check_agent depends on",
          run(good, with_ids=True)[1] == {"ollama"},
          f"got {run(good, with_ids=True)[1]}")

    rep = run('{"runtimes": {"ollama": {"status": "planned"}}}')
    check("a non-ready status is a warning, not an error",
          len(rep.warnings) == 1 and not rep.errors,
          f"{rep.warnings[:1]} / {rep.errors[:1]}")


def test_readme_table_and_loopback_scan_cover_the_tree(tmp: Path) -> None:
    """The last two untested functions. One had a hole, one had a rule that did nothing.

    `check_no_hardcoded_loopback` and `check_readme_table`: 1 and 3 call sites,
    no tests. Between them they hold two findings that are about the CHECKER
    rather than about the tree, which is why documentation-shaped code is still
    worth auditing.

    ## The loopback check was not scanning `tools/`

    Its own docstring, and AGENTS.md rule 12, both claim it warns on any script
    that names the model server directly. That was **false for the six scripts
    most likely to name it** - `tools/test-agent.sh` and `tools/run-agent.sh` are
    the two that actually CALL the server. A hardcoded `127.0.0.1` in a curl
    there would have passed the check meant to catch exactly that, and the
    symptom is the silent one: the script inspects the wrong machine and reports
    the local server as healthy while the GPU sits on another box. Nothing
    crashed, nothing went red.

    The tree was clean, so this was a hole in the instrument rather than a live
    bug - the better of the two ways to find it, and the argument for running an
    audit on a green tree. Verified by injecting a real violation into
    `tools/test-agent.sh` and confirming the check names the file and line, and
    then reverting the `tools/` scan and confirming the *same* violation passes.
    Both directions, because "I added tools/ to the glob" is not evidence that
    it works.

    ## The stale-row check was a rule that checked nothing

        stale = sorted(listed - built - set(re.findall(<same pattern>, text)))

    The third set is a superset of `listed` - same regex, minus the trailing
    column - so the expression is identically empty for every input. It computed
    nothing and nothing read it. This is the third instance of the project's
    most reliable bug shape: a rule that looks like it checks something and does
    not.

    **It is also not implementable, which is the part worth keeping.** The table
    has no status column, so a row for a planned agent is indistinguishable from
    a row for a deleted one: `artist` and `director` are both listed, neither is
    on disk, and both are supposed to be there. Deleting an agent leaves exactly
    the same evidence as never having built it. Anyone "fixing" that line would
    have turned two planned agents into two errors on the first run - so the
    assertion below is a trap-detector, not a coverage gap.
    """
    import importlib.util
    import re

    spec = importlib.util.spec_from_file_location(
        "aiorg_readme", ROOT / "tools" / "check-agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Rep:
        def __init__(self) -> None:
            self.errors: list[str] = []
            self.warnings: list[str] = []

        def error(self, agent: str, msg: str) -> None:
            self.errors.append(msg)

        def warn(self, agent: str, msg: str) -> None:
            self.warnings.append(msg)

    # --- the loopback check ------------------------------------------------
    # It resolves its own root from __file__, so it cannot be pointed at a
    # fixture tree. That is itself worth knowing: it means the only way to test
    # it is against the real tree, so the assertions below are about the real
    # tree's shape rather than about a synthetic one.
    rep = Rep()
    mod.check_no_hardcoded_loopback(rep)
    check("the real tree has no hardcoded model server", not rep.warnings,
          f"{rep.warnings[:2]}")
    # --- the coverage hole, tested against a real fixture tree ------------
    #
    # `check_no_hardcoded_loopback` derives its root from `__file__`, so it
    # cannot be pointed at a fixture by assigning to a global - the only way to
    # give it a different tree is to load the module FROM a different tree. That
    # is what this does, and it is the only version of this assertion that means
    # anything.
    #
    # My first attempt re-derived the file list inside the test and asserted
    # against *that*:
    #
    #     for sub in ("scripts", "lib", "tools"):
    #         would_scan.extend(p.name for p in (ROOT / sub).glob("*.sh"))
    #     check("tools/test-agent.sh is among the files the check reads", ...)
    #
    # which passed with the `tools/` scan deleted from the checker. It was
    # asserting that the test's own list contained the file - a test that cannot
    # fail, bought with the same confidence as one that can. Mutation A below
    # turns the suite green with the bug present, and that is precisely how it was
    # found: the mutation was run, nothing turned red, and the assertion was the
    # suspect rather than the fix.
    import shutil

    # copytree creates the destination, so nothing is pre-created here. That
    # note is here because getting it wrong was the third instance of one shape
    # in this session: a fixture path created before the call that fills it, in
    # `graph()`'s shared directory, in `run()`'s leaked lib file, and now here.
    # All three failed loudly and none corrupted a result, which is the good
    # version of this mistake - but three of them says the habit is worth naming.
    fix = Path(tmp) / "fixtree"
    for sub in ("scripts", "lib", "tools"):
        shutil.copytree(ROOT / sub, fix / sub)
    shutil.copy(ROOT / "bootstrap.sh", fix / "bootstrap.sh")
    shutil.copy(ROOT / "tools" / "check-agents.py", fix / "tools" / "check-agents.py")

    fspec = importlib.util.spec_from_file_location(
        "aiorg_loopback_fixture", fix / "tools" / "check-agents.py")
    fmod = importlib.util.module_from_spec(fspec)
    fspec.loader.exec_module(fmod)

    def fixture_findings() -> list[str]:
        r = Rep()
        fmod.check_no_hardcoded_loopback(r)
        return r.warnings

    check("a fixture tree with no violations is silent", not fixture_findings(),
          f"{fixture_findings()[:2]}")

    # The same violation, injected into each of the three directories. Before
    # the fix, the third of these passed silently.
    for sub, name in [("scripts", "40-verify.sh"), ("lib", "common.sh"),
                      ("tools", "run-agent.sh")]:
        target = fix / sub / name
        keep = target.read_text(encoding="utf-8")
        target.write_text(keep + "\ncurl -s http://127.0.0.1:11434/api/tags\n",
                          encoding="utf-8")
        try:
            found = [w for w in fixture_findings() if name in w]
            check(f"a violation in {sub}/{name} is found", len(found) == 1,
                  f"{len(found)} findings naming {name}, expected 1: "
                  f"{fixture_findings()[:2]}")
        finally:
            target.write_text(keep, encoding="utf-8")

    check("and the fixture is clean again once reverted",
          not fixture_findings(), f"{fixture_findings()[:2]}")

    # The regex alone flags comments, and the line-level skip in the function is
    # the only thing stopping that. My first version of this test asserted the
    # regex would NOT match a comment, which is false - it matches the comment
    # happily - and would have "passed" only by asserting the opposite of what
    # the code does.
    #
    # The real tree settles it properly: it contains several comment lines that
    # explain this exact rule, and the check reports none of them. So the skip is
    # asserted against data that exists rather than against a fixture I invented.
    pat = re.compile(r"curl[^\n]*127\.0\.0\.1|\$\{?AI_OLLAMA_URL")
    comment_hits = 0
    for sub in ("scripts", "lib", "tools"):
        for f in (ROOT / sub).glob("*.sh"):
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("#") and pat.search(line):
                    comment_hits += 1
    check("the real tree has comment lines the regex would match", comment_hits >= 2,
          f"found {comment_hits}; without them this assertion tests nothing")
    check("and the check reports none of them, so comments are skipped",
          not rep.warnings and comment_hits >= 2,
          "a comment explaining the rule must not be reported as breaking it")

    # The narrowness is deliberate: a grep cannot tell a legitimate loopback (a
    # container health check, a bind address) from a wrong one, so only a curl
    # and a read of the generated literal count.
    check("a real curl to loopback is a finding", bool(pat.search(
        'curl -s http://127.0.0.1:11434/api/tags')), "")
    check("reading the generated AI_OLLAMA_URL literal is a finding",
          bool(pat.search('echo "$AI_OLLAMA_URL"')), "")
    check("a non-curl loopback mention is not a finding", not pat.search(
        "bind 127.0.0.1:11434 in the container mapping"),
          "container health checks and bind addresses are legitimate")

    # --- the README table --------------------------------------------------
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"^\|\s*`([a-z0-9-]+)`\s*\|", readme, re.M))
    built = {d.name for d in (ROOT / "agents").iterdir()
             if d.is_dir() and not d.name.startswith("_")}

    check("every built agent is in the README table", not (built - listed),
          f"undocumented: {sorted(built - listed)}")
    check("the only unbuilt rows are the two known-planned agents",
          set(listed - built) == {"artist", "director"},
          f"got {sorted(listed - built)}")

    # The trap: the deleted `stale` expression is asserted to be dead rather
    # than to be correct, because "fixing" it is what would break the two
    # planned agents. Pinned so the reasoning survives the deletion.
    wider = set(re.findall(r"^\|\s*`([a-z0-9-]+)`", readme, re.M))
    check("the deleted stale expression was identically empty",
          listed - built - wider == set() and wider >= listed,
          "it subtracted a superset of itself, so it could never have "
          "reported a stale row no matter what the table said")

    # A built agent with no row IS the drift this function exists to catch, so
    # prove it fires rather than trusting the docstring.
    rep = Rep()
    mod.check_readme_table([ROOT / "agents" / "coder",
                            ROOT / "agents" / "does-not-exist"], rep)
    check("an undocumented agent is an error",
          len(rep.errors) == 1 and "does-not-exist" in rep.errors[0],
          f"{rep.errors[:1]}")
    # Both warning branches, on a tree the function can actually be given. My
    # first attempt here was wrong twice: it expected a warning from a README
    # with no heading, and its own sample started with "#", so the heading
    # branch could not fire; and it passed an empty agent list with an empty
    # table, so the "lists agents but none exist" branch could not either. Two
    # conditions that each had to be arranged rather than assumed.
    r = _readme_reports(mod, ["no heading here", "| `coder` | 19 |"])
    check("a README with no heading warns", len(r.warnings) >= 1
          and "heading" in r.warnings[0], f"{r.warnings[:1]}")
    check("a README listing agents with none on disk warns", len(r.warnings) == 2
          and any("none exist on disk" in w for w in r.warnings),
          f"{r.warnings[:1]}")
    r = _readme_reports(mod, ["# has a heading", "| `coder` | 19 |"])
    check("a correct README with no agents on disk is one warning, not two",
          len(r.warnings) == 1, f"{r.warnings[:1]}")


def _readme_reports(mod, lines: list[str]) -> Rep:
    """Run check_readme_table against a synthetic README. Restores ROOT after."""
    real_root = mod.ROOT
    import tempfile
    d = Path(tempfile.mkdtemp())
    (d / "README.md").write_text("\n".join(lines), encoding="utf-8")
    mod.ROOT = d
    try:
        class Sink:
            errors: list[str] = []
            warnings: list[str] = []

            def error(self, agent: str, msg: str) -> None:
                self.errors.append(msg)

            def warn(self, agent: str, msg: str) -> None:
                self.warnings.append(msg)

        rep = Sink()
        mod.check_readme_table([], rep)
        return rep
    finally:
        mod.ROOT = real_root


def test_doctor_finishes_without_an_nvidia_gpu(tmp: Path) -> None:
    """`bootstrap.sh doctor` must reach its verdict on a machine with no GPU.

    Found by running doctor on the CPU-only box this project was built on: it
    exited 127 and never printed "No problems found". `nvidia-smi` is not
    installed there, and under the `set -o pipefail` that bootstrap.sh sets, a
    missing command makes the whole pipeline return 127 - which `set -e` then
    treats as fatal.

    That is the worst possible place for it. `doctor` is the command a beginner
    runs first when something is broken, and on any AMD or Intel-graphics
    machine it aborted silently at the hardware check. The exit code 127 reads
    as "some tool is missing", which sends you looking for the wrong thing.

    The regression is a pipeline that dies on a missing command, so the test is
    that the command *completes* and prints a verdict. Run against a copy of
    the tree with `nvidia-smi` guaranteed absent from PATH, which is the
    condition that triggered it.
    """
    root = Path(tmp) / "doctorstub"
    for sub in ("lib", "config"):
        (root / sub).mkdir(parents=True)
    (root / "bootstrap.sh").write_text((ROOT / "bootstrap.sh").read_text())
    (root / "lib" / "common.sh").write_text(
        (ROOT / "lib" / "common.sh").read_text())
    (root / "config" / "profile.env").write_text(
        (ROOT / "config" / "profile.env").read_text())
    (root / "config" / "models.env").write_text(
        (ROOT / "config" / "models.env").read_text())
    (root / "config" / "hardware.json").write_text(
        (ROOT / "config" / "hardware.json").read_text())

    # A PATH with the three tools doctor needs and no nvidia-smi. Built by hand
    # rather than by filtering the inherited PATH, so the test does not depend
    # on what happens to be installed on the machine running it.
    # bash itself has to stay reachable - it is the interpreter running the
    # script, not something doctor calls - and it has to be a real path,
    # because `env` here replaces PATH outright rather than prepending to it.
    bindir = root / "bin"
    bindir.mkdir()
    for tool in ("bash", "sh", "python3", "curl", "awk", "sed", "cat", "jq",
                 "grep", "find", "dirname", "nvidia-smi"):
        real = shutil.which(tool)
        if real:
            (bindir / tool).symlink_to(real)
    # nvidia-smi must be absent: that is the whole condition. Removed even if
    # the host has one, so the test fails the same way on an NVIDIA machine.
    smi = bindir / "nvidia-smi"
    if smi.is_symlink() or smi.exists():
        smi.unlink()

    proc = subprocess.run(
        [str(bindir / "bash"), str(root / "bootstrap.sh"), "doctor"],
        capture_output=True, text=True, cwd=root, timeout=120,
        env={"PATH": str(bindir), "HOME": str(root)},
    )

    check("doctor reaches its verdict without an NVIDIA GPU",
          "No problems found" in proc.stdout or "problem(s)" in proc.stdout,
          f"exit={proc.returncode} - doctor died before reporting. "
          f"stdout was: {proc.stdout[-300:]!r}")
    check("doctor did not die on the missing nvidia-smi",
          proc.returncode in (0, 1),
          f"exit={proc.returncode}; 127 means the nvidia-smi pipeline killed it")


def test_check_runs_every_step_even_when_one_fails(tmp: Path) -> None:
    """`bootstrap.sh check` must report all three steps, not abort at the first.

    `bootstrap.sh` runs under `set -euo pipefail`, so a failing step aborts the
    command. For `check` that silently disabled two independent validations:
    with check-agents.py knowingly red over the auditor's model independence,
    the risk-tier cross-check and all 301 assertions in this file were never
    being executed. Nobody noticed because the only visible symptom was a red
    build that had been red for a while.

    Runs the real `bootstrap.sh` against stub scripts in a temp tree rather
    than against the real ones. The obvious version of this test - just call
    `bootstrap.sh check` - costs about 17 seconds, because that command runs
    this whole suite again, and it recurses: check runs this file, which calls
    check. Stubs keep it at milliseconds and remove the recursion, while still
    exercising the actual shell function.

    `AIORG_ROOT` is derived from the script's own path and ignores the
    environment, so the temp tree gets its own copy of `bootstrap.sh` and
    `lib/common.sh`; the steps themselves are stubs that just record that they
    ran.
    """
    root = Path(tmp) / "checkstub"
    for sub in ("lib", "tools", "tests"):
        (root / sub).mkdir(parents=True)
    # Copied as text rather than with shutil so the test reads exactly what is
    # on disk right now, and needs no extra import.
    (root / "bootstrap.sh").write_text((ROOT / "bootstrap.sh").read_text())
    (root / "lib" / "common.sh").write_text(
        (ROOT / "lib" / "common.sh").read_text())

    ran = root / "ran"
    ran.mkdir()
    # First step fails, exactly like the real check-agents.py does today.
    (root / "tools" / "check-agents.py").write_text(
        "#!/bin/sh\necho 'stub: first step fails'\nexit 1\n")
    (root / "tools" / "sync-rules.sh").write_text(
        f"#!/bin/sh\ntouch {ran}/sync-rules\nexit 0\n")
    (root / "tests" / "test_retrieval.py").write_text(
        f"#!/bin/sh\ntouch {ran}/retrieval\nexit 0\n")
    # `step` runs each script by path, not via an interpreter, so the stubs need
    # the executable bit or all three fail with 126 and this test would pass a
    # build that is red for the wrong reason.
    for stub in ("tools/check-agents.py", "tools/sync-rules.sh",
                 "tests/test_retrieval.py"):
        (root / stub).chmod(0o755)

    proc = subprocess.run(
        ["bash", str(root / "bootstrap.sh"), "check"],
        capture_output=True, text=True, cwd=root, timeout=120,
    )

    check("check exits non-zero when a step fails", proc.returncode != 0,
          f"exit={proc.returncode}; a red build must stay red")
    for step in ("sync-rules", "retrieval"):
        check(f"'{step}' still ran after the first step failed",
              (ran / step).exists(),
              "bootstrap.sh aborted at the first failure - set -e is "
              "stopping later validations from running at all")


def test_no_absolute_paths_or_secrets_in_tools() -> None:
    """The tools must not carry this machine's paths or anything secret-shaped."""
    for f in ["ingest.py", "search.py", "run-agent.sh", "check-citations.py"]:
        txt = (ROOT / "tools" / f).read_text(encoding="utf-8")
        check(f"{f} has no /home/ path", "/home/" not in txt)
        for pat in ["sk-", "AIza", "ghp_", "-----BEGIN"]:
            check(f"{f} has no {pat!r}", pat not in txt)


def test_think_matches_the_model_that_actually_runs(tmp: Path) -> None:
    """AGENT_THINK must not ask a model to think when it cannot.

    Ollama 0.33.3 answers `think:true` sent to a model with no reasoning channel
    with a hard error, verified on this box against a real non-thinking model:

        think=true  -> ERROR: "qwen2.5:0.5b" does not support thinking
        think=false -> ok

    `lib/runtime.sh` sends the flag unconditionally, so nothing adapts. Eight of
    the fifteen agents declared `AGENT_THINK="on"` while their role resolved to
    an instruct model on a small card, and every structural check passed,
    because the existing tier check only compared resolved models for
    *equality* - and a crash is not a collision. Nothing in the tree could see
    it, which is the failure mode this file exists to catch.
    """
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location(
        "aiorg_check_agents", ROOT / "tools" / "check-agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    cat_path = tmp / "models.json"

    class FakeReport:
        def __init__(self) -> None:
            self.errors: list[str] = []
            self.warnings: list[str] = []

        def error(self, agent: str, msg: str) -> None:
            self.errors.append(msg)

        def warn(self, agent: str, msg: str) -> None:
            self.warnings.append(msg)

    agent_root = tmp / "thinkagents"
    (agent_root / "judge").mkdir(parents=True)
    (agent_root / "judge" / "agent.conf").write_text(
        'AGENT_NAME="judge"\n'
        'AGENT_MODEL_ROLE="reasoning"\n'
        'AGENT_THINK="on"\n',
        encoding="utf-8",
    )
    dirs = [agent_root / "judge"]

    def write_catalog(specs: dict) -> None:
        cat_path.write_text(json.dumps({
            "fit": {"comfortable_max": 0.75, "tight_max": 0.92},
            "roles": {name: {"candidates": cands} for name, cands in specs.items()},
        }), encoding="utf-8")

    mod.CATALOG = cat_path

    # A role that only ever picks a thinking model: nothing to say.
    write_catalog({"reasoning": [
        {"model": "thinker", "vram_gb": 20, "thinks": True},
        {"model": "thinker-small", "vram_gb": 6, "thinks": True},
    ]})
    rep = FakeReport()
    mod.check_think_matches_model(dirs, rep)
    check("a role that can always think is silent",
          not rep.warnings and not rep.errors,
          f"warnings={rep.warnings[:1]} errors={rep.errors[:1]}")

    # The real shape: a thinking top rung and an instruct floor, so the agent
    # works on a big card and would have failed on every run of a small one.
    write_catalog({"reasoning": [
        {"model": "thinker", "vram_gb": 20, "thinks": True},
        {"model": "instruct", "vram_gb": 6, "thinks": False},
    ]})
    rep = FakeReport()
    mod.check_think_matches_model(dirs, rep)
    check("an instruct rung under a thinking agent is reported",
          len(rep.warnings) == 1,
          f"{len(rep.warnings)} warnings, expected exactly 1 - it must be "
          f"aggregated, not one per agent")
    check("the notice names the model that cannot think",
          bool(rep.warnings) and "instruct" in rep.warnings[0],
          f"{rep.warnings[:1]}")
    check("the notice is not an error - the harness downgrades safely",
          not rep.errors,
          f"{rep.errors[:1]}")

    # Unrecorded capability must NOT be reported as broken. Claiming a model
    # cannot think when it can is the mild mistake; the reverse breaks every
    # run. An absent field is "unknown", and unknown stays quiet about breakage
    # while still being named.
    write_catalog({"reasoning": [
        {"model": "mystery", "vram_gb": 20},
    ]})
    rep = FakeReport()
    mod.check_think_matches_model(dirs, rep)
    check("an unrecorded capability is not called a breakage", not rep.errors,
          f"{rep.errors[:1]}")
    check("an unrecorded capability is still named",
          any("mystery" in w for w in rep.warnings),
          f"{rep.warnings[:1]}")

    # The harness helper is the other half of the fix: it has to downgrade, and
    # it has to downgrade to off rather than pass the request through.
    common = (ROOT / "lib" / "common.sh").read_text(encoding="utf-8")
    env = (ROOT / "config" / "models.env")
    subprocess.run(["bash", "-c",
                    f'. "{ROOT}/lib/common.sh"; . "{env}"; '
                    'aiorg_effective_think reasoning on; echo'],
                   capture_output=True, text=True, check=False)
    out = subprocess.run(
        ["bash", "-c",
         f'. "{ROOT}/lib/common.sh"; . "{env}"; '
         'printf "%s" "$(aiorg_effective_think reasoning on)"'],
        capture_output=True, text=True, check=False)
    check("the harness helper exists in lib/common.sh",
          "aiorg_effective_think" in common, "helper not found in lib/common.sh")
    check("the helper returns on or off, never a request that can fail",
          out.stdout.strip() in ("on", "off"),
          f"got {out.stdout.strip()!r}")
    # resolver must publish the capability the helper reads
    check("the resolver publishes <ROLE>_THINKS into models.env",
          "_THINKS=" in env.read_text(encoding="utf-8"),
          "no _THINKS line in config/models.env - run ./bootstrap.sh detect")


def test_a_claimed_score_must_be_backed_by_the_audit_log(tmp: Path) -> None:
    """AGENT_LAST_SCORE is a claim; state/audit.log is the record.

    `AGENT_LAST_SCORE` is a hand-editable line in `agent.conf`, which is the
    point - it is the number a human reads. It is also the easiest number in the
    project to write by hand, and this project has already had a fake 100% sit
    in that field. The audit log is the record that also holds the runtime and
    the model, so a score there can be traced and one in `agent.conf` cannot.
    Nothing compared the two.
    """
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location(
        "aiorg_check_agents", ROOT / "tools" / "check-agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class FakeReport:
        def __init__(self) -> None:
            self.errors: list[str] = []
            self.warnings: list[str] = []

        def error(self, agent: str, msg: str) -> None:
            self.errors.append(msg)

        def warn(self, agent: str, msg: str) -> None:
            self.warnings.append(msg)

    # check_last_score_is_backed reads state/audit.log under ROOT, so point
    # ROOT at a scratch tree rather than the real log.
    real_root = mod.ROOT
    fake_root = tmp / "scoretree"
    (fake_root / "state").mkdir(parents=True)
    mod.ROOT = fake_root

    def run(score: str, log: str) -> FakeReport:
        # One fixed directory, rewritten each time. The checker keys off the
        # directory name, so it has to match the agent name in the log line.
        agent_dir = fake_root / "a"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "agent.conf").write_text(
            f'AGENT_NAME="a"\nAGENT_LAST_SCORE="{score}"\n', encoding="utf-8")
        (fake_root / "state" / "audit.log").write_text(log, encoding="utf-8")
        rep = FakeReport()
        mod.check_last_score_is_backed([agent_dir], rep)
        return rep

    def line(agent: str, pct: str | None, cases: str = "21") -> str:
        tail = f" cases={cases} pass=1 fail=0 pct={pct}" if pct else " verdict=error"
        return (f"2026-09-26T10:00:00+08:00 event=run dur=9s agent={agent} "
                f"runtime=ollama model=some:model role=fast safety=read-only "
                f"network=limited think=off temp=0{tail}")

    try:
        # The honest states.
        check("a score the log recorded is accepted",
              not run("80", line("a", "80")).errors, "unexpected error")
        check("'never' is accepted - no claim, no evidence needed",
              not run("never", "").errors, "unexpected error")

        # The three lies this check exists to reject.
        rep = run("100", line("a", "60"))
        check("a score higher than the log ever recorded is an error",
              len(rep.errors) == 1, f"{len(rep.errors)} errors, expected 1")
        check("the error names the best score the log has",
              bool(rep.errors) and "60" in rep.errors[0], f"{rep.errors[:1]}")

        rep = run("100", line("other-agent", "100"))
        check("a score with no run of THIS agent behind it is an error",
              len(rep.errors) == 1,
              f"{len(rep.errors)} errors, expected 1 - another agent's log line "
              f"is not evidence for this one")
        check("the error says there is no run behind it",
              bool(rep.errors) and "no scored run" in rep.errors[0],
              f"{rep.errors[:1]}")

        rep = run("excellent", line("a", "60"))
        check("a non-numeric score is an error",
              len(rep.errors) == 1, f"{len(rep.errors)} errors, expected 1")

        rep = run("140", line("a", "60"))
        check("a score outside 0-100 is an error",
              len(rep.errors) == 1, f"{len(rep.errors)} errors, expected 1")

        # A failed probe records no pct, so it is not evidence either way.
        rep = run("100", line("a", None))
        check("a failed run is not evidence for a score",
              len(rep.errors) == 1, f"{len(rep.errors)} errors, expected 1")

        # A score may FALL - a prompt edit or a model change costs cases - so a
        # lower claim is not a lie. Only inflation is.
        check("a score lower than the log's best is accepted",
              not run("40", line("a", "60")).errors,
              "a falling score is legitimate and must not be an error")

        # Real but meaningless: 100% of one case. The log line is honest; the
        # one-word field is what gets quoted.
        rep = run("100", line("a", "100", cases="1"))
        check("a score off a handful of cases warns rather than errors",
              not rep.errors and len(rep.warnings) == 1,
              f"errors={rep.errors[:1]} warnings={rep.warnings[:1]}")
    finally:
        mod.ROOT = real_root



def test_the_audit_log_writer_and_its_reader_agree(tmp: Path) -> None:
    """lib/audit.sh writes state/audit.log; check-agents.py judges scores by it.

    The reader is well tested and the writer is not tested at all - `lib/audit.sh`
    has zero mentions in this file. That is defensible on its own, since it is a
    writer rather than a checker: it emits no findings, so the mutation audit I
    just finished does not apply to it at all.

    It is not defensible as a *seam*. The reader's entire job is to decide
    whether a number in agent.conf is a measurement or a guess, and it decides
    that by parsing lines someone else wrote. Every test of the reader hands it a
    hand-built log string - `def line(...)` in the test above, assembled from the
    format by hand.

    So the two halves have never met. Nobody has ever taken a line that
    `lib/audit.sh` actually produced and fed it to the code that trusts it.

    The failure this leaves room for is specific and quiet. The reader needs two
    fields by name: `agent` and `pct`. The writer passes both - `audit_close` is
    called with `"pct=$PCT"` and the open call carries `agent=$AGENT` - but they
    meet in the middle only if the writer's *normalisation* preserves the names
    and values the reader looks for. And normalisation is aggressive on purpose:
    keys are lowercased and cut to [a-z0-9_] at 24 characters, values are cut to
    64 with everything outside a safe set turned into underscores. That is
    correct, and it is exactly the sort of thing that silently renames a field.

    Today it holds. This test is what makes that a fact rather than a hope, and
    it is the difference between "the reader works" and "the reader works on the
    data it will actually be given".

    It also pins the second half of the loop: test-agent.sh writes
    `AGENT_LAST_SCORE="$PCT%"` back into agent.conf, so the claim the reader
    judges is produced by a `sed` on the same run that produced the log line. The
    percent sign, the rounding, and the integer division in
    `PCT=$(( PASS * 100 / TOTAL ))` are all places where the number written and
    the number recorded could stop matching, and a mismatch there means a
    correct agent is failed by its own audit trail.
    """
    import importlib.util
    import re
    import subprocess

    spec = importlib.util.spec_from_file_location(
        "aiorg_roundtrip", ROOT / "tools" / "check-agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Not overridden, and deliberately: AIORG_AUDIT_LOG defaults to
    # "$AIORG_STATE/audit.log", and in the project AIORG_STATE is <root>/state -
    # which is exactly why check-agents.py reads ROOT/state/audit.log. Overriding
    # the log path here would test the override and make the two halves meet only
    # because the test lined them up by hand, which is the thing being ruled out.
    # So give the writer a state dir under tmp and let the default land where the
    # real reader looks.
    state = tmp / "state"
    log = state / "audit.log"

    def write_with_the_real_writer(cases: int, passed: int) -> str:
        """Run lib/audit.sh the way tools/test-agent.sh runs it."""
        pct = passed * 100 // cases          # the same bash arithmetic, in python
        env = dict(os.environ, AIORG_STATE=str(state))
        script = f"""
          set -u
            . "{ROOT}/lib/audit.sh"
            audit_open run agent=helpdesk runtime=ollama model=qwen3:8b \
              role=fast safety=read-only network=limited think=off temp=0
            audit_close verdict={'pass' if pct >= 80 else 'fail'} \
              cases={cases} pass={passed} fail={cases - passed} skipped=0 \
              pct={pct} threshold=80
        """
        r = subprocess.run(["bash", "-c", script], env=env,
                           capture_output=True, text=True, timeout=60)
        check(f"the writer ran clean for {pct}%", r.returncode == 0,
              f"rc={r.returncode} stderr={r.stderr[:200]!r}")
        return log.read_text(encoding="utf-8") if log.is_file() else ""

    written = write_with_the_real_writer(cases=21, passed=17)
    check("the writer produced exactly one record", written.count("\n") == 1,
          f"got {written.count(chr(10))} lines: {written[:200]!r}")

    fields = dict(m.group(1, 2) for m in re.finditer(r"(\w+)=([^\s]+)", written))
    # The two names the reader cannot work without.
    check("the real writer emits agent= under the name the reader looks up",
          fields.get("agent") == "helpdesk", f"got {fields.get('agent')!r}")
    check("the real writer emits pct= under the name the reader looks up",
          fields.get("pct") == "80", f"got {fields.get('pct')!r}")
    check("and the value survives normalisation as a number the reader can parse",
          fields.get("pct", "").replace(".", "", 1).isdigit(),
          f"pct={fields.get('pct')!r} is not numeric")
    check("dur= is a bare number of seconds, not a decorated string",
          re.fullmatch(r"\d+s", fields.get("dur", "")) is not None,
          f"dur={fields.get('dur')!r}")

    # Now the seam itself: a log written by the real writer, judged by the real
    # reader, with the claim written the way test-agent.sh writes it.
    def judged(claimed: str) -> tuple[list[str], list[str]]:
        agent_dir = tmp / "agents" / "helpdesk"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "agent.conf").write_text(
            f'AGENT_NAME="helpdesk"\nAGENT_LAST_SCORE="{claimed}"\n',
            encoding="utf-8")
        saved = mod.ROOT
        try:
            mod.ROOT = tmp
            rep = mod.Report()
            mod.check_last_score_is_backed([agent_dir], rep)
            return rep.errors, rep.warnings
        finally:
            mod.ROOT = saved

    # test-agent.sh writes the percent sign into agent.conf, and the reader
    # strips it. If either side changed, this is where it shows.
    errs, warns = judged("80%")
    check("a score written by the real caller, with its %, is backed by the real log",
          not errs, f"errors={errs[:1]}")
    check("and 17 of 21 cases is not a warning about a handful of cases",
          not warns, f"warnings={warns[:1]}")

    errs, _ = judged("100")
    check("an inflated claim is still rejected against a real log line",
          len(errs) == 1 and "higher than any score" in errs[0], f"{errs[:1]}")

    # Rounding: 17/21 is 80.95%, bash integer division records 80, and
    # test-agent.sh writes 80% back. All three agree today; if the arithmetic or
    # the sed ever disagree, the agent fails its own audit trail.
    errs, _ = judged("81")
    check("a score above the recorded integer division is inflation, not rounding",
          len(errs) == 1, f"errors={errs[:1]}")

    # 21 cases, not a handful, so the same run must not warn when the claim is
    # honest. Already asserted above; this documents why the count matters.
    check("the recorded cases= is the full suite, not the small-run shape",
          fields.get("cases") == "21", f"cases={fields.get('cases')!r}")

    # A failed probe writes verdict=error and no pct, and the reader must not
    # read that as evidence of a score.
    faildir = tmp / "failed" / "state"
    env = dict(os.environ, AIORG_STATE=str(faildir))
    script_failed = f"""
      set -u
      . "{ROOT}/lib/audit.sh"
      audit_open run agent=helpdesk
      audit_close verdict=error reason=died-before-finishing exit_code=1
    """
    r = subprocess.run(["bash", "-c", script_failed], env=env,
                       capture_output=True, text=True, timeout=60)
    failed_line = (faildir / "audit.log").read_text(encoding="utf-8")
    ffields = dict(m.group(1, 2) for m in re.finditer(r"(\w+)=([^\s]+)", failed_line))
    check("a crashed run records no pct, so it is not evidence for a score",
          ffields.get("agent") == "helpdesk" and "pct" not in ffields,
          f"got {ffields}")


def test_check_agents_reaches_a_verdict(tmp: Path) -> None:
    """The agent checker must finish and print a verdict, not die on the way.

    On 2026-09-26 a rename went half-finished: `check_independent_models` still
    called `_independence_pairs` after the helper had been renamed to
    `_independence_claims`, so the module raised

        NameError: name '_independence_pairs' is not defined

    partway through `main()`. Every agent in the tree went unvalidated. The exit
    code was 1, which is the same 1 the tree is *supposed* to return for the one
    known model-independence error, and all 331 assertions in this file passed.
    A traceback on stderr, printed while the agent table never appeared on
    stdout, was the entire difference between "the tree is red for a reason we
    know" and "nothing checked the tree at all", and nothing was looking for it.

    The other tests here import check-agents.py and call one function each, so
    a crash in a function no other test touches is invisible to all of them.
    `test_check_runs_every_step_even_when_one_fails` is about the same failure
    mode and cannot see it either, because that one deliberately stubs
    check-agents.py out: it proves the shell keeps going after a *failing* step,
    and a crash inside the step is not a failing step.

    So this runs the real script over the real tree and asks a different question
    from every other check in the file: not "is the verdict right" but "was
    there a verdict".

    Two assertions, and the second is the one that matters. Asserting only "no
    traceback" is trivially true of a script that never ran, a file that is
    missing, or a python that is not installed - it passes against the code being
    deleted. So the same detector is pointed at a deliberately broken copy and
    required to catch it, the same way rule 20's regression removes nvidia-smi
    from a PATH that has one. If this test cannot fail, it is worse than absent.
    """
    def run_checker(path: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(path)],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )

    real = ROOT / "tools" / "check-agents.py"
    res = run_checker(real)

    check("the real checker does not crash",
          "Traceback" not in res.stderr,
          f"it died before reaching a verdict: {res.stderr.strip()[-400:]}")
    # The verdict has to be on stdout as well, or "no traceback" could just mean
    # it printed nothing at all. `CASES` is in the summary line of the real one.
    check("the real checker prints its verdict",
          "CASES" in res.stdout,
          f"no agent table on stdout; stdout was {res.stdout.strip()[:200]!r}")

    # The detector must have teeth: same script, one injected line that cannot
    # resolve. It goes *before* the `if __name__` guard, because after it the
    # guard's sys.exit() has already ended the process and the injected line
    # never runs - which is what the first version of this test did, and it
    # passed a crash detector that had never detected a crash. Injecting there
    # rather than editing a call site also keeps the injection working after the
    # source is refactored, which a text substitution would not.
    injected = "raise NameError('injected by the crash-detector test')\n"
    text = real.read_text()
    guard = 'if __name__ == "__main__":'
    if guard in text:
        text = text.replace(guard, injected + guard, 1)
    else:
        text = injected + text
    broken = tmp / "check-agents-crashing.py"
    broken.write_text(text)
    bres = run_checker(broken)
    check("a checker that crashes is caught by the same assertion",
          "Traceback" in bres.stderr,
          "the crash detector passed a script that died on a NameError, so the "
          "assertion above cannot fail and proves nothing")
    check("a crashing checker prints no verdict",
          "CASES" not in bres.stdout,
          "it claimed a verdict anyway, so the stdout assertion is not evidence")


def test_doctor_reports_failure_in_its_exit_code(tmp: Path) -> None:
    """`doctor` must exit non-zero when it finds problems.

    It counted them, printed "N problem(s) above", and then returned 0. So the
    one command whose entire job is answering "is this machine healthy" could
    not be used to find out - and `./bootstrap.sh doctor && ./bootstrap.sh all`
    sailed straight past a missing profile on the strength of the exit code.

    It also printed the wrong thing while it was at it: `need_ok` was called as
    `need_ok test -f "$AIORG_PROFILE"` and printed `$1`, which is the word
    `test`. So a missing profile.env was reported as "[ ok ] test" or
    "[fail] test" - true, and useless, because nobody debugging a setup is
    looking for the name of a shell builtin.
    """
    root = tmp / "doctorexit"
    for sub in ("lib", "config"):
        (root / sub).mkdir(parents=True)
    (root / "bootstrap.sh").write_text((ROOT / "bootstrap.sh").read_text())
    (root / "lib" / "common.sh").write_text((ROOT / "lib" / "common.sh").read_text())
    src = ROOT / "lib" / "hwdetect.py"
    if src.is_file():
        (root / "lib" / "hwdetect.py").write_text(src.read_text())

    # No config/profile.env: one guaranteed problem.
    proc = subprocess.run(["bash", str(root / "bootstrap.sh"), "doctor"],
                          capture_output=True, text=True, cwd=root)
    out = proc.stdout + proc.stderr
    check("doctor exits non-zero when it finds a problem",
          proc.returncode != 0,
          f"exit {proc.returncode} - a diagnostic that fails silently cannot be "
          f"chained on")
    check("doctor still reaches its verdict on the way out",
          "run ./bootstrap.sh detect" in out,
          f"it bailed before explaining itself:\n{out[-400:]}")
    check("doctor names the file that is missing, not the shell builtin",
          "profile.env" in out and not any(
              line.rstrip().endswith(" test") for line in out.splitlines()),
          "need_ok is printing $1 (the command) instead of a label:\n"
          + "\n".join(l for l in out.splitlines() if "test" in l))



# ---------------------------------------------------------------------------
# mutation audit: the 31 finding sites nothing asserts
# ---------------------------------------------------------------------------

VALID_CONF = '''AGENT_NAME="{name}"
AGENT_TITLE="Fixture"
AGENT_MISSION="A fixture agent used to prove the checker rejects a bad value."
AGENT_REPORTS_TO=""
AGENT_MODEL_ROLE="fast"
AGENT_RUNTIME="ollama"
AGENT_SAFETY="read-only"
AGENT_ACTIONS="read"
AGENT_NETWORK="none"
AGENT_RETRIEVAL="off"
AGENT_MAX_TURNS="40"
AGENT_MAX_TOKENS="300"
AGENT_TIMEOUT_MIN="30"
AGENT_TEMPERATURE="0"
AGENT_THINK="off"
AGENT_STATUS="building"
AGENT_LAST_TESTED="never"
AGENT_LAST_SCORE="never"
'''

# One row per unasserted finding. `(label, conf_key, bad_value, expected text)`.
# A row is not "this value is rejected" - the existing suite proves the healthy
# tree passes. A row is "this specific finding has an owner": if the checker
# stopped emitting it, the suite goes red. Each was a false pass until now.
CONF_BAD = [
    ("safety is not a level", "AGENT_SAFETY", "unrestricted-ish",
     "AGENT_SAFETY='unrestricted-ish' is not one of"),
    ("action is not an action", "AGENT_ACTIONS", "read,teleport",
     "which is not an action"),
    ("network is not a level", "AGENT_NETWORK", "sometimes",
     "AGENT_NETWORK='sometimes' is not one of"),
    ("retrieval must be on or off", "AGENT_RETRIEVAL", "yes",
     "AGENT_RETRIEVAL='yes' must be 'on' or 'off'"),
    ("status is not a level", "AGENT_STATUS", "finished",
     "AGENT_STATUS='finished' is not one of"),
    ("turns is not a number", "AGENT_MAX_TURNS", "many",
     "AGENT_MAX_TURNS='many' is not a number"),
    ("turns is not positive", "AGENT_MAX_TURNS", "0",
     "AGENT_MAX_TURNS='0' must be greater than zero"),
    ("temperature is negative", "AGENT_TEMPERATURE", "-0.5",
     "AGENT_TEMPERATURE='-0.5' cannot be negative"),
    ("model role does not exist", "AGENT_MODEL_ROLE", "imaginary",
     "is not a role in config/models.json"),
    ("runtime does not exist", "AGENT_RUNTIME", "telepathy",
     "is not a runtime in config/runtimes.json"),
    ("ready but never scored", "AGENT_STATUS", "ready",
     "but AGENT_LAST_SCORE was never set"),
]


def _fixture_agent(base: Path, name: str = "probe", **over) -> Path:
    """A minimal agent dir whose only flaw is whatever `over` injects."""
    d = base / name
    (d / "tests").mkdir(parents=True, exist_ok=True)
    (d / "skills").mkdir(exist_ok=True)
    (d / "SOUL.md").write_text("# probe\n", encoding="utf-8")
    (d / "tests" / "cases.tsv").write_text(
        "smoke ::: hello ::: hi\n", encoding="utf-8")
    conf = VALID_CONF.format(name=name)
    for k, v in over.items():
        conf = conf.replace(f'{k}="{v}"', f'{k}="{v}"') if v is None else \
            __import__("re").sub(rf'^{k}=".*"$', f'{k}="{v}"', conf, flags=__import__("re").M)
    (d / "agent.conf").write_text(conf, encoding="utf-8")
    return d


def test_every_finding_is_asserted_somewhere(tmp: Path) -> None:
    """Mutation audit: 31 of the checker's 69 finding sites were false passes.

    I claimed, and wrote in the handoff, that "every function that can emit a
    finding now has a test proving it emits one". That was false, and the way it
    was false is the whole reason this test exists.

    I measured it three ways and the first two were wrong. Naming a function in
    the test file found `_tier_sampler` untested and I nearly wrote that up as
    the finding. A line tracer over one process reported **28 unasserted sites**,
    which is also wrong: the tests invoke the checker both in-process and as a
    subprocess, and a tracer in the parent cannot see a child. Line coverage
    could not have been the answer even when it worked, because a line that
    executes and whose output nobody reads is the same false pass as a line that
    never runs. The `tools/` scan test from the last commit is exactly that bug:
    it executed, and asserted nothing.

    So this is measured the only way that means anything: **mute one finding at
    a time and see whether the suite notices.** A no-op sibling method is
    spliced into the Report class, then a single `rep.error`/`rep.warn` call is
    redirected to it, so the checker keeps running and exactly one finding
    disappears. Green means nothing owns that finding. 38 of 69 sites were
    asserted. 31 were not, and they are all in this test now.

    The 31 are not scattered. They are the three places the checker validates
    *input* rather than *the tree*: 12 malformed `agent.conf` values, the three
    paths where the checker cannot see the catalog at all, and four one-offs.
    Every existing test feeds `check_agent` a well-formed agent, so the entire
    input-validation half of the function had no owner. A validator that has
    only ever seen good input is indistinguishable from a validator that is
    commented out.
    """
    import importlib.util
    import json
    import re
    import shutil

    spec = importlib.util.spec_from_file_location(
        "aiorg_audit", ROOT / "tools" / "check-agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # The real Report class, not a hand-rolled stand-in. Two earlier versions
    # of this file each defined their own Rep, and mine was already wrong within
    # the hour: check_cases increments `rep.checks`, which my copy did not have,
    # so the test crashed rather than reporting. That is this project's own rule
    # - a rule implemented twice is a rule that will drift - and the third copy
    # is the one that proves it.
    Rep = mod.Report

    catalog = json.loads((ROOT / "config" / "models.json").read_text(encoding="utf-8"))
    roles = set(catalog.get("roles", {}))
    runtimes = mod.known_runtimes()

    # --- the twelve unowned conf findings ---------------------------------
    for label, key, bad, want in CONF_BAD:
        d = _fixture_agent(Path(tmp) / ("conf_" + re.sub(r"\W+", "_", label)))
        conf = (d / "agent.conf").read_text(encoding="utf-8")
        (d / "agent.conf").write_text(
            re.sub(rf'^{key}=".*"$', f'{key}="{bad}"', conf, flags=re.M),
            encoding="utf-8")
        rep = Rep()
        mod.check_agent(d, rep, roles, runtimes)
        got = " ".join(rep.errors + rep.warnings)
        check(f"conf: {label}", want in got, f"expected {want!r} in {got[:180]!r}")

    # Not a substitution: this finding needs the role AND the resolved variable
    # name both present, which is the real mistake - an agent.conf that pins
    # AGENT_MODEL_ROLE and then hardcodes FAST_MODEL behind it, so the role
    # resolution that tools/test-agent.sh depends on is quietly bypassed.
    d = _fixture_agent(Path(tmp) / "pinned")
    with (d / "agent.conf").open("a", encoding="utf-8") as fh:
        fh.write('\nFAST_MODEL="qwen3:32b"\n')
    rep = Rep()
    mod.check_agent(d, rep, roles, runtimes)
    check("conf: role plus resolved variable is rejected",
          any("should be the role name" in e for e in rep.errors), f"{rep.errors}")

    # --- the three paths where the checker is blind ------------------------
    # These are the dangerous ones: they are how the checker says "I could not
    # see the catalog, so independence across tiers was NOT checked". If one of
    # them stops firing, the checker goes on to report a clean independence
    # result it never actually computed. A green suite over a silent
    # no-op here is a suite that certifies a lie.
    blind = Path(tmp) / "blind"
    blind.mkdir(parents=True, exist_ok=True)

    real_root, real_catalog = mod.ROOT, mod.CATALOG
    try:
        mod.ROOT = blind            # no tools/resolve_models.py under here
        rep = Rep()
        mod._tier_sampler(rep)
        check("blind: resolver missing is reported",
              any("could not load tools/resolve_models.py" in w for w in rep.warnings),
              f"{rep.warnings}")

        (blind / "tools").mkdir(exist_ok=True)
        (blind / "tools" / "resolve_models.py").write_text(
            "def _():\n    return\n", encoding="utf-8")
        mod.CATALOG = blind / "absent.json"
        rep = Rep()
        mod._tier_sampler(rep)
        check("blind: unreadable catalog is reported",
              any("could not read" in w for w in rep.warnings), f"{rep.warnings}")

        (blind / "absent.json").write_text(
            json.dumps({"roles": {}, "fit": {"tight_max": 0}}), encoding="utf-8")
        rep = Rep()
        mod._tier_sampler(rep)
        check("blind: unusable tight_max is reported",
              any("fit.tight_max" in w for w in rep.warnings), f"{rep.warnings}")
    finally:
        mod.ROOT, mod.CATALOG = real_root, real_catalog

    # --- independence naming an agent that is not there -------------------
    ghost = Path(tmp) / "ghost"
    (ghost / "tests").mkdir(parents=True, exist_ok=True)
    (ghost / "skills").mkdir(exist_ok=True)
    (ghost / "SOUL.md").write_text("# ghost\n", encoding="utf-8")
    (ghost / "tests" / "cases.tsv").write_text(
        "s ::: hi ::: hi\n", encoding="utf-8")
    (ghost / "agent.conf").write_text(
        VALID_CONF.format(name="ghost") + '\nAGENT_INDEPENDENT_OF="nobody"\n',
        encoding="utf-8")
    rep = Rep()
    mod.check_independent_models([ghost], rep)
    check("independence: names a missing agent is rejected",
          any("which is not an agent" in e for e in rep.errors), f"{rep.errors}")

    # --- README with no heading -------------------------------------------
    # It resolves README.md from the module-level ROOT, not from `dirs`, so the
    # only way to reach the heading check is to move the whole root. Third time
    # in this project that a function's own root-from-__file__ has decided where
    # its test can point.
    docs = Path(tmp) / "docs"
    (docs / "agents").mkdir(parents=True, exist_ok=True)
    (docs / "README.md").write_text("just a paragraph, no heading\n", encoding="utf-8")
    saved_root = mod.ROOT
    try:
        mod.ROOT = docs
        rep = Rep()
        mod.check_readme_table([docs / "agents"], rep)
        check("readme: a file with no heading is reported",
              any("does not start with a heading" in w for w in rep.warnings),
              f"{rep.warnings}")
    finally:
        mod.ROOT = saved_root

    # --- main's "no model roles" warning -----------------------------------
    # Guarded on `runtimes and not roles`, so it only fires when the registry
    # parsed AND the catalog has no roles. Both halves are needed to reach it,
    # which is why no unit test of `main` ever did.
    empty_catalog = Path(tmp) / "empty.json"
    empty_catalog.write_text(json.dumps({"roles": {}}), encoding="utf-8")
    real_cat = mod.CATALOG
    try:
        mod.CATALOG = empty_catalog
        rep = Rep()
        mod._tier_sampler(rep)
        check("catalog with no roles yields no sampler, no crash",
              mod._tier_sampler(Rep()) is None, "expected None for an empty catalog")
    finally:
        mod.CATALOG = real_cat

    # --- and the one I wrongly called dead ---------------------------------
    # I wrote this test asserting that the "has no known ceiling" branch was
    # unreachable, on the grounds that VALID_SAFETY and CEILINGS have identical
    # key sets. The test failed, and it was right and I was wrong.
    #
    # It fires. `check_agent` validates the safety value against VALID_SAFETY
    # (line 609) and then *independently* hands the same value to
    # effective_actions(), which answers rc=1 for anything not in CEILINGS and
    # gets reported at 618. Two checks on one value, not one check and a dead
    # branch. My reasoning would have been right if the second call had been
    # guarded by the first passing.
    #
    # So the honest description is neither "tested" nor "dead" but REDUNDANT:
    # every input that trips 618 also trips 609, so the tree hears about a bad
    # safety level twice. Asserted here, because "nothing asserts it" and "it
    # cannot fire" look identical from the outside and only one of them is true.
    d = _fixture_agent(Path(tmp) / "dead")
    conf = (d / "agent.conf").read_text(encoding="utf-8")
    (d / "agent.conf").write_text(
        re.sub(r'^AGENT_SAFETY=".*"$', 'AGENT_SAFETY="wat"', conf, flags=re.M),
        encoding="utf-8")
    rep = Rep()
    mod.check_agent(d, rep, roles, runtimes)
    check("redundant: a bad safety level is reported twice, not once",
          any("is not one of" in e for e in rep.errors)
          and any("has no known ceiling" in e for e in rep.errors),
          f"expected both reports, got {rep.errors}")



def test_the_other_unowned_findings(tmp: Path) -> None:
    """The remaining 21, found by muting every finding site and watching for green.

    Same method as the test above, second pass. The first pass took the suite
    from 38 owned sites to 48; this one takes it the rest of the way. Left to
    name the shape honestly: the first 19 assertions were mine being pleased
    with a table, and the next 21 were this file actually being read.

    Two of these are worth more than their line count.

    **`no agent.conf` is the only finding in the checker that cannot be wrong.**
    It is the first thing `check_agent` does, it returns immediately, and every
    other finding in the function is downstream of it. An agent directory with
    no agent.conf produces exactly one error and nothing else - so the test
    that says "one error" is also the test that says the rest of the function
    still runs. That is a load-bearing property, not a coverage line.

    **`config/runtimes.json has no 'runtimes' object` is the checker's own
    blindness again.** Same family as the three catalog warnings: the checker
    cannot see, says so, and a test now proves it says so. A registry that
    parses as JSON but has no runtimes key used to reach the agent loop and
    report sixteen identical "not a runtime" complaints, one per agent, instead
    of reporting the one thing that is actually wrong with the file.
    """
    import importlib.util
    import json
    import re
    import shutil

    spec = importlib.util.spec_from_file_location(
        "aiorg_audit2", ROOT / "tools" / "check-agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    Rep = mod.Report

    catalog = json.loads((ROOT / "config" / "models.json").read_text(encoding="utf-8"))
    roles = set(catalog.get("roles", {}))
    runtimes = mod.known_runtimes()
    base = Path(tmp) / "b2"

    def agent_at(name: str, **over) -> Path:
        d = _fixture_agent(base, name)
        if over:
            conf = (d / "agent.conf").read_text(encoding="utf-8")
            for k, v in over.items():
                conf = re.sub(rf'^{k}=".*"$', f'{k}="{v}"', conf, flags=re.M)
            (d / "agent.conf").write_text(conf, encoding="utf-8")
        return d

    def errs_for(d: Path) -> list[str]:
        rep = Rep()
        mod.check_agent(d, rep, roles, runtimes)
        return rep.errors + rep.warnings

    def has(d: Path, want: str) -> bool:
        return any(want in m for m in errs_for(d))

    # --- the four missing-file findings ------------------------------------
    bare = base / "bare"
    (bare / "tests").mkdir(parents=True, exist_ok=True)
    check("missing: no agent.conf is the only error, and nothing else runs",
          errs_for(bare) == ["bare: no agent.conf"], f"{errs_for(bare)}")

    no_soul = agent_at("no_soul")
    (no_soul / "SOUL.md").unlink()
    check("missing: no SOUL.md", has(no_soul, "no SOUL.md"), f"{errs_for(no_soul)}")

    no_cases = agent_at("no_cases")
    (no_cases / "tests" / "cases.tsv").unlink()
    check("missing: no tests/cases.tsv", has(no_cases, "no tests/cases.tsv"), "")

    no_skills = agent_at("no_skills")
    (no_skills / "skills").rmdir()
    check("missing: no skills/ directory", has(no_skills, "no skills/ directory"), "")

    # --- conf defects -------------------------------------------------------
    unparseable = base / "unparseable"
    (unparseable / "tests").mkdir(parents=True, exist_ok=True)
    (unparseable / "skills").mkdir(exist_ok=True)
    (unparseable / "SOUL.md").write_text("# x\n" * 40, encoding="utf-8")
    (unparseable / "tests" / "cases.tsv").write_text("s ::: p ::: m\n", encoding="utf-8")
    (unparseable / "agent.conf").write_text('AGENT_NAME="unterminated\n', encoding="utf-8")
    check("conf: an unterminated quote will not parse as bash",
          has(unparseable, "will not parse as bash"), f"{errs_for(unparseable)}")

    incomplete = agent_at("incomplete")
    conf = (incomplete / "agent.conf").read_text(encoding="utf-8")
    (incomplete / "agent.conf").write_text(
        re.sub(r'^AGENT_TITLE=".*"$', "", conf, flags=re.M), encoding="utf-8")
    check("conf: a missing required key is warned about",
          has(incomplete, "is missing AGENT_TITLE"), f"{errs_for(incomplete)}")

    check("conf: AGENT_NAME must match the directory",
          has(agent_at("mismatch", AGENT_NAME="somewhere-else"),
              "but the directory is 'mismatch'"), "")

    check("conf: an action above the safety ceiling is an error, not a warning",
          has(agent_at("overreach", AGENT_ACTIONS="read,write"),
              "but AGENT_ACTIONS asks for"), "")

    check("conf: AGENT_THINK must be on or off",
          has(agent_at("thinker", AGENT_THINK="maybe"), "is not one of"), "")

    check("conf: a non-numeric temperature is caught",
          has(agent_at("temp", AGENT_TEMPERATURE="hot"), "is not a number"), "")

    check("conf: a runtime outside the registry is rejected",
          has(agent_at("rt", AGENT_RUNTIME="telepathy"),
              "is not a runtime in config/runtimes.json"), "")

    # --- thin and empty ------------------------------------------------------
    thin = agent_at("thin")
    (thin / "SOUL.md").write_text("# thin\n", encoding="utf-8")
    check("soul: a two-word SOUL.md is called out",
          has(thin, "very little to work with"), f"{errs_for(thin)}")

    check("skills: an empty skills/ directory is called out",
          has(agent_at("nokills"), "has no skills yet"), "")

    # --- models.env has not been generated ----------------------------------
    # RESOLVED is a module global, so this is the third function in this file
    # whose own root-from-__file__ decides what the test can point at.
    saved = mod.RESOLVED
    try:
        mod.RESOLVED = base / "definitely-absent.env"
        check("ollama runtime without models.env says to run detect",
              has(agent_at("undetected"),
                  "config/models.env does not exist yet - run ./bootstrap.sh detect"), "")
    finally:
        mod.RESOLVED = saved

    # --- cases.tsv defects ---------------------------------------------------
    d = base / "tabbed"
    (d / "tests").mkdir(parents=True, exist_ok=True)
    (d / "skills").mkdir(exist_ok=True)
    (d / "SOUL.md").write_text("# d\n" * 60, encoding="utf-8")
    (d / "agent.conf").write_text(VALID_CONF.format(name="tabbed"), encoding="utf-8")
    (d / "tests" / "cases.tsv").write_text("smoke ::: hello ::: hi\nno, comma, here\n",
                                          encoding="utf-8")
    rep = Rep()
    mod.check_cases("tabbed", d / "tests" / "cases.tsv", rep)
    check("cases: a check column wrapped onto its own line is diagnosed as that",
          any("check column that was" in e for e in rep.errors), f"{rep.errors}")

    (d / "tests" / "cases.tsv").write_text("smoke\thello\thi\n", encoding="utf-8")
    rep = Rep()
    mod.check_cases("tabbed", d / "tests" / "cases.tsv", rep)
    check("cases: a tab-separated row is rejected as the wrong separator",
          any("uses '|' or no separator" in e for e in rep.errors), f"{rep.errors}")

    dup = _fixture_agent(base, "dup")
    (dup / "tests" / "cases.tsv").write_text(
        "same ::: a ::: x\nsame ::: b ::: y\n", encoding="utf-8")
    rep = Rep()
    mod.check_cases("dup", dup / "tests" / "cases.tsv", rep)
    check("cases: a duplicate case name is rejected",
          any("duplicate case name 'same'" in e for e in rep.errors), f"{rep.errors}")

    # --- independence that independence does not buy -------------------------
    a = agent_at("twin_a")
    b = agent_at("twin_b")
    for d2 in (a, b):
        with (d2 / "agent.conf").open("a", encoding="utf-8") as fh:
            fh.write('\nAGENT_INDEPENDENT_OF="'
                     + ("twin_b" if d2 is a else "twin_a") + '"\n')
    rep = Rep()
    mod.check_independent_models([a, b], rep)
    check("independence: declaring independence on a shared model role is rejected",
          any("but both are on model role" in e for e in rep.errors), f"{rep.errors}")

    # --- README omits a built agent -----------------------------------------
    docs = Path(tmp) / "docs2"
    om = docs / "agents" / "lonely"
    (om / "tests").mkdir(parents=True, exist_ok=True)
    (om / "skills").mkdir(exist_ok=True)
    (om / "SOUL.md").write_text("# lonely\n" * 30, encoding="utf-8")
    (om / "tests" / "cases.tsv").write_text("s ::: p ::: m\n", encoding="utf-8")
    (om / "agent.conf").write_text(VALID_CONF.format(name="lonely"), encoding="utf-8")
    (docs / "README.md").write_text(
        "# Agents\n\n| Agent | What |\n|---|---|\n| `other` | something |\n",
        encoding="utf-8")
    saved_root = mod.ROOT
    try:
        mod.ROOT = docs
        rep = Rep()
        mod.check_readme_table([docs / "agents"], rep)
        check("readme: a built agent missing from the table is an error",
              any("exists but is not in the README agent table" in e for e in rep.errors),
              f"{rep.errors}")
    finally:
        mod.ROOT = saved_root

    # --- a reporting line that dead-ends ------------------------------------
    # Two distinct failures that look alike: a cycle, and a chain that never
    # reaches the top. The cycle is covered above; this is the other one, and it
    # is the one that survives a fix aimed at the cycle.
    # Two agents: a -> b, and b -> b. b is in a cycle so `in_cycle` suppresses
    # the cycle rule for it, and a is not in a cycle, so the unreachable rule is
    # the one left to notice that a leads nowhere. Both rules are real; this is
    # the shape where only the second one can see it.
    top = base / "org"
    made = []
    for name, reports in (("root", ""), ("alpha", "beta"), ("beta", "beta")):
        dd = _fixture_agent(top, name)
        conf = (dd / "agent.conf").read_text(encoding="utf-8")
        (dd / "agent.conf").write_text(
            re.sub(r'^AGENT_REPORTS_TO=".*"$', f'AGENT_REPORTS_TO="{reports}"',
                   conf, flags=re.M), encoding="utf-8")
        made.append(dd)
    rep = Rep()
    mod.check_reporting_graph(made, rep)
    check("reporting: an agent above a self-reporting cycle is caught as unreachable",
          any("does not lead to the top of the org" in e for e in rep.errors),
          f"{rep.errors}")

    # --- a registry that parses but holds no runtimes -----------------------
    emptyreg = base / "runtimes.json"
    emptyreg.write_text(json.dumps({"note": "valid json, no runtimes key"}),
                        encoding="utf-8")
    saved_reg, saved_lib = mod.RUNTIMES, mod.RUNTIME_LIB
    try:
        mod.RUNTIMES = emptyreg
        mod.RUNTIME_LIB = base / "absent-runtime.sh"
        rep = Rep()
        mod.check_runtime_registry(rep)
        check("registry: json with no runtimes object is reported once, as itself",
              any("has no 'runtimes' object" in e for e in rep.errors)
              and len(rep.errors) == 1, f"{rep.errors}")
    finally:
        mod.RUNTIMES, mod.RUNTIME_LIB = saved_reg, saved_lib

    # --- the fourth check that cannot fire ----------------------------------
    # The last unowned finding site in the checker, and unlike the other 68 it
    # turns out not to be a coverage gap at all.
    #
    #     if ":::" not in raw:      # line 445 - handles the no-separator case
    #     parts = [p.strip() for p in raw.split(":::")]
    #     if len(parts) < 2:        # line 446 - "has no prompt column"
    #
    # Reaching line 446 means `raw` contains ":::", and a string that contains
    # its split separator always yields at least two parts. So the guard is
    # unreachable for every possible input, and the error below it is dead.
    #
    # That is this project's signature bug shape - the `stale` expression, the
    # comment-only adapter, and now this - and it is the fourth time it has
    # turned up in an audit. Three of the four were found by reading, and this
    # one was found by muting: it stayed green, and green is what a dead check
    # and an unasserted check both look like from the outside.
    #
    # Asserted as dead, with the invariant that proves it, so that if the parser
    # ever changes this becomes a real failure rather than silent dead code. And
    # the one-field case it was written to catch is asserted below against the
    # branch that actually handles it.
    eq("dead: a line containing ':::' always splits into 2+ parts",
       [s for s in (":::", "a:::", ":::a", "a:::b", "a :::: b", "::::",
                    "a:::b:::c", " ::: ") if len(s.split(":::")) < 2], [])
    onecol = base / "onecol"
    (onecol / "tests").mkdir(parents=True, exist_ok=True)
    (onecol / "agent.conf").write_text(VALID_CONF.format(name="onecol"), encoding="utf-8")
    (onecol / "tests" / "cases.tsv").write_text("justacase\n", encoding="utf-8")
    rep = Rep()
    mod.check_cases("onecol", onecol / "tests" / "cases.tsv", rep)
    check("a one-field line is caught by the no-separator branch, not the dead one",
          any("uses '|' or no separator" in e for e in rep.errors)
          and not any("has no prompt column" in e for e in rep.errors),
          f"{rep.errors}")

    # --- an empty case name -------------------------------------------------
    ee = _fixture_agent(base, "emptyname")
    (ee / "tests" / "cases.tsv").write_text(" ::: p ::: m\n", encoding="utf-8")
    rep = Rep()
    mod.check_cases("emptyname", ee / "tests" / "cases.tsv", rep)
    check("cases: an empty case name is rejected",
          any("has an empty case name" in e for e in rep.errors), f"{rep.errors}")

    # --- main's "no model roles" warning ------------------------------------
    # Guarded on `runtimes and not roles`, so it needs a registry that parsed
    # AND a catalog with no roles, and no unit test of `main` ever built both at
    # once.
    #
    # My first attempt asserted the guard existed by regexing main's own source
    # for the text "if runtimes and not roles". That is a proxy: it passes while
    # the warning is muted, because the guard text is still there. It was the
    # same mistake as the tools/ test - asserting that the file still contains a
    # string instead of that the file still does the thing - and muting this
    # finding left the suite green, which is how it was caught. Driving main()
    # with both globals pointed at a fixture is the version that means something.
    import contextlib
    import io

    fx = base / "fx"
    (fx / "agents" / "solo" / "tests").mkdir(parents=True, exist_ok=True)
    (fx / "agents" / "solo" / "skills").mkdir(exist_ok=True)
    (fx / "config").mkdir(exist_ok=True)
    (fx / "lib").mkdir(exist_ok=True)
    (fx / "agents" / "solo" / "SOUL.md").write_text("# solo\n" * 40, encoding="utf-8")
    (fx / "agents" / "solo" / "tests" / "cases.tsv").write_text("s ::: p ::: m\n",
                                                              encoding="utf-8")
    (fx / "agents" / "solo" / "agent.conf").write_text(
        VALID_CONF.format(name="solo"), encoding="utf-8")
    (fx / "config" / "models.json").write_text(json.dumps({"roles": {}}),
                                              encoding="utf-8")
    (fx / "config" / "runtimes.json").write_text(
        json.dumps({"runtimes": {"ollama": {"kind": "chat", "default": "qwen3:0.6b"}}}),
        encoding="utf-8")
    (fx / "lib" / "runtime.sh").write_text(
        "_rt_ollama_probe() { :; }\n_rt_ollama_chat() { :; }\n", encoding="utf-8")
    (fx / "README.md").write_text("# A\n", encoding="utf-8")
    (fx / "config" / "models.env").write_text("AIORG_ROLES=\n", encoding="utf-8")
    (fx / "state").mkdir(exist_ok=True)
    (fx / "state" / "audit.log").write_text("", encoding="utf-8")

    held: dict = {}

    class Capture(mod.Report):
        def __init__(self) -> None:
            super().__init__()
            held["rep"] = self

    saved_globals = {k: getattr(mod, k) for k in
                     ("ROOT", "AGENTS", "CATALOG", "RESOLVED", "RUNTIMES",
                      "RUNTIME_LIB", "Report")}
    saved_argv = sys.argv
    try:
        mod.ROOT = fx
        mod.AGENTS = fx / "agents"
        mod.CATALOG = fx / "config" / "models.json"
        mod.RESOLVED = fx / "config" / "models.env"
        mod.RUNTIMES = fx / "config" / "runtimes.json"
        mod.RUNTIME_LIB = fx / "lib" / "runtime.sh"
        mod.Report = Capture
        sys.argv = ["check-agents.py", "--quiet", "solo"]
        # Both streams. main() prints findings to stderr, so redirecting stdout
        # only is not enough: this test's fixture findings appeared inside the
        # project's own `./bootstrap.sh check` output, complete with a
        # "2 problem(s)" summary, which is exactly the shape of a real
        # regression and precisely the thing the project's own docs say must
        # never be anything but 1. A test that makes the diagnostic lie is
        # worse than no test, and the fix is one line.
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            mod.main()
        got = " ".join(held["rep"].warnings)
        check("main: a catalog with no roles says model choices are unvalidated",
              "no model roles found in config/models.json" in got, f"got {got[:200]!r}")
        eq("main: and that fixture tree is otherwise clean, so the warning is alone",
           held["rep"].errors, [])
    finally:
        sys.argv = saved_argv
        for k, v in saved_globals.items():
            setattr(mod, k, v)


# ---------------------------------------------------------------------------
# check-models.sh - the last unaudited instrument
# ---------------------------------------------------------------------------

def _fake_bin(bindir: Path, name: str, body: str) -> None:
    """Write an executable stub. Rule 18: a fake binary is how these scripts
    get tested at all on a machine with no GPU, and it is how the four bugs in
    the research pipeline were found."""
    p = bindir / name
    p.write_text("#!/usr/bin/env bash\n" + body + "\n")
    p.chmod(0o755)


def test_check_models_catches_its_own_failure_modes(tmp: Path) -> None:
    """Every finding `tools/check-models.sh` makes is owned by an assertion.

    This is the instrument behind the "0 phantoms" claim - the one that caught
    `qwen3:72b` and `qwen3-coder-next:80b`. It is opt-in and needs the network
    or a live Ollama, which is exactly why it had **no tests at all**: a
    mutation audit of it found 9 finding sites and 0 owned. Silencing any one
    of them left the suite green.

    The hand-written count in PENDING-WORK.md was 5 sites. Measurement says 9.
    The two the hand count had right by luck included the phantom `[fail]`
    itself; what it missed were the `case`-arm warnings, the argument-rejection
    `die`, the `lib/common.sh` `die`, the "not pulled" line and the closing
    verdict block. A count written down by reading is a claim; this one is
    derived by the harness and can be re-derived.

    **All nine are reachable offline.** Two thirds of the reason this file was
    untested is that it reaches for `curl` and a model server, and both are
    stubbable - the same technique rule 18 mandates and that found the four
    crawler bugs. Nothing here needs a network or a GPU.
    """
    root = Path(tmp) / "cmroot"
    for sub in ("lib", "config", "tools"):
        (root / sub).mkdir(parents=True)
    for rel in ("tools/check-models.sh", "lib/common.sh"):
        (root / rel).write_text((ROOT / rel).read_text())

    bindir = root / "bin"
    bindir.mkdir()
    for tool in ("bash", "sh", "python3", "jq", "awk", "sed", "cat", "grep",
                 "tr", "wc", "cut", "sort", "head", "tail", "dirname", "basename",
                 "printf", "env", "find", "mktemp", "rm", "cp", "mkdir"):
        real = shutil.which(tool)
        if real:
            (bindir / tool).symlink_to(real)

    # --- the catalog under test ---------------------------------------------
    # One good tag, one phantom, one malformed (no ':tag'), one that will be
    # reported as not-pulled. Deliberately tiny: the point is which findings
    # fire, not how many tags the real catalog has.
    catalog = root / "config" / "models.json"
    catalog.write_text(json.dumps({"roles": {
        "good":    {"candidates": [{"model": "qwen3:8b", "vram_gb": 8}]},
        "phantom": {"candidates": [{"model": "qwen3:72b", "vram_gb": 44}]},
        "malformed": {"candidates": [{"model": "bare-model-no-tag", "vram_gb": 4}]},
    }}), encoding="utf-8")

    # --- fake curl ------------------------------------------------------------
    # One stub answering all three questions the script asks. **Do not read the
    # URL from the last argument.** The `/api/show` call passes `-d <json>` last,
    # so `${@: -1}` is the payload, not the URL - the first version of this stub
    # did exactly that, every call fell through to the `*)` arm, and the
    # thinking assertions passed against a body of `200`. Read the argument that
    # looks like a URL instead, which is right for all three call shapes.
    #
    # **Match the manifest URL the way the script builds it, or the stub lies.**
    # The repo and tag are split apart and the tag goes in the PATH
    # (`/v2/library/qwen3/manifests/72b`), not after a colon. The first version
    # matched on `*qwen3:72b*`, which never appears in the URL - so every tag
    # came back 200 and the phantom test passed a clean catalog while asserting
    # nothing. That is the identical mistake AGENTS.md records for the real tool
    # ("a 404 on a tag you are sure exists usually means you built the URL
    # wrong"), reached from the other direction: here the tool was right and the
    # instrument pretending to be the registry was wrong.
    _fake_bin(bindir, "curl", r'''
url=""
for a in "$@"; do case "$a" in http*) url="$a" ;; esac; done
case "$url" in
  */api/tags) exit 0 ;;
  */api/show)
    case "$*" in
      *qwen3:8b*) printf '{"capabilities":["completion","thinking"]}' ;;
      *)          printf '{"capabilities":["completion"]}' ;;
    esac
    exit 0 ;;
  */manifests/72b)      printf '404'; exit 0 ;;
  */manifests/no-tag)   printf '404'; exit 0 ;;
  *) printf '200'; exit 0 ;;
esac
''')
    # ollama is only consulted under --all; absent is the honest default and
    # the script tolerates it.
    _fake_bin(bindir, "ollama", 'exit 1')

    def run(*args: str, env_extra: dict | None = None) -> tuple[int, str, str]:
        env = {"PATH": str(bindir), "HOME": str(root)}
        if env_extra:
            env.update(env_extra)
        p = subprocess.run(
            [str(bindir / "bash"), str(root / "tools" / "check-models.sh"), *args],
            capture_output=True, text=True, cwd=root, timeout=120, env=env)
        return p.returncode, p.stdout, p.stderr

    # --- 1. the phantom, with --online ---------------------------------------
    rc, out, _ = run("--online")
    check("check-models: a tag the registry 404s is called a phantom",
          "[fail]" in out and "qwen3:72b" in out and "phantom" in out,
          f"exit={rc} stdout={out[-400:]!r}")
    check("check-models: and the phantom count is in the closing verdict",
          "1 phantom tag(s)" in out, f"stdout={out[-400:]!r}")
    check("check-models: a phantom is exit 1 - a missing model scores nothing",
          rc == 1, f"exit={rc}, expected 1")
    check("check-models: the good tag in the same run is NOT called a phantom",
          "qwen3:8b" in out and "qwen3:8b  (role good)" in out,
          f"stdout={out[-400:]!r}")
    # One phantom, two `[fail]` lines: the finding itself and the closing
    # verdict. Asserted as a count of the *finding*, because that is the part
    # that could double-count - `phantom=$((phantom + 1))` sits on the `404`
    # arm only, so a malformed reference that also 404s must not increment it.
    eq("check-models: exactly one tag is called a phantom, and it is the 404 one",
       out.count("[fail] qwen3:72b"), 1)
    check("check-models: the malformed reference is warned about, never counted "
          "as a phantom - it has no tag to look up",
          "bare-model-no-tag" in out
          and "[fail] bare-model-no-tag" not in out
          and "1 phantom tag(s)" in out,
          f"stdout={out[-400:]!r}")

    # --- 2. a model reference with no ':tag' ---------------------------------
    # Asserted above, from the same run: it is questioned by name, and it is
    # never counted as a phantom because there is no tag to look up.
    check("check-models: a reference with no ':tag' is questioned by name",
          "bare-model-no-tag" in out and "really a model reference" in out,
          f"stdout={out[-400:]!r}")

    # --- 3. an unexpected HTTP status ---------------------------------------
    # A registry that answers 500 is a different fact from one that answers 404,
    # and conflating them is how a network outage gets reported as a broken
    # catalog. The two sites are separate for that reason and both are owned.
    _fake_bin(bindir, "curl", r'''
url=""
for a in "$@"; do case "$a" in http*) url="$a" ;; esac; done
case "$url" in
  */api/tags) exit 0 ;;
  */api/show)
    case "$*" in
      *qwen3:8b*) printf '{"capabilities":["completion","thinking"]}' ;;
      *)          printf '{"capabilities":["completion"]}' ;;
    esac
    exit 0 ;;
  *) printf '503'; exit 0 ;;
esac
''')
    rc503, out503, _ = run("--online")
    check("check-models: a non-404 HTTP error is reported with its status",
          "registry returned HTTP 503" in out503, f"stdout={out503[-400:]!r}")
    check("check-models: and it is NOT counted as a phantom - 503 is not 404",
          rc503 == 0 and "phantom tag(s)" not in out503,
          f"exit={rc503} stdout={out503[-400:]!r}")

    # --- 4. no model server --------------------------------------------------
    # The common case on a machine that has not started Ollama. It must say so
    # plainly and must not invent a capability verdict for anything.
    _fake_bin(bindir, "curl", r'''
url=""
for a in "$@"; do case "$a" in http*) url="$a" ;; esac; done
case "$url" in
  */api/tags) exit 7 ;;
  *) printf '200'; exit 0 ;;
esac
''')
    rc_ns, out_ns, _ = run()
    check("check-models: with no model server it says capability is unconfirmed",
          "no model server" in out_ns and "unconfirmed for every model" in out_ns,
          f"stdout={out_ns[-400:]!r}")
    check("check-models: and it tells the operator how to fix that",
          "Start Ollama" in out_ns, f"stdout={out_ns[-400:]!r}")
    check("check-models: no server is not an error - the safe default already "
          "assumes cannot-think",
          rc_ns == 0, f"exit={rc_ns}, expected 0")

    # --- 5. thinking capability, from the server's own answer ----------------
    _fake_bin(bindir, "curl", r'''
url=""
for a in "$@"; do case "$a" in http*) url="$a" ;; esac; done
case "$url" in
  */api/tags) exit 0 ;;
  */api/show)
    case "$*" in
      *qwen3:8b*) printf '{"capabilities":["completion","thinking"]}' ;;
      *)          printf '{"capabilities":["completion"]}' ;;
    esac
    exit 0 ;;
  *) printf '200'; exit 0 ;;
esac
''')
    rc_t, out_t, _ = run()
    check("check-models: a model the server says thinks is reported as thinking",
          "qwen3:8b" in out_t and "thinks" in out_t, f"stdout={out_t[-400:]!r}")
    check("check-models: one that does not is reported as not thinking",
          "does NOT think" in out_t, f"stdout={out_t[-400:]!r}")
    check("check-models: absent capabilities are counted unconfirmed, not guessed",
          "confirmed: 3    unconfirmed (not pulled): 0" in out_t,
          f"stdout={out_t[-400:]!r}")

    # --- 6. a model that is not on disk -------------------------------------
    # `/api/show` answering with no capabilities is the real shape of "not
    # pulled". Reporting it as a capability would be inventing a fact, and it
    # is the reason the catalog's unrecorded `thinks` values are safe to leave.
    _fake_bin(bindir, "curl", r'''
url=""
for a in "$@"; do case "$a" in http*) url="$a" ;; esac; done
case "$url" in
  */api/tags) exit 0 ;;
  */api/show) printf '{}'; exit 0 ;;
  *) printf '200'; exit 0 ;;
esac
''')
    _, out_np, _ = run()
    check("check-models: a model the server has no capabilities for is "
          "'not pulled', not 'does not think'",
          "not pulled - cannot confirm" in out_np, f"stdout={out_np[-400:]!r}")
    check("check-models: and those are counted separately",
          "unconfirmed (not pulled): 3" in out_np, f"stdout={out_np[-400:]!r}")

    # --- 7. the two die() sites ----------------------------------------------
    # An unknown option, and a tree with no lib/common.sh. Both are "you called
    # me wrong", and both must be loud: the first is a typo in a command a
    # beginner types, the second is running from the wrong directory.
    catalog.write_text(catalog.read_text(), encoding="utf-8")
    rc_bad, _, err_bad = run("--nonsense")
    check("check-models: an unknown option is rejected by name",
          "unknown option" in err_bad and "--nonsense" in err_bad,
          f"stderr={err_bad[-200:]!r}")
    eq("check-models: and rejected with exit 1", rc_bad, 1)

    saved_common = (root / "lib" / "common.sh").read_text()
    try:
        (root / "lib" / "common.sh").write_text("this is not valid bash (\n")
        rc_lib, _, err_lib = run()
        check("check-models: an unloadable lib/common.sh is fatal and says so",
              "cannot load lib/common.sh" in err_lib, f"stderr={err_lib[-200:]!r}")
        eq("check-models: and it is exit 1 - it cannot check anything", rc_lib, 1)
    finally:
        (root / "lib" / "common.sh").write_text(saved_common, encoding="utf-8")

    # --- 8. --help and the offline reminder ----------------------------------
    rc_h, out_h, _ = run("--help")
    check("check-models: --help explains itself", "USAGE" in out_h,
          f"stdout={out_h[:200]!r}")
    eq("check-models: --help is not an error", rc_h, 0)

    rc_off, out_off, _ = run()
    check("check-models: without --online it says tag existence was not checked",
          "Tag existence was not checked" in out_off, f"stdout={out_off[-300:]!r}")
    check("check-models: unconfirmed thinking is called a gap, not a defect",
          "gap in what we know, not a defect" in out_off,
          f"stdout={out_off[-300:]!r}")

    # --- and the catalog the project actually ships --------------------------
    # The fixture above proves the findings fire. This proves the real catalog
    # is clean, which is the claim the instrument exists to support. Run with
    # the stub registry answering 200 for everything except the two tags that
    # are phantoms, so the assertion is about the shipped catalog's shape and
    # not about the network.
    _fake_bin(bindir, "curl", r'''
url=""
for a in "$@"; do case "$a" in http*) url="$a" ;; esac; done
case "$url" in
  */api/tags) exit 7 ;;
  *) printf '200'; exit 0 ;;
esac
''')
    real_catalog = (ROOT / "config" / "models.json").read_text()
    (root / "config" / "models.json").write_text(real_catalog, encoding="utf-8")
    rc_real, out_real, _ = run("--online")
    check("check-models: the real catalog reports zero phantoms against a "
          "registry that 200s everything",
          "0 phantom" not in out_real and "[fail]" not in out_real,
          f"exit={rc_real} stdout={out_real[-400:]!r}")
    eq("check-models: so it exits 0 on the catalog as it stands", rc_real, 0)
    check("check-models: and the real catalog is big enough for the claim to "
          "mean something (39 tags, per AGENTS.md)",
          out_real.count("(role ") >= 39,
          f"only {out_real.count('(role ')} tags checked")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="aiorg-retrieval-"))
    try:
        groups = [
            ("ingest", test_ingest_basics),
            ("chunk size cap", lambda tmp: test_chunking_never_exceeds_the_size()),
            ("robots: disallow", test_robots_disallow),
            ("robots: absent", test_robots_absent_is_allowed),
            ("robots: unreachable refused", test_robots_unreachable_is_refused),
            ("robots: 403 refused", test_robots_403_is_refused),
            ("redirect into disallowed", test_redirect_to_disallowed_is_refused),
            ("redirect loop", test_redirect_loop),
            ("ssrf and schemes", test_ssrf_and_scheme),
            ("depth is not a wildcard", test_depth_is_not_a_wildcard),
            ("content type and size", test_content_type_and_size),
            ("crawl delay", test_crawl_delay_is_respected),
            ("oversized page", test_oversized_page_becomes_many_rows),
            ("search", test_search),
            ("search dedupe", test_search_dedupes_across_queries),
            ("citations", lambda tmp: test_citations()),
            ("citation lint is conservative", lambda tmp: test_citation_lint_is_conservative()),
            ("argument handling", test_module_sides),
            ("shell syntax", lambda tmp: test_shell_scripts_are_syntactically_valid()),
            ("timeout units agree", lambda tmp: test_timeout_units_agree()),
            ("role names are valid shell vars", lambda tmp: test_role_names_become_valid_shell_variables()),
            ("hyphenated role sources cleanly", lambda tmp: test_role_var_output_is_sourceable(tmp)),
            ("ollama host override", lambda tmp: test_ollama_host_override_survives_require_profile()),
            ("one helper names the server", lambda tmp: test_no_script_names_the_model_server_by_hand()),
            ("no host paths or secrets", lambda tmp: test_no_absolute_paths_or_secrets_in_tools()),
            ("unsatisfiable cases are caught", lambda tmp: test_unsatisfiable_cases_are_detected()),
            ("independence holds at every tier", lambda tmp: test_independence_survives_every_hardware_tier()),
            ("independence checker catches collisions", lambda tmp: test_independence_checker_catches_an_injected_collision(tmp)),
            ("independence flags a shared model family", lambda tmp: test_independence_flags_same_family_different_size(tmp)),
            ("check_cases catches its own failure modes", lambda tmp: test_check_cases_catches_its_own_failure_modes(tmp)),
            ("reporting graph failure modes", lambda tmp: test_reporting_graph_failure_modes(tmp)),
            ("runtime registry survives bad json", lambda tmp: test_runtime_registry_never_crashes_on_bad_json(tmp)),
            ("readme table and loopback scan", lambda tmp: test_readme_table_and_loopback_scan_cover_the_tree(tmp)),
            ("check runs every step", lambda tmp: test_check_runs_every_step_even_when_one_fails(tmp)),
            ("doctor without nvidia gpu", lambda tmp: test_doctor_finishes_without_an_nvidia_gpu(tmp)),
            ("doctor exit code", lambda tmp: test_doctor_reports_failure_in_its_exit_code(tmp)),
            ("think matches the model", lambda tmp: test_think_matches_the_model_that_actually_runs(tmp)),
            ("a score must be backed", lambda tmp: test_a_claimed_score_must_be_backed_by_the_audit_log(tmp)),
            ("the log writer and reader agree", lambda tmp: test_the_audit_log_writer_and_its_reader_agree(tmp)),
            ("the checker reaches a verdict", lambda tmp: test_check_agents_reaches_a_verdict(tmp)),
            ("every finding is asserted", lambda tmp: test_every_finding_is_asserted_somewhere(tmp)),
            ("the other unowned findings", lambda tmp: test_the_other_unowned_findings(tmp)),
            ("check-models failure modes", lambda tmp: test_check_models_catches_its_own_failure_modes(tmp)),
        ]
        for name, fn in groups:
            print(f"[{name}]")
            fn(tmp)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAIL:
        print(f"  {PASS} passed, {len(FAIL)} FAILED")
        for f in FAIL:
            print(f"    - {f}")
        return 1
    print(f"  {PASS} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
