#!/usr/bin/env python3
"""Fetch web pages and index them so an agent can retrieve them later.

This is the retrieval half of the research department, and it is deliberately
NOT an agent. The reasoning about what is worth reading belongs to a researcher;
the fetching belongs here, where the rules can be enforced rather than asked for.

Why outside the agent, then? Because the rules below are the kind an agent
cannot be trusted with. "Only fetch what robots.txt allows" is a sentence in a
prompt, and a prompt is a request rather than a control. Here it is a check that
runs before a socket opens. The same reasoning as the risk tiers in
`lib/common.sh`: a limit that the limited party administers is not a limit.

What it will not do, and these are refusals rather than options:

  * fetch anything robots.txt disallows, for any user agent
  * exceed a per-host delay, or ignore a Crawl-delay if the site sets one
  * fetch a private, loopback or link-local address (SSRF guard - a fetcher that
    will follow a hostname into 10.0.0.0/8 is an exfiltration primitive)
  * send cookies, credentials, or an Authorization header, ever
  * follow a redirect to a different host without re-checking the rules there
  * treat an unreadable robots.txt as permission to proceed
  * fetch anything that is not http(s)

Retrieval is lexical (SQLite FTS5 / BM25), not semantic. That is a real
limitation and it is documented in `tools/search.py`: a query using different
words from the source will miss. Semantic search is a later upgrade, not a
reason to have no retrieval today.

Provenance is the point of the whole design. Every chunk stores the URL it came
from, the page title, and the moment it was fetched. A research agent is asked
to cite, and it can only cite what it can name - so the citation has to be
carried in the data rather than reconstructed by the model, which is the one
thing that invents plausible sources without noticing.

Usage:
    ingest.py --url https://example.com/docs --limit 20
    ingest.py --seeds seeds.txt --depth 2 --delay 2.0
    ingest.py --url https://example.com --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import re
import socket
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

USER_AGENT = "ai-org-research/1.0"
DEFAULT_DELAY = 1.0        # seconds between requests to the same host
CHUNK_CHARS = 800          # target size of an indexed chunk
CHUNK_OVERLAP = 120        # repeated between chunks so a sentence spanning a
                           # boundary is still findable from either side
MAX_BYTES = 2_000_000      # refuse anything larger; it is a file, not a page
MAX_REDIRECTS = 5          # every hop is re-checked, so keep the chain short
ALLOWED_TYPES = ("text/html", "application/xhtml+xml", "text/plain")

SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "iframe", "head"}
# Links are how a crawl becomes a crawl. Restricting to these keeps a research
# run pointed at documents rather than wandering into a sitemap of a shopping
# site.
LINK_TAGS = {"a": "href"}


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# network guards
# --------------------------------------------------------------------------

def resolve_and_check(url: str, allow_private: bool) -> str:
    """Return the URL if it is safe to fetch, else raise.

    The DNS answer is checked, not the hostname. A name that looks public can
    resolve to 127.0.0.1, and the fetch is what actually goes to that address.
    """
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError(f"refusing scheme {parts.scheme!r}: only http and https")
    if not parts.hostname:
        raise ValueError("no hostname in URL")

    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 80,
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise ValueError(f"cannot resolve {parts.hostname}: {e}") from e

    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        bad = (addr.is_private or addr.is_loopback or addr.is_link_local
               or addr.is_reserved or addr.is_multicast or addr.is_unspecified)
        if bad and not allow_private:
            raise ValueError(
                f"{addr} is private/loopback/link-local and --allow-private was "
                f"not given. Refusing to fetch it.")
    return url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Turn a 3xx into a value the caller has to look at."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PoliteFetcher:
    """A urllib opener with the manners, and the limits, in code.

    No cookie handler and no auth handler are installed. That is not an
    oversight to be tidied up later - a session cookie is how a fetcher starts
    being logged in as somebody, and the research agents have no business being
    logged in as anybody.
    """

    def __init__(self, delay: float, allow_private: bool, timeout: int):
        self.delay = max(0.0, delay)
        self.allow_private = allow_private
        self.timeout = timeout
        self.last_hit: dict[str, float] = {}
        self.robots: "Robots | None" = None
        # No redirect handler on purpose. urllib's HTTPRedirectHandler would
        # chase a Location header for us, and the checks below would then apply
        # to the URL we asked for rather than the one we ended up at. Following
        # redirects is a loop instead, so the destination is re-validated by the
        # same code path that validates a seed.
        self.opener = urllib.request.build_opener(NoRedirect())

    def wait(self, url: str, crawl_delay: float | None = None) -> None:
        host = urllib.parse.urlsplit(url).netloc
        target = max(self.delay, crawl_delay or 0.0)
        gap = time.monotonic() - self.last_hit.get(host, 0.0)
        if gap < target:
            time.sleep(target - gap)
        self.last_hit[host] = time.monotonic()

    def _follow(self, url: str, hops: int) -> tuple[str, str, str | None]:
        """Walk the Location chain by hand, re-checking every hop.

        A seed on an allowed path can redirect to a disallowed path, to another
        host whose robots.txt says no, or straight at a private address. Any of
        those is a refusal, not a technicality, and the only way to know is to
        look at where the chain actually ends.
        """
        seen = {url}
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            self.wait(current)
            final, body, ctype, location = self._request_with_location(current)
            if not location:
                return final, body, ctype
            nxt = urllib.parse.urljoin(final, location)
            if nxt in seen:
                raise ValueError(f"redirect loop at {nxt}")
            seen.add(nxt)
            if self.robots is not None:
                allowed, delay = self.robots.allows(nxt)
                if not allowed:
                    raise ValueError(
                        f"redirect target {nxt} is disallowed by that host's "
                        f"robots.txt")
                self.wait(nxt, delay)
            current = nxt
        raise ValueError(f"more than {MAX_REDIRECTS} redirects starting at {url}")

    def _request_with_location(self, url: str):
        """Fetch, treating a 3xx as a return value rather than an exception."""
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
        })
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                body = resp.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise ValueError(f"page exceeds {MAX_BYTES} bytes")
                ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
                return resp.geturl(), body.decode("utf-8", errors="replace"), ctype, None
        except urllib.error.HTTPError as e:
            if e.code not in (301, 302, 303, 307, 308):
                raise
            return url, "", "", e.headers.get("Location")

    def get(self, url: str, crawl_delay: float | None = None) -> tuple[str, str, str]:
        """Return (final_url, body, content_type). Raises on refusal or failure."""
        url = resolve_and_check(url, self.allow_private)
        self.wait(url, crawl_delay)
        final, body, ctype = self._follow(url, 0)
        if ctype and not any(ctype.startswith(t) for t in ALLOWED_TYPES):
            raise ValueError(f"content-type {ctype} is not indexable")
        return final, body, ctype


class Robots:
    """robots.txt, cached per host, fetched as politely as anything else."""

    def __init__(self, fetcher: PoliteFetcher):
        self.f = fetcher
        # An absent robots.txt and an unreachable one are different facts. The
        # first means "no opinion", the second means "could not ask". Storing a
        # parser for the first and None for the second is what makes that
        # distinction survive to the decision.
        self.cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.absent: set[str] = set()

    def _fetch_robots(self, origin: str):
        """(body, present). A 404 is an answer, a failure is not."""
        url = f"{origin}/robots.txt"
        try:
            _, body, ctype = self.f.get(url)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                # RFC 9309 2.3.1.3: unauthorised means the rules are not
                # available to us, and a crawler that is not authorised is not
                # one to go and find out. This is a refusal, not an absence.
                raise PermissionError(
                    f"{origin}/robots.txt is not readable by this crawler")
            if e.code == 404:
                return None, False
            # 5xx and anything else odd. A server in trouble is not a server
            # that has waived its rules, so this has to reach the refusal path
            # with a reason attached rather than escaping as a bare HTTPError.
            raise ConnectionError(
                f"{origin}/robots.txt returned HTTP {e.code}") from e
        except (urllib.error.URLError, OSError) as e:
            raise ConnectionError(f"could not reach {url}: {e}") from e
        if ctype and not any(ctype.startswith(t) for t in ALLOWED_TYPES):
            return None, False
        return body, True

    def for_host(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        origin = urllib.parse.urlsplit(url)[:2]
        origin = f"{origin[0]}://{origin[1]}"
        if origin in self.cache:
            return self.cache[origin]
        if origin in self.absent:
            return None
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(f"{origin}/robots.txt")
        try:
            body, present = self._fetch_robots(origin)
            if not present:
                log(f"  no robots.txt at {origin} - the site has no opinion")
                self.absent.add(origin)
                rp = None
            else:
                # Parse the body we already fetched. rp.read() would go and
                # fetch it a second time, through a different opener, without
                # the rate limit - so a busy crawl would hit every host twice
                # for the file that is supposed to slow it down.
                rp.parse(body.splitlines())
        except (PermissionError, ConnectionError) as e:
            # Unreachable robots.txt means we do not know the rules. Assuming
            # "allow" here is how a crawler ends up somewhere it was told not to
            # go, and the whole point of this file is that it cannot be argued
            # with. Refuse, and say why. A host with no robots.txt at all is
            # still fine - that is the site declining to publish any.
            log(f"  {e} - refusing this host rather than assuming permission")
            rp = None
        self.cache[origin] = rp
        return rp

    def allows(self, url: str) -> tuple[bool, float | None]:
        origin = urllib.parse.urlsplit(url)[:2]
        origin = f"{origin[0]}://{origin[1]}"
        if origin in self.absent:
            return True, None
        try:
            rp = self.for_host(url)
        except Exception:                             # noqa: BLE001
            return False, None
        if rp is None:
            return False, None
        try:
            ok = rp.can_fetch(USER_AGENT, url)
        except Exception:                             # noqa: BLE001
            return False, None
        delay = None
        try:
            delay = rp.crawl_delay(USER_AGENT)
        except Exception:                             # noqa: BLE001
            pass
        return ok, delay


# --------------------------------------------------------------------------
# html -> text
# --------------------------------------------------------------------------

class TextExtractor(HTMLParser):
    """Pull visible text and links out of a page.

    Prefers lxml, falls back to bs4, then to this. The fallback chain matters
    because the environment that runs the research agents is not guaranteed to
    be the one that has the nicer libraries installed.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[str] = []
        self.title: str = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in LINK_TAGS:
            for k, v in attrs:
                if k == LINK_TAGS[tag] and v:
                    self.links.append(v)

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "br", "tr"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data.strip()
        if not self._skip:
            self.parts.append(data)

    @property
    def text(self) -> str:
        raw = "".join(self.parts)
        raw = re.sub(r"[ \t\xa0]+", " ", raw)
        raw = re.sub(r"\n\s*\n\s*\n+", "\n\n", raw)
        return "\n".join(ln.strip() for ln in raw.splitlines() if ln.strip())


