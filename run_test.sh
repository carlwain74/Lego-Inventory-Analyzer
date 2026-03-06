#!/usr/bin/env bash
# run_tests.sh — Run the pytest and Jest test suites and report results
# Usage: ./run_tests.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTS_DIR="$SCRIPT_DIR/tests"
UI_DIR="$SCRIPT_DIR/test_ui"

PYTEST_PASSED=false
JEST_PASSED=false

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
RESET='\033[0m'

# ── Helpers ───────────────────────────────────────────────────────────────────
header() { echo -e "\n${BOLD}${YELLOW}══════════════════════════════════════${RESET}"; \
           echo -e "${BOLD}${YELLOW}  $1${RESET}"; \
           echo -e "${BOLD}${YELLOW}══════════════════════════════════════${RESET}\n"; }
pass()   { echo -e "${GREEN}✔  $1${RESET}"; }
fail()   { echo -e "${RED}✘  $1${RESET}"; }

# ── pytest ────────────────────────────────────────────────────────────────────
header "pytest  →  $TESTS_DIR"

COVERAGE_THRESHOLD=90
COVERAGE_PASSED=false

if ! command -v pipenv &>/dev/null; then
  fail "pipenv not found — run: pip install pipenv"
  PYTEST_EXIT=127
elif [ ! -d "$TESTS_DIR" ]; then
  fail "tests/ directory not found at $TESTS_DIR"
  PYTEST_EXIT=1
else
  echo "Syncing Pipfile dev dependencies..."
  pipenv sync --dev

  set +e
  pipenv run pytest "$TESTS_DIR" -v \
    --cov="$SCRIPT_DIR" \
    --cov-config="$SCRIPT_DIR/.coveragerc" \
    --cov-report=term-missing \
    --cov-report=html:"$SCRIPT_DIR/coverage_html" \
    2>&1
  PYTEST_EXIT=$?
  set -e
fi

if [ $PYTEST_EXIT -eq 0 ]; then
  PYTEST_PASSED=true
  pass "pytest suite passed"
else
  fail "pytest suite failed (exit $PYTEST_EXIT)"
fi

# ── Coverage threshold check ──────────────────────────────────────────────────
if [ $PYTEST_EXIT -eq 0 ] && command -v pipenv &>/dev/null; then
  set +e
  COVERAGE_PCT=$(pipenv run coverage report --rcfile="$SCRIPT_DIR/.coveragerc" 2>/dev/null \
    | awk '/TOTAL/{print $NF}' | tr -d '%')
  set -e

  if [ -n "$COVERAGE_PCT" ]; then
    if [ "$COVERAGE_PCT" -ge "$COVERAGE_THRESHOLD" ]; then
      COVERAGE_PASSED=true
      pass "Coverage: ${COVERAGE_PCT}% (threshold: ${COVERAGE_THRESHOLD}%)"
    else
      fail "Coverage: ${COVERAGE_PCT}% is below threshold of ${COVERAGE_THRESHOLD}%"
      fail "HTML report: $SCRIPT_DIR/coverage_html/index.html"
      PYTEST_PASSED=false
    fi
  else
    echo -e "${YELLOW}⚠  Could not parse coverage percentage — check report manually${RESET}"
  fi
fi

# ── Jest ──────────────────────────────────────────────────────────────────────
header "Jest  →  $UI_DIR"

if ! command -v npm &>/dev/null; then
  fail "npm not found — install Node.js from https://nodejs.org"
  JEST_EXIT=127
elif [ ! -d "$UI_DIR" ]; then
  fail "test_ui/ directory not found at $UI_DIR"
  JEST_EXIT=1
else
  # Install node_modules if needed
  if [ ! -d "$UI_DIR/node_modules" ]; then
    echo "Installing npm dependencies..."
    npm --prefix "$UI_DIR" install --silent
  fi

  set +e
  npm --prefix "$UI_DIR" test 2>&1
  JEST_EXIT=$?
  set -e
fi

if [ $JEST_EXIT -eq 0 ]; then
  JEST_PASSED=true
  pass "Jest suite passed"
else
  fail "Jest suite failed (exit $JEST_EXIT)"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
header "Summary"

$PYTEST_PASSED   && pass "pytest (incl. coverage ≥ ${COVERAGE_THRESHOLD}%)" || fail "pytest"
$JEST_PASSED   && pass "Jest"   || fail "Jest"

echo ""
if $PYTEST_PASSED && $JEST_PASSED; then
  echo -e "${GREEN}${BOLD}All suites passed.${RESET}"
  exit 0
else
  echo -e "${RED}${BOLD}One or more suites failed.${RESET}"
  exit 1
fi