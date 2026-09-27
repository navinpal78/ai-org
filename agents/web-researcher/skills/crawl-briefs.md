# Writing a crawl brief

You do not crawl. `tools/ingest.py` does, and your job is to write the brief that
tells it what to collect - and, more importantly, what not to.

    SEEDS:    https://example.com/docs/
    DEPTH:    1          # the given pages only; 2 follows links
    LIMIT:    25         # pages, not requests
    DELAY:    1.0        # seconds per host; raise it for a small site
    EXCLUDE:  /login, /admin, /pricing, /user/
    REASON:   public documentation, indexed for tech-researcher

## Depth is the most dangerous parameter

`--depth 2` follows every link on a page. On a documentation site that is
reasonable. On a site with a calendar, or a tag cloud, or a comments section, it
walks into a very large part of somebody's server.

Start at depth 1. Expand deliberately, and say why each expansion is worth it.

## Exclude before you include

List the paths you do not want. `/admin`, `/login`, `/account`, `/user/`,
`/comment`, `/tag`, `/search`, `/cart`, `/checkout`. The ingester stays on the
host you gave it, but on a large site that is still a great deal of somebody's
pages, and none of them are what you are researching.

## Limits are politeness, not safety

`--limit` and `--delay` exist because the site is somebody else's machine. A
crawl that would be visible in their logs is the wrong crawl even where
robots.txt permits it. If the site looks small or personal, say so and slow
down further.

## What to write for each seed

- Why this source, and what question it is meant to answer.
- What a good outcome looks like, so the ingester's output can be judged.
- What you already suspect, so a null result is recognisable as informative.

## When to recommend against a crawl

- The content is behind a login, a paywall, or a `robots.txt` disallow.
- It is about identifiable people: profiles, comments, forums, anything personal.
- The site's terms prohibit automated collection and robots.txt is silent.
- The volume is large and the question could be answered from a handful of pages.

In each case, say what you would do instead. There is almost always a smaller
legitimate source.
