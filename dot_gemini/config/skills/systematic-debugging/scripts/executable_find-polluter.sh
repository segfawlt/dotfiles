#!/usr/bin/env bash
# Bisect which test file creates unwanted filesystem/state pollution.
# Usage: ./find-polluter.sh <file_or_dir_to_check> <test_glob_pattern> <test_runner_cmd...>
# Example: ./find-polluter.sh '.git' 'src/**/*.test.ts' pnpm vitest run

set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <file_or_dir_to_check> <test_pattern> [runner_cmd...]" >&2
  echo "Example: $0 '.test-leak.db' 'src/**/*.test.ts' pnpm vitest run" >&2
  exit 1
fi

POLLUTION_CHECK="$1"
TEST_PATTERN="${2#./}"
shift 2

if [ "$#" -gt 0 ]; then
  RUNNER=("$@")
else
  RUNNER=(npx vitest run)
fi

if [ -e "$POLLUTION_CHECK" ]; then
  echo "Error: '$POLLUTION_CHECK' already exists before running tests. Remove it first." >&2
  exit 1
fi

mapfile -t TEST_FILES < <(find . \( -path "./$TEST_PATTERN" -o -path "./${TEST_PATTERN//\*\*\//}" \) -type f | sort -u)
TOTAL="${#TEST_FILES[@]}"

echo "Scanning $TOTAL test files for '$POLLUTION_CHECK' using: ${RUNNER[*]}"

COUNT=0
for TEST_FILE in "${TEST_FILES[@]}"; do
  COUNT=$((COUNT + 1))
  printf '[%d/%d] %s\r' "$COUNT" "$TOTAL" "$TEST_FILE"
  "${RUNNER[@]}" "$TEST_FILE" >/dev/null 2>&1 || true

  if [ -e "$POLLUTION_CHECK" ]; then
    echo -e "\nPOLLUTER FOUND: $TEST_FILE (created '$POLLUTION_CHECK')"
    ls -la "$POLLUTION_CHECK"
    exit 0
  fi
done

echo -e "\nNo single test file created '$POLLUTION_CHECK' in isolation."
exit 1
