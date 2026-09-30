"""Mutation audit: does a test own every finding tools/check-agents.py makes?

Run it from the project root:

    python3 tools/mutation-audit.py [--target tools/check-agents.py]

Takes about 5 minutes and mutates 69 call sites, one at a time. It splices a
no-op `_mute` method into the Report class and redirects a single
rep.error()/rep.warn() at it, so the checker keeps running and exactly one
finding disappears. The suite is then expected to go RED. A site that stays
green has no test asserting it.

    asserted (suite goes red when silenced): 68/69
    false passes: 1        <- check_cases:447, proved unreachable, asserted dead

**Use this, not name-matching and not line coverage.** Naming a function in the
test file misses helpers reached through a caller. A line tracer misses every
finding the tests provoke in a subprocess - and a line that executes while
nothing asserts its output is the same false pass as a line that never runs.

**Three traps, two of them this script already fell into and one it inherited
from itself without fixing:**

1. Do not pick a scratch directory with `idx % WORKERS`. That chooses a
   directory but not a thread, so ThreadPoolExecutor runs tasks with the same
   index class concurrently in one tree and they overwrite each other's
   mutations. The total then moves between identical runs (it did: 19, 21, 6).
   Each worker now gets a contiguous chunk and its own tree.
2. A mutation whose line window misses its target returns SKIP, and SKIP must
   NOT be counted as asserted. A mutation that never happened reported as a
   pass is the exact false-pass shape this script exists to detect.
   **This is the third trap, until 2026-09-30 it was live in this file:** the
   denominator was `len(res)` and the numerator `len(res)-len(green)`, so every
   SKIP was counted as asserted on both sides. Measured and demonstrated: one
   extra blank line inside the MUT constant - a change nothing would notice -
   shifted 56 of 69 sites out of the four-line locate window, every one of them
   came back SKIP, and the script printed a perfect
   `asserted ... 69/69, false passes: 0` while knowing, in the line above, that
   those sites had "counted for nothing". The sibling shell script had been
   fixed for exactly this under the heading "**`asserted = n - green - skips`
   counted a mutation that never ran as a pass**". The fix is the same here:
   the ratio is derived from rows that actually reported, a site with no result
   is a hard error, and a skip is reported as not asserted, not absorbed into
   the green column.
3. The locate window had **zero margin**: the MUT insertion shifts every site
   by exactly the number of lines it occupies, and 61 of 69 sites landed on the
   window's last row. Sites are now located by their AST position carried into
   the shifted text, verified by column and by a re-count, so the mutation
   lands or it is a skip - there is no window to outgrow.

The result is stable across runs. Keep it that way: if the number moves between
identical runs, the harness is broken, not the tree.

**The account is the whole point, and it is the sibling's account.** Sites that
reported RED are asserted; GREEN is a false pass; SKIP counts for nothing;
a site with no result at all is a broken harness and the script exits 2 rather
than printing a number. See tools/mutation-audit.sh, which documents the same
shape at length. If you ever see a clean number from the python harness, check
the "skipped" and "no result" lines first.
"""
import ast
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_TARGET = 'tools/check-agents.py'

MUTE_TEXT = "    def _mute(self, agent: str, msg: str) -> None:\n        return\n\n"


def is_emit(n):
    return (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr in ('error', 'warn')
            and isinstance(n.func.value, ast.Name) and n.func.value.id == 'rep')


def find_sites(source):
    """Return [(function, lineno, kind, start_col, end_lineno, end_col), ...].

    lineno/start_col/end_lineno/end_col are 1/0-based as CPython reports them,
    so the exact call text can be recovered with ast.get_source_segment even
    when the call spans lines. Derive the list; never read it off a doc.
    """
    sites = []

    def walk(node, cur):
        for n in ast.iter_child_nodes(node):
            if isinstance(n, ast.FunctionDef):
                walk(n, n.name)
            else:
                if is_emit(n) and cur:
                    sites.append((cur, n.lineno, n.func.attr,
                                  n.col_offset, n.end_lineno, n.end_col_offset))
                walk(n, cur)

    walk(ast.parse(source), None)
    return sites


