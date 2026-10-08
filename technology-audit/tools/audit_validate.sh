#!/usr/bin/env bash
# Validate technology-audit repo structure and required project artifacts.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RED=$'\033[31m'; GRN=$'\033[32m'; BLD=$'\033[1m'; RST=$'\033[0m'
fail() { echo "${RED}✗${RST} $*"; exit 1; }
pass() { echo "${GRN}✓${RST} $*"; }

step() { echo; echo "${BLD}══ $* ══${RST}"; }

step "Required top-level files"
for f in README.md docs/METHODOLOGY.md docs/TAXONOMY.md templates/technology-sheet.yaml; do
  [[ -f "$f" ]] || fail "missing $f"
done
pass "top-level"

step "Projects"
shopt -s nullglob
projects=(projects/*/)
[[ ${#projects[@]} -gt 0 ]] || fail "no projects/*/"
for p in "${projects[@]}"; do
  slug="${p%/}"
  slug="${slug#projects/}"
  [[ -f "projects/$slug/SCOPE.md" ]] || fail "projects/$slug/SCOPE.md"
  [[ -f "projects/$slug/INVENTORY.md" ]] || fail "projects/$slug/INVENTORY.md"
  inv="projects/$slug/INVENTORY.md"
  grep -q '|.*|' "$inv" || fail "$inv: no table rows"
  sheet_count=$(find "projects/$slug/sheets" -name '*.yaml' 2>/dev/null | wc -l)
  if [[ "$sheet_count" -lt 1 ]]; then
    fail "projects/$slug/sheets: need at least one .yaml"
  fi
  pass "project $slug ($sheet_count sheets)"
done

step "YAML sanity"
while IFS= read -r y; do
  grep -q '^id:' "$y" || fail "$y: missing id:"
  grep -q '^maturity:' "$y" || fail "$y: missing maturity:"
done < <(find projects -name '*.yaml' -print)

pass "YAML sanity"
echo
echo "${GRN}${BLD}OK: audit_validate${RST}"
