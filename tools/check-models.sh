#!/usr/bin/env bash
# =============================================================================
# check-models.sh - ask real questions about the catalog's model tags.
#
# Two gaps, one script, because both of them are the same question asked at a
# different moment: "can this tag actually be pulled, and can it think?"
#
#   1. Phantom tags. config/models.json had no check that its tags exist, and
#      three of them did not (2026-09-26). A tag that cannot be pulled produces
#      a model that is missing at run time, and a missing model is how you get a
#      score that means nothing. This is the catalog-dressed version of the fake
#      100% that used to sit in AGENT_LAST_SCORE.
#
#   2. Thinking capability. Ollama 0.33.3 answers a `think:true` request sent to
#      a model with no reasoning channel with a hard error, not a shrug:
#
#          think=true  -> ERROR: "qwen2.5:0.5b" does not support thinking
#          think=false -> ok
#
#      The catalog records this as a `thinks` field per candidate, and
#      aiorg_effective_think treats a MISSING value as "cannot think" - the safe
#      direction, since think=off on a thinking model merely loses deliberation
#      while think=on on an instruct model means the run never happens. That
#      safety is exactly why the unverified ones need chasing: each one silently
#      forgoes thinking on a card that could have supported it.
#
# WHY THIS IS NOT PART OF ./bootstrap.sh check
#
# Both questions need something check-agents.py must not depend on. Tag
# existence needs the network, and capability needs a running Ollama with the
# weights already on disk. check-agents.py has to work offline on a machine with
# no GPU, because that is the machine you most need it on. So this is
# explicitly opt-in, and its findings are pasted back into the catalog by hand.
#
# USAGE
#
#   tools/check-models.sh              capability of models already pulled
#   tools/check-models.sh --online     + verify every tag exists in the registry
#   tools/check-models.sh --all        + try to pull the missing ones first
#
# Exit 0 if nothing is wrong, 1 if any tag is a phantom. Unconfirmed thinking
# capability is reported but is NOT fatal - it is a gap in what we know, not a
# defect in the catalog, and the safe default already handles it.
# =============================================================================

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CATALOG="$ROOT/config/models.json"

die() { printf 'check-models: %s\n' "$1" >&2; exit 1; }
note() { printf '  %s\n' "$1"; }
bad()  { printf '  [fail] %s\n' "$1"; }
ok()   { printf '  [ ok ] %s\n' "$1"; }
warn() { printf '  [warn] %s\n' "$1"; }

[ -f "$CATALOG" ] || die "no catalog at $CATALOG - run from the project root"
command -v python3 >/dev/null 2>&1 || die "python3 is required"
command -v jq     >/dev/null 2>&1 || die "jq is required"

ONLINE=0
PULL=0
for arg in "$@"; do
  case "$arg" in
    --online) ONLINE=1 ;;
    --all)    ONLINE=1; PULL=1 ;;
    -h|--help) sed -n '2,45p' "$0"; exit 0 ;;
    *) die "unknown option '$arg' (try --help)" ;;
  esac
done

# --- every model tag in the catalog, with the role and role it belongs to ----
# Printed as `role<TAB>model` so the report can say which role is affected.
# A model used by two roles appears twice on purpose: it is two decisions.
tags="$(python3 - "$CATALOG" <<'PY'
import json, sys
cat = json.load(open(sys.argv[1], encoding="utf-8"))
for role, spec in sorted(cat.get("roles", {}).items()):
    for c in spec.get("candidates", []):
        m = c.get("model")
        if m:
            print(f"{role}\t{m}")
PY
)" || die "could not parse $CATALOG"

[ -n "$tags" ] || die "the catalog lists no model candidates at all"

total="$(printf '%s\n' "$tags" | wc -l | tr -d ' ')"
unique="$(printf '%s\n' "$tags" | cut -f2 | sort -u | wc -l | tr -d ' ')"

