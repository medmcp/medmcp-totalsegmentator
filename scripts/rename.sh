#!/usr/bin/env bash
# One-shot rename of the placeholder package name after scaffolding from the template.
#
# Usage:
#   ./scripts/rename.sh medmcp-dicom
#
# This replaces:
#   - the PyPI/distribution name  "medmcp-template"  -> "medmcp-dicom"
#   - the Python module name      "medmcp_template"  -> "medmcp_dicom"
#   - the src directory           src/medmcp_template -> src/medmcp_dicom
#
# The script removes itself when it finishes.

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 <new-package-name>" >&2
    echo "  e.g. $0 medmcp-dicom" >&2
    exit 1
fi

NEW_DIST="$1"

if [[ ! "$NEW_DIST" =~ ^[a-z][a-z0-9-]*$ ]]; then
    echo "error: package name must be lowercase letters, digits, and hyphens (got: $NEW_DIST)" >&2
    exit 1
fi

NEW_MOD="${NEW_DIST//-/_}"

OLD_DIST="medmcp-template"
OLD_MOD="medmcp_template"

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

if [[ ! -d "src/$OLD_MOD" ]]; then
    echo "error: src/$OLD_MOD not found — did you already rename?" >&2
    exit 1
fi

echo "Renaming: $OLD_DIST -> $NEW_DIST  (module: $OLD_MOD -> $NEW_MOD)"

# Find all git-tracked text files and substitute in place. Includes Dockerfiles
# and JSON (the .devcontainer config) so the container setup is renamed too.
# Exclude this script, LICENSE/CHANGELOG (historical text), and CONTRIBUTING.md
# (contains meta-references to medmcp-template as the origin template repo that
# must not be renamed).
mapfile -t files < <(
    git ls-files \
        "*.py" "*.toml" "*.yml" "*.yaml" "*.md" "justfile" "*.cfg" "*.ini" \
        "*Dockerfile" "*.json" \
        | grep -v -E "^scripts/rename\.sh$|^CHANGELOG\.md$|^CONTRIBUTING\.md$"
)

for f in "${files[@]}"; do
    if grep -q -E "$OLD_DIST|$OLD_MOD" "$f"; then
        sed -i.bak \
            -e "s/$OLD_DIST/$NEW_DIST/g" \
            -e "s/$OLD_MOD/$NEW_MOD/g" \
            "$f"
        rm "$f.bak"
        echo "  updated: $f"
    fi
done

git mv "src/$OLD_MOD" "src/$NEW_MOD" 2>/dev/null || mv "src/$OLD_MOD" "src/$NEW_MOD"
echo "  moved:   src/$OLD_MOD -> src/$NEW_MOD"

# Rename the in-package skills subdirectory (directory name not covered by sed above).
if [[ -d "src/$NEW_MOD/skills/$OLD_DIST" ]]; then
    # git mv so the index follows; a plain mv leaves `git ls-files` reporting a
    # path that no longer exists, which later loops then fail to open.
    git mv "src/$NEW_MOD/skills/$OLD_DIST" "src/$NEW_MOD/skills/$NEW_DIST" 2>/dev/null \
        || mv "src/$NEW_MOD/skills/$OLD_DIST" "src/$NEW_MOD/skills/$NEW_DIST"
    echo "  moved:   src/$NEW_MOD/skills/$OLD_DIST -> src/$NEW_MOD/skills/$NEW_DIST"
fi

# Strip the scaffolding sections. These explain how to create a stack FROM the
# template and are meaningless once you are the stack — medmcp-dicom shipped with
# them for months because this step was left to the reader. The markers are in
# README.md and CONTRIBUTING.md; CONTRIBUTING is excluded from the rename above
# (it names the template deliberately) but still needs the block removed.
stripped=0
while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    if grep -q "TEMPLATE-ONLY:START" "$f"; then
        sed -i.bak '/<!-- TEMPLATE-ONLY:START -->/,/<!-- TEMPLATE-ONLY:END -->/d' "$f"
        rm "$f.bak"
        echo "  stripped template-only section: $f"
        stripped=$((stripped + 1))
    fi
done < <(git ls-files "*.md")
[[ $stripped -gt 0 ]] || echo "  note: no TEMPLATE-ONLY markers found (already stripped?)"

# Point the image workflow at the new stack and let it publish. The template
# ships with push disabled so it never publishes ghcr.io/medmcp/template.
SHORT="${NEW_DIST#medmcp-}"
if [[ -f .github/workflows/images.yml ]]; then
    sed -i.bak \
        -e "s/^  STACK: template$/  STACK: $SHORT/" \
        -e "s/^          push: false$/          push: \${{ github.event_name != 'pull_request' }}/" \
        .github/workflows/images.yml
    rm .github/workflows/images.yml.bak
    echo "  updated: .github/workflows/images.yml (STACK=$SHORT, publishing enabled)"
fi

# Remove this script rather than telling the reader to. One less step to skip.
rm -f "$0"
echo "  removed: scripts/rename.sh"

echo
echo "Done. Next steps:"
echo "  1. Edit pyproject.toml (description, keywords, URLs)"
echo "  2. Replace README.md with your project's own README, including the"
echo "     Bundled tools and Citation sections, and mirror them in NOTICE"
echo "  3. Implement your tools in src/$NEW_MOD/tools/ and register them in server.py"
echo "     Include a _render key in each tool's return dict with display rules + NEXT ACTION"
echo "  4. Rename src/$NEW_MOD/skills/$NEW_DIST/ to a task name (e.g. explore-data),"
echo "     update the name: field in SKILL.md to match, then write workflow + gotchas only"
echo "  5. just setup && just check"
