#!/usr/bin/env bash
# Run syno_thumbs.py in every directory under the given photo root.
# Usage: ./run_all_thumbs.sh [PHOTO_ROOT]
# Example: ./run_all_thumbs.sh /mnt/mesterhome/Photos/PhotoLibrary

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${SCRIPT_DIR}/syno_thumbs.py"
ROOT="${1:-.}"

if [[ ! -f "$SCRIPT" ]]; then
  echo "Error: syno_thumbs.py not found at $SCRIPT" >&2
  exit 1
fi

if [[ ! -d "$ROOT" ]]; then
  echo "Error: not a directory: $ROOT" >&2
  exit 1
fi

echo "Running thumbnails under: $ROOT"
# Use -exec so find passes each path directly to python (avoids pipe corrupting paths)
find "$ROOT" -type d \( -name '@eaDir' -prune -o -exec python3 "$SCRIPT" {} \; \)
echo "Done."
