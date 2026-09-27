#!/usr/bin/env python3
"""Search the research index built by `tools/ingest.py`.

Returns chunks with the provenance needed to cite them: source URL, page title,
and the moment it was fetched. That is not decoration. A research agent is asked
to say where a claim came from, and it can only do that if the source is carried
in the data - asking a model to remember which of several passages a claim came
from is asking it to guess, and a confident guess with a plausible URL attached
is the exact failure this whole department exists to avoid.

## This is lexical retrieval, and it is the honest limit

SQLite FTS5 ranks with BM25 over words. It has no idea what anything *means*, so
a query using different words from the source finds nothing. "How do I stop the
disk filling up" will miss a page that says "retention policy" and never uses
the word "disk".

That is a real weakness, not a rounding error, and it is why the research
agents are told to report an empty result as an empty result rather than filling
the gap from memory. Semantic retrieval is the fix and it is not built yet: there
is no embedding model in `config/models.json` that this machine can run, and
shipping a vector store over an empty index would be a very good way to appear
finished.

Usage:
    search.py "backup retention policy" --k 5
    search.py --sources                  # what is actually in the index
    search.py "chunking provenance" --json
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = "state/research/index.db"


def build_match(query: str) -> str:
    """Turn free text into a safe FTS5 MATCH expression.

    FTS5 has its own query language: bare AND/OR/NOT/NEAR are operators, a
    double quote opens a phrase, and a stray `-` or `*` is a syntax error. Hand a
    researcher's question straight to MATCH and it throws - so a query that
    happens to contain the word "not" would fail on punctuation rather than
    returning results, which reads as "nothing found" and quietly poisons the
    agent's confidence in the whole index.

    So: quoted phrases in the input stay phrases, everything else becomes a
    double-quoted term, and the terms are OR'd. OR rather than AND because this
    is recall-first - BM25 does the ranking, and a conjunction would silently
    return nothing whenever one word in the question is absent from the source.
    """
    phrases = re.findall(r'"([^"]+)"', query)
    rest = re.sub(r'"[^"]*"', " ", query)
    terms = [t for t in re.findall(r"[\w']+", rest, flags=re.UNICODE) if t]

    parts = [f'"{p.strip()}"' for p in phrases if p.strip()]
    parts += [f'"{t}"' for t in terms]
    if not parts:
        return ""
    return " OR ".join(parts)


def connect(db: Path) -> sqlite3.Connection:
    if not db.exists():
        print(f"No index at {db}. Build one with tools/ingest.py first.",
              file=sys.stderr)
        raise SystemExit(2)
    return sqlite3.connect(db)


def age(fetched_at: str) -> str:
    """How old the source is, in words a model can reason about.

    Freshness is part of provenance. A 2023 blog post answering a 2026 question
    is not wrong, but the reader has to be able to see that.
    """
    try:
        when = datetime.fromisoformat(fetched_at)
    except ValueError:
        return fetched_at
    days = (datetime.now(timezone.utc) - when).days
    if days < 1:
        return "fetched today"
    if days < 31:
        return f"fetched {days}d ago"
    if days < 365:
        return f"fetched {days // 30}mo ago"
    return f"fetched {days // 365}y ago"


def search(conn: sqlite3.Connection, query: str, k: int) -> list[dict]:
    match = build_match(query)
    if not match:
        return []
    try:
        rows = conn.execute(
            "SELECT c.url, c.title, c.fetched_at, c.chunk_index, c.text,"
            "       bm25(chunks_fts, 2.0, 1.0) AS score"
            "  FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid"
            " WHERE chunks_fts MATCH ?"
            " ORDER BY score LIMIT ?", (match, k)).fetchall()
    except sqlite3.OperationalError as e:
        print(f"FTS query failed ({e}); treating as no results.", file=sys.stderr)
        return []

    out = []
    for url, title, fetched, idx, text, score in rows:
        out.append({
            "url": url,
            "title": title or "(no title)",
            "fetched_at": fetched,
            "freshness": age(fetched),
            "chunk": idx,
            "text": text.strip(),
            "score": round(-score, 3),      # bm25() is better when lower; flip it
        })
    return out


def evidence(conn: sqlite3.Connection, queries: list[str], k: int) -> int:
    """Emit a citation-numbered evidence block for one or more queries.

    Chunks are de-duplicated across queries, so a passage that answers two of
    the questions appears once and gets one number. A block containing the same
    text under three numbers teaches the agent to cite the same source three
    times, which looks like corroboration and is not.
    """
    seen: set[tuple] = set()
    picked: list[dict] = []
    for q in queries:
        for h in search(conn, q, k):
            key = (h["url"], h["chunk"])
            if key in seen:
                continue
            seen.add(key)
            picked.append(h)

    if not picked:
        print("[SOURCES]")
        print("(none - nothing in the index matches these queries)")
        return 1

    print("[SOURCES]")
    for i, h in enumerate(picked, 1):
        print(f"[{i}] {h['title']} - {h['url']} ({h['freshness']})")
        body = h["text"]
        if len(body) > 900:
            body = body[:900].rsplit(" ", 1)[0] + " ..."
        for line in body.splitlines():
            print(f"    {line}")
        print()
    print(f"({len(picked)} chunk(s) from "
          f"{len({h['url'] for h in picked})} page(s). "
          f"These are the only sources you have. If they do not answer the "
          f"question, say so - do not fill the gap from memory.)")
    return 0


def show_sources(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        "SELECT url, title, fetched_at, n_chunks FROM pages ORDER BY url").fetchall()
    if not rows:
        print("The index is empty - nothing has been ingested yet.")
        return 0
    total = sum(r[3] for r in rows)
    print(f"{len(rows)} page(s), {total} chunk(s) in the index\n")
    for url, title, fetched, n in rows:
        print(f"  {n:3d} chunk(s)  {title or '(untitled)'}")
        print(f"              {url}  ({age(fetched)})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Search the research index.")
    ap.add_argument("query", nargs="*", help="search terms; wrap a phrase in \"quotes\"")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--k", type=int, default=5, help="max chunks (default 5)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--sources", action="store_true", help="list what is indexed")
    ap.add_argument("--evidence", action="store_true",
                    help="emit a citation-numbered evidence block for every query")
    args = ap.parse_args()

    conn = connect(Path(args.db))

    if args.sources:
        return show_sources(conn)

    query = " ".join(args.query).strip()
    if not query:
        ap.error("give a query, or --sources to list what is indexed")

    if args.evidence:
        # Every argument is its own query, not one long OR - that is what lets a
        # question be researched from several angles without the angles
        # diluting each other.
        return evidence(conn, args.query, args.k)

    hits = search(conn, query, args.k)

    if args.json:
        print(json.dumps({"query": query, "hits": hits}, indent=2))
        return 0 if hits else 1

    if not hits:
        # Said plainly, and said as a fact about the index rather than about the
        # world. "Nothing found" means nothing in the index matched - not that
        # nothing exists. The agent is told to pass that distinction on.
        print(f"No indexed source matches {query!r}.")
        print("That is a fact about the index, not about the world - the page may "
              "never have been ingested, or may use different words.")
        return 1

    print(f"{len(hits)} chunk(s) for {query!r}\n")
    for i, h in enumerate(hits, 1):
        print(f"[{i}] {h['title']}")
        print(f"    {h['url']}")
        print(f"    {h['freshness']}  (chunk {h['chunk']}, relevance {h['score']})")
        body = h["text"]
        if len(body) > 600:
            body = body[:600].rsplit(" ", 1)[0] + " ..."
        for line in body.splitlines():
            print(f"    | {line}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