# --- 1. does the tag exist? (network) ----------------------------------------
phantom=0
if [ "$ONLINE" -eq 1 ]; then
  echo "== tag existence (registry) =="
  # The tag goes in the PATH, not after a colon. `qwen3:14b` 404s under the
  # wrong form and 200s under the right one, and a 404 on a tag you are sure
  # exists usually means the URL is wrong rather than the model being missing.
  while IFS=$'\t' read -r role model; do
    repo="${model%%:*}"
    tag="${model##*:}"
    if [ "$repo" = "$model" ]; then
      warn "$model has no ':tag' - is '$model' really a model reference?"
      continue
    fi
    if [ "$PULL" -eq 1 ] && ! ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$model"; then
      note "pulling $model ..."
      ollama pull "$model" >/dev/null 2>&1 || true
    fi
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
      "https://registry.ollama.ai/v2/library/$repo/manifests/$tag")"
    case "$code" in
      200) ok "$model  (role $role)" ;;
      404) bad "$model  (role $role) - NOT IN THE REGISTRY. This is a phantom: \
anything that resolves to it will fail to pull."; phantom=$((phantom + 1)) ;;
      *)   warn "$model  (role $role) - registry returned HTTP $code" ;;
    esac
  done <<< "$tags"
  echo
fi

# --- 2. can it think? (local Ollama) ----------------------------------------
# /api/show reports a `capabilities` array; "thinking" in it is the server's own
# answer about the model, which is the only source worth trusting. The registry
# manifests do not carry it - they have no template field at all, so a manifest
# scan reports "no thinking" for models that demonstrably do think.
echo "== thinking capability (local model server) =="
# Named the one way, by the helper. A literal endpoint here would be the fourth
# round of this project's most-repeated bug: three scripts each addressing the
# server differently, and the symptom being a check that inspects the wrong
# machine whenever the GPU is elsewhere. tools/check-agents.py watches for
# exactly this and fails the build on it.
# shellcheck source=lib/common.sh
if ! . "$ROOT/lib/common.sh" 2>/dev/null; then
  die "cannot load lib/common.sh - run this from the project root"
fi
url="$(aiorg_ollama_url)"

if ! curl -sf --max-time 5 "$url/api/tags" >/dev/null 2>&1; then
  warn "no model server at $url - capability unconfirmed for every model."
  warn "Start Ollama, pull the models you want verified, and re-run."
else
  confirmed=0
  unconfirmed=0
  while IFS=$'\t' read -r role model; do
    caps="$(curl -s --max-time 20 "$url/api/show" \
      -d "$(jq -nc --arg m "$model" '{name:$m}')" 2>/dev/null \
      | jq -r 'if (.capabilities // null) == null then "absent" else (.capabilities | join(",")) end' \
      2>/dev/null)"
    case "$caps" in
      ""|absent|null)
        unconfirmed=$((unconfirmed + 1))
        printf '  [ ?? ] %-24s role %-20s not pulled - cannot confirm\n' "$model" "$role"
        ;;
      *thinking*)
        confirmed=$((confirmed + 1))
        ok "$(printf '%-24s role %-20s thinks' "$model" "$role")"
        ;;
      *)
        confirmed=$((confirmed + 1))
        ok "$(printf '%-24s role %-20s does NOT think  ->  "thinks": false' "$model" "$role")"
        ;;
    esac
  done <<< "$tags"
  echo
  note "confirmed: $confirmed    unconfirmed (not pulled): $unconfirmed"
fi

# --- verdict -----------------------------------------------------------------
echo
if [ "$phantom" -gt 0 ]; then
  printf '  [fail] %d phantom tag(s). Anything resolving to these fails to pull,\n' "$phantom"
  printf '         and a missing model produces a score that means nothing.\n'
  printf '         Fix the catalog, then re-run. See AGENTS.md, "phantom models".\n'
  exit 1
fi
if [ "$ONLINE" -eq 0 ]; then
  note "Tag existence was not checked - that needs the network. Run with --online."
fi
note "Unconfirmed thinking capability is a gap in what we know, not a defect:"
note "aiorg_effective_think treats it as 'cannot think', which is the safe side."
exit 0
