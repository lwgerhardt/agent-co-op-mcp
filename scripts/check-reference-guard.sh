#!/usr/bin/env bash
# Fail if tracked files contain forbidden consumer reference paths or names.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GUARD_SCRIPT="scripts/check-reference-guard.sh"

PATTERNS=(
  'examples/loa'
  'references/loa'
  'loa-gap-analysis'
  'legacy-of-arcana'
  'Legacy-of-Arcana'
  'Legacy of Arcana'
  '\bLoA\b'
  '\bArcana\b'
)

mapfile -t FILES < <(
  git ls-files -- . ":(exclude)${GUARD_SCRIPT}" | rg -v '^$' || true
)

if ((${#FILES[@]} == 0)); then
  echo "No tracked files to scan."
  exit 0
fi

FAILED=0
for pattern in "${PATTERNS[@]}"; do
  if MATCHES=$(rg -n -i --no-heading "$pattern" "${FILES[@]}" 2>/dev/null || true); then
    if [[ -n "$MATCHES" ]]; then
      echo "Forbidden reference pattern matched: $pattern"
      echo "$MATCHES"
      echo
      FAILED=1
    fi
  fi
done

if ((FAILED != 0)); then
  echo "Forbidden reference patterns must not appear in this repository."
  echo "Remove the matches above or use generic examples under examples/."
  exit 1
fi

echo "Reference guard passed."