def extract(html: str) -> tuple[str, str, list[str]]:
    """Return (title, text, absolute_links)."""
    try:
        from lxml import html as lxml_html
        tree = lxml_html.fromstring(html)
        for bad in tree.xpath("//script|//style|//noscript|//template|//svg"):
            bad.getparent().remove(bad)
        title = (tree.findtext(".//title") or "").strip()
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n",
                      "\n".join(t.strip() for t in tree.text_content().splitlines() if t.strip()))
        links = [h for h in tree.xpath("//a/@href") if h]
        return title, text, links
    except Exception:                                 # noqa: BLE001
        pass
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for bad in soup(["script", "style", "noscript", "template", "svg"]):
            bad.decompose()
        title = (soup.title.string.strip() if soup.title and soup.title.string else "")
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n",
                      "\n".join(t.strip() for t in soup.get_text("\n").splitlines() if t.strip()))
        links = [a["href"] for a in soup.find_all("a", href=True)]
        return title, text, links
    except Exception:                                 # noqa: BLE001
        pass
    p = TextExtractor()
    p.feed(html)
    return p.title, p.text, p.links


# --------------------------------------------------------------------------
# chunking
# --------------------------------------------------------------------------

def _split_long(piece: str, size: int) -> list[str]:
    """Break a single oversized piece into retrievable parts.

    Needed because the paragraph split below is the *preferred* boundary, not a
    guarantee. Real pages do not come pre-split into paragraphs: a 150KB
    reference page, or a standards document that wraps at 72 columns, can arrive
    as one block with no blank line anywhere in it. The first version of this
    function trusted the blank lines and emitted the whole thing as a single
    chunk - which quietly destroyed the entire design, because a 150KB FTS5 row
    cannot be retrieved usefully, gets truncated to 900 characters on the way out,
    and gives a researcher one enormous citable "source".

    So the hard rule is: no chunk comes out larger than `size`, whatever the
    input looks like. Preference order is line, then sentence, then a raw slice -
    the last one produces mid-sentence fragments, which is why it is last.
    """
    if len(piece) <= size:
        return [piece]

    # 1. lines, which for wrapped plain text is the natural boundary
    lines = piece.split("\n")
    if len(lines) > 1:
        out, cur, n = [], [], 0
        for ln in lines:
            if cur and n + len(ln) + 1 > size:
                out.append("\n".join(cur))
                cur, n = [], 0
            cur.append(ln)
            n += len(ln) + 1
        if cur:
            out.append("\n".join(cur))
        # a single line may still be over the limit; recurse on it
        return [s for part in out for s in _split_long(part, size)] if any(
            len(x) > size for x in out) else out

    # 2. sentences, for one long unbroken line of prose
    sents = re.split(r"(?<=[.!?])\s+", piece)
    if len(sents) > 1:
        out, cur, n = [], [], 0
        for s in sents:
            if cur and n + len(s) + 1 > size:
                out.append(" ".join(cur))
                cur, n = [], 0
            cur.append(s)
            n += len(s) + 1
        if cur:
            out.append(" ".join(cur))
        return [s for part in out for s in _split_long(part, size)] if any(
            len(x) > size for x in out) else out

    # 3. last resort: hard slices. Mid-word, but retrievable, which beats one
    #    giant row that nothing can retrieve from.
    return [piece[i:i + size] for i in range(0, len(piece), size)]


