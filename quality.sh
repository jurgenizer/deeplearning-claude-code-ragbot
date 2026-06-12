#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

case "$1" in
  --fix)
    echo "Formatting code with black..."
    uv run black backend/
    echo "Done. All files formatted."
    ;;
  "")
    echo "Checking code formatting..."
    uv run black --check backend/
    echo "All formatting checks passed."
    ;;
  *)
    echo "Usage: $0 [--fix]"
    echo "  (no args)  Check formatting without changes"
    echo "  --fix      Auto-format all files"
    exit 1
    ;;
esac