def insertion_row(base_lines):
    """Return the 1-based row of the anchor the no-op is spliced in front of.

    The no-op is inserted immediately before `def error(self`, which is what
    keeps a silenced call a call rather than a crash. Absent the anchor, no
    insertion happens at all - the count check would then make every site a
    SKIP, which is correct behaviour for a target that is not check-agents.py.
    """
    for i, line in enumerate(base_lines):
        if 'def _mute(self' in line:
            return None
        if line.strip() == 'def error(self, agent: str, msg: str) -> None:':
            return i + 1
    return None


def build_mutated_text(base, mute_text=MUTE_TEXT):
    """Add the no-op reporting sibling to a copy of the target's text."""
    return base.replace("    def error(self", mute_text + "    def error(self", 1)


def mutate(base, site, mute_text=MUTE_TEXT):
    """Redirect exactly one finding at the no-op. Returns (status, text).

    status is 'landed' or 'skip'. A skip means the mutation did not land and
    the caller must NOT count it as asserted - the false-pass shape this whole
    script exists to detect.

    Location is by AST, not by a window. The no-op insertion shifts every site
    below the anchor row by exactly lenlist(mute_text) lines; a site's real
    position is node row + shift, and the column pin is the AST's own. Both are
    verified by a re-count of the muted call before the text is believed.
    """
    base_lines = base.splitlines(keepends=True)
    row = insertion_row(base_lines)
    shift = 0 if row is None else mute_text.count("\n")
    mut_lines = build_mutated_text(base, mute_text=mute_text).splitlines(keepends=True)

    func, lineno, kind, col, end_lineno, end_col = site
    target = f"rep.{kind}("
    new_index = lineno - 1 + shift
    if row is not None and lineno < row:
        new_index = lineno - 1
    if new_index >= len(mut_lines):
        return 'skip', None
    line = mut_lines[new_index]
    # the AST column pin must still point at the call on the shifted row
    if func != "" and (col < 0 or col >= len(line) or line[col:col + len(target)] != target):
        return 'skip', None
    mut_lines[new_index] = line[:col] + line[col:].replace(target, f"rep._mute(", 1)
    mut = ''.join(mut_lines)
    if mut.count('rep._mute(') != base.count('rep._mute(') + 1:
        return 'skip', None
    return 'landed', mut


def account(rows, n):
    """Reduce mutation results to the only numbers worth printing.

    rows: list of (func, lineno, kind, status) where status is RED, GREEN,
    SKIP-mutation-did-not-land, or '' (no result at all). A skip or an empty
    status must never be counted as asserted - the whole instrument exists so
    a coverage claim cannot be derived by subtracting the failures from a
    constant.
    """
    reds = sum(1 for r in rows if r[-1] == 'RED')
    green = [r for r in rows if r[-1] == 'GREEN']
    skips = [r for r in rows if r[-1].startswith('SKIP')]
    missing = n - len(rows)
    return reds, green, skips, missing


def run_one(src, site, suite):
    """Mute one site in `src` and run `suite`; returns (site + status)."""
    # always restore, even when the suite blows up (timeout, KeyboardInterrupt)
    base = src.read_text()
    try:
        status, mut = mutate(base, site)
        if status != 'landed':
            return site + ('SKIP-mutation-did-not-land',)
        src.write_text(mut)
        r = subprocess.run(suite, cwd=src.parent.parent,
                           capture_output=True, text=True, timeout=300)
        return site + ('RED' if r.returncode != 0 else 'GREEN',)
    finally:
        src.write_text(base)


def build_worker_tree(w):
    d = pathlib.Path('/tmp/opencode/mut_{}'.format(w))
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    return d