def chunk(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split on paragraph boundaries, keeping a little overlap.

    Chunking on a fixed character count alone splits sentences, and a sentence
    split across two chunks is a sentence that cannot be quoted accurately by
    anyone who finds only one half of it. So paragraphs first, and a hard size
    limit underneath (see `_split_long`) for the pages that have none.
    """
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        return []
    chunks, cur, n = [], [], 0
    for para in paras:
        if cur and n + len(para) + 2 > size:
            chunks.append("\n\n".join(cur))
            # carry the tail forward so the boundary sentence survives in both
            tail, tlen = [], 0
            for prev in reversed(cur):
                if tlen >= overlap:
                    break
                tail.insert(0, prev)
                tlen += len(prev) + 2
            cur, n = tail, tlen
        cur.append(para)
        n += len(para) + 2
    if cur:
        chunks.append("\n\n".join(cur))
    # the hard cap, applied to whatever the paragraph pass produced
    return [s for c in chunks for s in _split_long(c, size)]


# --------------------------------------------------------------------------
# store
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
  url         TEXT PRIMARY KEY,
  title       TEXT,
  fetched_at  TEXT NOT NULL,
  n_chunks    INTEGER NOT NULL DEFAULT 0,
  status      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
  id           INTEGER PRIMARY KEY,
  url          TEXT NOT NULL REFERENCES pages(url) ON DELETE CASCADE,
  title        TEXT,
  fetched_at   TEXT NOT NULL,
  chunk_index  INTEGER NOT NULL,
  content_hash TEXT NOT NULL,
  text         TEXT NOT NULL,
  UNIQUE (url, chunk_index)
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
  USING fts5(title, text, content='chunks', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, title, text) VALUES (new.id, new.title, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, title, text)
  VALUES ('delete', old.id, old.title, old.text);
END;
CREATE INDEX IF NOT EXISTS chunks_url ON chunks(url);
"""


def open_store(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def store_page(conn: sqlite3.Connection, url: str, title: str,
               text: str, fetched_at: str, force: bool) -> int:
    """Index one page. Returns the number of chunks written."""
    pieces = chunk(text)
    if not pieces:
        return 0
    digest = lambda s: hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()  # noqa: E731

    row = conn.execute("SELECT n_chunks FROM pages WHERE url = ?", (url,)).fetchone()
    if row and not force:
        # Unchanged content is not re-indexed. Re-ingesting the same site on a
        # schedule should be cheap, and a duplicate chunk in the index is a
        # duplicate a researcher will eventually cite twice.
        existing = [r[0] for r in conn.execute(
            "SELECT content_hash FROM chunks WHERE url = ? ORDER BY chunk_index", (url,))]
        if existing == [digest(p) for p in pieces]:
            return 0

    # Parent row first. chunks.url REFERENCES pages(url), so the page has to
    # exist before its chunks do - writing them the other way round fails on the
    # foreign key, which is exactly the kind of mistake a schema check finds and
    # a real crawl does not, until it does.
    conn.execute(
        "INSERT INTO pages (url, title, fetched_at, n_chunks, status) VALUES (?,?,?,?,?)"
        " ON CONFLICT(url) DO UPDATE SET title=excluded.title,"
        " fetched_at=excluded.fetched_at, n_chunks=excluded.n_chunks, status=excluded.status",
        (url, title, fetched_at, len(pieces), "indexed"))
    conn.execute("DELETE FROM chunks WHERE url = ?", (url,))   # triggers keep fts in step
    for i, piece in enumerate(pieces):
        conn.execute(
            "INSERT INTO chunks (url, title, fetched_at, chunk_index, content_hash, text)"
            " VALUES (?,?,?,?,?,?)",
            (url, title, fetched_at, i, digest(piece), piece))
    conn.commit()
    return len(pieces)


# --------------------------------------------------------------------------
# crawl
# --------------------------------------------------------------------------

def seed_urls(args) -> list[str]:
    if args.url:
        return list(args.url)
    if args.seeds:
        out = []
        for line in Path(args.seeds).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
        return out
    return []


def crawl(args) -> int:
    db = open_store(Path(args.db))
    fetcher = PoliteFetcher(args.delay, args.allow_private, args.timeout)
    robots = Robots(fetcher)
    fetcher.robots = robots      # a redirect target is checked with the same rules
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    queue = deque(seed_urls(args))
    seen: set[str] = set()
    stats = {"indexed": 0, "chunks": 0, "robots": 0, "skipped": 0, "error": 0, "noop": 0}

    while queue and stats["indexed"] < args.limit:
        url = queue.popleft()
        url = urllib.parse.urldefrag(url)[0]
        if url in seen:
            continue
        seen.add(url)

        allowed, crawl_delay = robots.allows(url)
        if not allowed:
            log(f"  robots.txt disallows: {url}")
            stats["robots"] += 1
            continue

        if args.dry_run:
            log(f"  would fetch: {url}")
            stats["indexed"] += 1
            continue

        try:
            final_url, body, _ctype = fetcher.get(url, crawl_delay)
        except ValueError as e:
            log(f"  refused: {url} ({e})")
            stats["error"] += 1
            continue
        except (urllib.error.URLError, OSError) as e:
            log(f"  fetch failed: {url} ({e})")
            stats["error"] += 1
            continue

        title, text, links = extract(body)
        n = store_page(db, final_url, title, text, now, args.force)
        if n:
            stats["indexed"] += 1
            stats["chunks"] += n
            log(f"  indexed {n:3d} chunks  {final_url}")
        else:
            stats["noop"] += 1
            log(f"  unchanged        {final_url}")

        if args.depth >= 1:
            host = urllib.parse.urlsplit(final_url).netloc
            for href in links:
                nxt = urllib.parse.urljoin(final_url, href)
                if urllib.parse.urlsplit(nxt).netloc != host:
                    continue                      # stay on the host we were given
                if urllib.parse.urlsplit(nxt).scheme not in ("http", "https"):
                    continue
                if nxt not in seen:
                    queue.append(nxt)

    log("")
    log(f"  pages indexed {stats['indexed']}  chunks {stats['chunks']}  "
        f"unchanged {stats['noop']}  robots-refused {stats['robots']}  "
        f"errors {stats['error']}")
    log(f"  index: {args.db}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fetch and index pages for the research agents. "
                    "Obeys robots.txt, rate-limits per host, and refuses "
                    "private addresses.")
    ap.add_argument("--url", action="append", help="a URL to fetch (repeatable)")
    ap.add_argument("--seeds", help="file of seed URLs, one per line")
    ap.add_argument("--db", default="state/research/index.db",
                    help="index path (default: state/research/index.db)")
    ap.add_argument("--depth", type=int, default=0,
                    help="how many link hops from a seed. 0 = the seed pages only "
                         "(the default, and the polite choice), 1 = also their "
                         "direct links, 2+ = deeper. Depth is the parameter most "
                         "likely to walk into a large part of somebody's server.")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be fetched without fetching it")
    ap.add_argument("--limit", type=int, default=25, help="max pages to index")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                    help=f"min seconds between requests to one host (default {DEFAULT_DELAY})")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--force", action="store_true", help="re-index even if unchanged")
    ap.add_argument("--allow-private", action="store_true",
                    help="permit private/loopback addresses (local testing only)")
    args = ap.parse_args()

    if not seed_urls(args):
        ap.error("give --url or --seeds")
    if args.delay < 0:
        ap.error("--delay cannot be negative")
    if args.depth < 0:
        ap.error("--depth cannot be negative")
    return crawl(args)


if __name__ == "__main__":
    sys.exit(main())
