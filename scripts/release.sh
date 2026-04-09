#!/usr/bin/env bash
#
# Universal release script for DevHelm surface artifacts.
# Works for JS/TS (package.json), Python (pyproject.toml), and Go (tag-only).
#
# Usage:
#   ./scripts/release.sh <version>
#   ./scripts/release.sh 0.2.0
#   ./scripts/release.sh patch   (auto-bump: patch/minor/major)
#
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

die() { echo -e "${RED}error:${NC} $1" >&2; exit 1; }
info() { echo -e "${GREEN}=>${NC} $1"; }
warn() { echo -e "${YELLOW}warn:${NC} $1"; }

# --- Validate args ---
[[ $# -eq 1 ]] || die "Usage: ./scripts/release.sh <version|patch|minor|major>"
INPUT="$1"

# --- Detect project type ---
if [[ -f package.json ]]; then
  PROJECT_TYPE="node"
elif [[ -f pyproject.toml ]]; then
  PROJECT_TYPE="python"
elif [[ -f go.mod ]]; then
  PROJECT_TYPE="go"
else
  PROJECT_TYPE="generic"
fi

# --- Resolve current version ---
get_current_version() {
  case "$PROJECT_TYPE" in
    node)   node -p "require('./package.json').version" ;;
    python) grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)"/\1/' ;;
    *)      git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' || echo "0.0.0" ;;
  esac
}

CURRENT=$(get_current_version)

# --- Resolve target version ---
bump_version() {
  local current="$1" part="$2"
  IFS='.' read -r major minor patch <<< "$current"
  case "$part" in
    major) echo "$((major + 1)).0.0" ;;
    minor) echo "${major}.$((minor + 1)).0" ;;
    patch) echo "${major}.${minor}.$((patch + 1))" ;;
  esac
}

case "$INPUT" in
  major|minor|patch)
    VERSION=$(bump_version "$CURRENT" "$INPUT")
    ;;
  *)
    VERSION="${INPUT#v}"
    ;;
esac

# --- Validate semver ---
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
  die "Invalid semver: $VERSION"
fi

TAG="v${VERSION}"

# --- Pre-flight checks ---
[[ -z "$(git status --porcelain)" ]] || die "Working tree is dirty. Commit or stash changes first."

BRANCH=$(git branch --show-current)
[[ "$BRANCH" == "main" ]] || die "Must be on 'main' branch (currently on '$BRANCH')."

git fetch origin --tags --quiet
if git rev-parse "$TAG" >/dev/null 2>&1; then
  die "Tag $TAG already exists."
fi

info "Releasing: $CURRENT → ${VERSION} ($PROJECT_TYPE project)"
echo ""

# --- Bump version in project files ---
case "$PROJECT_TYPE" in
  node)
    npm version "$VERSION" --no-git-tag-version --allow-same-version >/dev/null
    info "Updated package.json → $VERSION"
    ;;
  python)
    sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml
    info "Updated pyproject.toml → $VERSION"
    ;;
  go)
    info "Go project — version derived from tag only"
    ;;
  generic)
    warn "No recognized project file — tagging only"
    ;;
esac

# --- Commit version bump (if files changed) ---
if [[ -n "$(git status --porcelain)" ]]; then
  git add -A
  git commit -m "chore: bump version to ${VERSION}" --quiet
  info "Committed version bump"
fi

# --- Tag and push ---
git tag -a "$TAG" -m "Release ${TAG}"
info "Created tag $TAG"

git push origin main --quiet
git push origin "$TAG" --quiet
info "Pushed main + $TAG to origin"

echo ""
echo -e "${GREEN}✓ Release ${TAG} initiated!${NC}"
echo "  → CI will build, test, and wait for your approval"
echo "  → Approve at: https://github.com/$(git remote get-url origin | sed 's|.*github.com[:/]\(.*\)\.git|\1|')/actions"