def main(argv):
    target = DEFAULT_TARGET
    if len(argv) > 1:
        if argv[1] in ('--target', '-t') and len(argv) > 2:
            target = argv[2]
        else:
            sys.stderr.write(f"usage: python3 {pathlib.Path(argv[0]).name} [--target PATH]\n")
            return 2

    src = ROOT / target
    if not src.is_file():
        sys.stderr.write(f"no such target: {target}\n")
        return 2

    # --- self-test: can this harness report a false pass at all? ------------
    # Mirror of tools/mutation-audit.sh. A mutation audit that cannot detect a
    # broken harness is a coverage claim bought with the same confidence as a
    # real one. It audits a target no test touches; every site must come back
    # FALSE PASS ("asserted ... 0/2", "false passes: 2"). If instead the probe
    # looks asserted, the harness is not measuring what it claims to.
    if os.environ.get('AIORG_MUT_SELFTEST', '1') != '0':
        probe_root = pathlib.Path('/tmp/opencode/mut_py_selftest')
        probe_work = '/tmp/opencode/mut_py_selftest_work'
        shutil.rmtree(probe_root, ignore_errors=True)
        probe_root.mkdir(parents=True)
        shutil.copytree(ROOT, probe_root / 'tree',
                        ignore=shutil.ignore_patterns('.git', '__pycache__'))
        probe = probe_root / 'tree' / 'tools' / '_probe.py'
        probe.write_text(
            "class Rep:\n"
            "    def error(self, agent: str, msg: str) -> None:\n"
            "        pass\n"
            "    def warn(self, agent: str, msg: str) -> None:\n"
            "        pass\n"
            "rep = Rep()\n"
            "def main():\n"
            "    rep.error('a')\n"
            "    rep.warn('b')\n"
            "if __name__ == '__main__':\n"
            "    main()\n")
        env = dict(os.environ, AIORG_MUT_SELFTEST='0')
        r = subprocess.run([sys.executable, 'tools/mutation-audit.py',
                            '--target', 'tools/_probe.py'],
                           cwd=str(probe_root / 'tree'),
                           env=env, capture_output=True, text=True, timeout=600)
        # point the child's suite back at the real one is NOT needed: the probe
        # tree's own copy of the suite is what runs, and it asserts nothing about
        # the probe - which is the point of the probe.
        if r.returncode != 0 or not re.search(r'asserted .*0/2', r.stdout) \
                or not re.search(r'false passes:\s*2', r.stdout):
            print("mutation-audit.py FAILED ITS OWN SELF-TEST - do not trust any number it prints.")
            print()
            print(r.stdout + r.stderr)
            return 3
        print("self-test ok: a target no test touches measures 0/2 asserted, not 2/2.")
        print()

    source = src.read_text()
    sites = find_sites(source)
    print(f"{len(sites)} finding sites in {target}")

    n = len(sites)
    if n == 0:
        return 0

    WORKERS = 4
    trees = [build_worker_tree(w) for w in range(WORKERS)]
    chunk_owner = {}
    for w in range(WORKERS):
        for idx in range(w, n, WORKERS):
            chunk_owner[idx] = w
    print(f"mutating {n} site(s), {WORKERS} contiguous chunks (no shared dir), one call muted at a time\n")

    def run_chunk(chunk):
        out = []
        for idx in chunk:
            d = trees[chunk_owner[idx]]
            tree_src = d / target
            suite = [sys.executable, 'tests/test_retrieval.py']
            out.append(run_one(tree_src, sites[idx], suite))
        return out

    res = []
    chunks = [list(range(w, n, WORKERS)) for w in range(WORKERS)]
    with ThreadPoolExecutor(WORKERS) as ex:
        for out in ex.map(run_chunk, chunks):
            res.extend(out)
    res.sort()

    json.dump([[r[0], r[1], r[2], r[-1]] for r in res],
              open('/tmp/opencode/mut_py_results.json', 'w'), indent=1)

    reds, green, skips, missing = account(res, n)
    measured = reds + len(green) + len(skips)
    for r in res:
        func, lineno, kind, st = r[0], r[1], r[2], r[-1]
        if st == 'GREEN':
            print(f"  FALSE PASS  {func}:{lineno}  rep.{kind}()")
        elif st.startswith('SKIP'):
            print(f"  SKIPPED (counts for nothing)  {func}:{lineno}  rep.{kind}()")
    print(f"\n  asserted (suite goes red when silenced): {reds}/{measured}")
    print(f"  false passes: {len(green)}")
    print(f"  skipped:      {len(skips)}")
    print(f"  no result:    {missing}")

    if missing > 0:
        print("\n  THE HARNESS IS BROKEN. Sites went unmeasured - fix this script before")
        print("  believing anything it says: an unmeasured site is the false-pass shape")
        print("  this audit exists to detect.")
        return 2
    if skips:
        print("\n  NOTE: skipped sites are NOT asserted, so the ratio above understates")
        print("  coverage. A skipped mutation is a mutation that did not happen.")
    if measured != n:
        print(f"\n  ERROR: measured {measured} of {n} sites")
        return 2
    print("\n  full results: /tmp/opencode/mut_py_results.json")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))