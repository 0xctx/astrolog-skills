#!/usr/bin/env bash
# Every check this project has, one PASS/FAIL verdict. Run from anywhere: scripts/validate.sh [--full]
#   --full  also runs the real official Astrolog download + build test (network, ~10 s)
cd "$(dirname "$0")/.." || exit 2
checks=(
  "unit tests|uv run pytest -q"
  "real Astrolog|uv run pytest -q -m 'astrolog and not network'"
  "types|uv run mypy"
  "lint|uv run ruff check ."
  "format|uv run ruff format --check ."
  "plugin|claude plugin validate . --strict"
  "manifest|claude plugin validate .claude-plugin/plugin.json --strict"
  "doctor smoke|bin/astro --json doctor --no-first-light"
  "source privacy|uv run python scripts/check_source_privacy.py"
)
[[ ${1:-} == --full ]] && checks+=("network + build|uv run pytest -q -m network")
failed=0
for check in "${checks[@]}"; do
  name=${check%%|*}; cmd=${check#*|}
  if out=$(eval "$cmd" 2>&1); then
    echo "✅ $name"
  else
    failed=1; echo "❌ $name — $cmd"; echo "$out" | tail -20 | sed 's/^/     /'
  fi
done
if [[ $failed == 0 ]]; then echo "Overall: PASS"; else echo "Overall: FAIL"; exit 1; fi
