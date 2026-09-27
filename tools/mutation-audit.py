"""Mutation audit: does a test own every finding tools/check-agents.py makes?

Run it from the project root:

    python3 tools/mutation-audit.py

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

**Two traps this script already fell into, both of which produced numbers that
looked like findings about the project:**

1. Do not pick a scratch directory with `idx % WORKERS`. That chooses a
   directory but not a thread, so ThreadPoolExecutor runs tasks with the same
   index class concurrently in one tree and they overwrite each other's
   mutations. The total then moves between identical runs (it did: 19, 21, 6).
   Each worker now gets a contiguous chunk and its own tree.
2. A mutation whose line window misses its target returns SKIP, and SKIP must
   NOT be counted as asserted. A mutation that never happened reported as a
   pass is the exact false-pass shape this script exists to detect.

The result is stable across runs. Keep it that way: if the number moves between
identical runs, the harness is broken, not the tree.
"""
import ast, pathlib, re, subprocess, sys, os, shutil
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent   # like the checker itself
SRC = 'tools/check-agents.py'
orig = (ROOT/SRC).read_text()

def is_emit(n):
    return (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr in ('error','warn')
            and isinstance(n.func.value, ast.Name) and n.func.value.id=='rep')
sites=[]
def walk(node,cur):
    for n in ast.iter_child_nodes(node):
        if isinstance(n, ast.FunctionDef): walk(n,n.name)
        else:
            if is_emit(n) and cur: sites.append((cur,n.lineno,n.func.attr))
            walk(n,cur)
walk(ast.parse(orig),None)

# no-op siblings so silencing one finding is not a crash
MUT = "    def _mute(self, agent: str, msg: str) -> None:\n        return\n\n"

def build(w):
    d = pathlib.Path(f'/tmp/opencode/mut_{w}')
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns('.git'))
    return d

def run_chunk(chunk):
    out = []
    for idx in chunk:
        out.append(run_one(idx))
    return out

def run_one(idx):
    func,lineno,kind = sites[idx]
    w = chunk_owner[idx]
    d = pathlib.Path(f'/tmp/opencode/mut_{w}')
    f = d/SRC
    base = f.read_text()
    # insert no-op once, right after the Report class __init__
    if '_mute' not in base:
        base = base.replace("    def error(self", MUT + "    def error(self", 1)
    lines = base.splitlines(keepends=True)
    i = lineno-1
    # the site line may have shifted by the insertion; locate by call text
    target = f"rep.{kind}("
    for j in range(i, min(i+4, len(lines))):
        if target in lines[j]:
            lines[j] = lines[j].replace(target, f"rep._mute(", 1); break
    else:
        return (idx, func, lineno, kind, 'SKIP-mutation-did-not-land')
    mut = ''.join(lines)
    if mut.count('rep._mute(') != base.count('rep._mute(') + 1:
        return (idx, func, lineno, kind, 'SKIP-mutation-did-not-land')
    f.write_text(mut)
    r = subprocess.run([sys.executable,'tests/test_retrieval.py'],cwd=d,
                       capture_output=True,text=True,timeout=300)
    f.write_text(base)
    return (idx, func, lineno, kind, 'RED' if r.returncode!=0 else 'GREEN')

WORKERS = 4
for w in range(WORKERS): build(w)
print(f"{len(sites)} finding sites, {WORKERS} contiguous chunks (no shared dir), one call muted at a time\n")
chunks = [list(range(i, len(sites), WORKERS)) for i in range(WORKERS)]
chunk_owner = {}
for w, ch in enumerate(chunks):
    for idx in ch: chunk_owner[idx] = w
res=[]
with ThreadPoolExecutor(WORKERS) as ex:
    for out in ex.map(run_chunk, chunks): res.extend(out)
res.sort()
import json
json.dump([[r[1],r[2],r[3],r[4]] for r in res], open('/tmp/opencode/mut_results.json','w'), indent=1)
green=[r for r in res if r[4]=='GREEN']
skips=[r for r in res if r[4].startswith('SKIP')]
for s in skips: print(f"  SKIPPED (counts for nothing)  {s[1]}:{s[2]}")
for idx,func,lineno,kind,st in res:
    if st=='GREEN': print(f"  FALSE PASS  {func}:{lineno}  rep.{kind}()")
print(f"\n  asserted (suite goes red when silenced): {len(res)-len(green)}/{len(res)}")
print(f"  false passes: {len(green)}")
