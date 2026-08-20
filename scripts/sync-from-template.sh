#!/usr/bin/env bash
# Copy the shared files listed in scripts/shared-files.txt from medmcp-template
# into this repo.
#
# Run this from a stack repo when the drift check reports a difference, or after
# the template changes something every stack should get:
#
#   ./scripts/sync-from-template.sh            # sync from the template's main
#   ./scripts/sync-from-template.sh <ref>      # ...or a tag/branch/SHA
#   DRY_RUN=1 ./scripts/sync-from-template.sh  # show what would change
#
# It writes files and nothing else — review the diff and commit it yourself.

set -euo pipefail

REF="${1:-main}"
TEMPLATE_REPO="${TEMPLATE_REPO:-https://github.com/medmcp/medmcp-template.git}"
DRY_RUN="${DRY_RUN:-}"

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

manifest="scripts/shared-files.txt"
[[ -f "$manifest" ]] || { echo "error: $manifest not found" >&2; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "Fetching $TEMPLATE_REPO @ $REF"
git clone --quiet --depth 1 --branch "$REF" "$TEMPLATE_REPO" "$tmp/template" 2>/dev/null \
    || {
        echo "error: could not clone $TEMPLATE_REPO at $REF" >&2
        echo "  If the template is private, point TEMPLATE_REPO at something you can read:" >&2
        echo "    TEMPLATE_REPO=git@github.com:medmcp/medmcp-template.git $0 $REF" >&2
        echo "    TEMPLATE_REPO=/path/to/local/medmcp-template $0 $REF" >&2
        exit 1
    }

changed=0 missing=0
while IFS= read -r f; do
    case "$f" in ''|'#'*) continue;; esac
    src="$tmp/template/$f"
    if [[ ! -f "$src" ]]; then
        echo "  !! not in template: $f"
        missing=$((missing + 1))
        continue
    fi
    if [[ -f "$f" ]] && cmp -s "$src" "$f"; then
        continue
    fi
    if [[ -n "$DRY_RUN" ]]; then
        echo "  would update: $f"
    else
        mkdir -p "$(dirname "$f")"
        cp "$src" "$f"
        echo "  updated: $f"
    fi
    changed=$((changed + 1))
done < "$manifest"

echo
if [[ $changed -eq 0 ]]; then
    echo "Already in sync with the template."
else
    echo "$changed file(s) ${DRY_RUN:+would be }changed. Review with: git diff"
fi
[[ $missing -eq 0 ]] || echo "$missing file(s) listed in $manifest are absent from the template — fix the manifest."
