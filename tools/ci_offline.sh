#!/usr/bin/env bash
# PiDrive Offline-CI — lokal und in GitHub Actions
# Nutzung: bash tools/ci_offline.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/pidrive${PYTHONPATH:+:$PYTHONPATH}"

RED=$'\033[31m'; GRN=$'\033[32m'; CYN=$'\033[36m'; BLD=$'\033[1m'; RST=$'\033[0m'
pass() { echo "${GRN}✓${RST} $*"; }
fail() { echo "${RED}✗${RST} $*"; exit 1; }
step() { echo; echo "${BLD}${CYN}══ $* ══${RST}"; }

# venv: lokal (PEP 668), in Actions reicht System-Python wenn deps schon da
ensure_python() {
  if python3 -c "import pytest, flask" 2>/dev/null; then
    return 0
  fi
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    python3 -m pip install -q -r requirements-ci.txt
    return 0
  fi
  local venv="${ROOT}/.venv-ci"
  if [[ ! -d "$venv" ]]; then
    echo "Lege $venv an (PEP 668) …"
    python3 -m venv "$venv"
  fi
  # shellcheck disable=SC1091
  source "$venv/bin/activate"
  python3 -m pip install -q -U pip
  python3 -m pip install -q -r requirements-ci.txt
}

ensure_python

FAILED=0
run() {
  local name="$1"; shift
  step "$name"
  if "$@"; then
    pass "$name"
  else
    echo "${RED}FAILED: $name${RST}"
    FAILED=$((FAILED + 1))
  fi
}

# ── 1. Docs ──────────────────────────────────────────────────────────────────
run "Docs-Links" bash tools/check_docs.sh

# ── 2. Shell-Syntax ──────────────────────────────────────────────────────────
step "Shell-Syntax"
for f in install.sh tools/check_docs.sh tools/ci_offline.sh scripts/*.sh; do
  [[ -f "$f" ]] || continue
  bash -n "$f" || fail "bash -n $f"
done
pass "Shell-Syntax"

# ── 3. Python compile ────────────────────────────────────────────────────────
step "compileall"
python3 -m compileall -q pidrive || fail "compileall"
pass "compileall"

# ── 4. pytest (Unit + Verträge) ──────────────────────────────────────────────
step "pytest"
python3 -m pytest tests/unit -q --tb=short
pass "pytest"

# ── 5. Zusammenfassung ───────────────────────────────────────────────────────
echo
if [[ "$FAILED" -gt 0 ]]; then
  fail "$FAILED Schritt(e) fehlgeschlagen"
fi
echo "${GRN}${BLD}OK: Offline-CI grün${RST}"
