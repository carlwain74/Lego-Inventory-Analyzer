#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# docker-push.sh — Build and push carlwainwright/lego-inventory to Docker Hub
#
# Usage:
#   ./docker-push.sh [version]
#
# Arguments:
#   version   Optional tag e.g. 0.3. If omitted, the script resolves the
#             version from the latest git tag, then falls back to the VERSION
#             file.
#
# Environment:
#   DOCKER_HUB_TOKEN   Required. Docker Hub Personal Access Token.
#                      Generate at: Hub → Account Settings → Security → New Access Token
#                      Set locally:  export DOCKER_HUB_TOKEN=your_token_here
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

IMAGE="carlwainwright/lego-inventory"
DOCKER_USER="carlwainwright"

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Colour

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── Resolve version ───────────────────────────────────────────────────────────
if [[ $# -ge 1 ]]; then
  VERSION="$1"
  info "Using provided version: ${VERSION}"
else
  # Try git tag first
  if git rev-parse --git-dir > /dev/null 2>&1; then
    GIT_TAG=$(git describe --tags --abbrev=0 2>/dev/null || true)
    if [[ -n "$GIT_TAG" ]]; then
      # Strip leading 'v' if present (e.g. v0.3 → 0.3)
      VERSION="${GIT_TAG#v}"
      info "Using latest git tag: ${GIT_TAG} → ${VERSION}"
    fi
  fi

  # Fall back to VERSION file
  if [[ -z "${VERSION:-}" ]]; then
    if [[ -f VERSION ]]; then
      VERSION=$(cat VERSION | tr -d '[:space:]')
      warn "No git tag found — using VERSION file: ${VERSION}"
    else
      error "No version provided, no git tags found, and no VERSION file exists."
    fi
  fi
fi

# ── Validate version format ───────────────────────────────────────────────────
if [[ ! "$VERSION" =~ ^[0-9]+(\.[0-9]+)*$ ]]; then
  error "Invalid version '${VERSION}'. Expected format: digits and dots only (e.g. 0.2, 1.0, 1.2.3)"
fi

# ── Check required tools ──────────────────────────────────────────────────────
for cmd in docker git curl; do
  if ! command -v "$cmd" &> /dev/null; then
    error "'${cmd}' is not installed or not on PATH."
  fi
done

# ── Check Docker daemon is running ────────────────────────────────────────────
if ! docker info > /dev/null 2>&1; then
  error "Docker Desktop is not running. Please start it and try again."
fi

# ── Check DOCKER_HUB_TOKEN ────────────────────────────────────────────────────
if [[ -z "${DOCKER_HUB_TOKEN:-}" ]]; then
  error "DOCKER_HUB_TOKEN is not set.\n\n  Generate a token at: https://hub.docker.com/settings/security\n  Then run: export DOCKER_HUB_TOKEN=your_token_here"
fi

# ── Confirm before proceeding ─────────────────────────────────────────────────
echo ""
echo -e "  Image : ${CYAN}${IMAGE}${NC}"
echo -e "  Tags  : ${CYAN}${VERSION}${NC}, ${CYAN}latest${NC}"
echo ""
read -r -p "Proceed? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi
echo ""

# ── Login ─────────────────────────────────────────────────────────────────────
info "Logging in to Docker Hub…"
LOGIN_OUTPUT=$(echo "$DOCKER_HUB_TOKEN" | docker login --username "$DOCKER_USER" --password-stdin 2>&1)
LOGIN_EXIT=$?

if [[ $LOGIN_EXIT -ne 0 ]] || ! echo "$LOGIN_OUTPUT" | grep -q "Login Succeeded"; then
  echo "$LOGIN_OUTPUT" >&2
  error "Docker Hub login failed. Check your DOCKER_HUB_TOKEN and username."
fi
success "Logged in."

# ── Build ─────────────────────────────────────────────────────────────────────
info "Building ${IMAGE}:${VERSION} and ${IMAGE}:latest…"
docker build \
  -t "${IMAGE}:${VERSION}" \
  -t "${IMAGE}:latest" \
  .
success "Build complete."

# ── Push ──────────────────────────────────────────────────────────────────────
info "Pushing ${IMAGE}:${VERSION}…"
docker push "${IMAGE}:${VERSION}"
success "Pushed ${VERSION}."

info "Pushing ${IMAGE}:latest…"
docker push "${IMAGE}:latest"
success "Pushed latest."

# ── Verify pushed tags via Docker Hub API ────────────────────────────────────
info "Verifying pushed tags on Docker Hub…"

verify_tag() {
  local tag="$1"
  local url="https://hub.docker.com/v2/repositories/${IMAGE}/tags/${tag}/"
  local http_status
  http_status=$(curl -s -o /dev/null -w "%{http_code}"     -H "Authorization: Bearer ${DOCKER_HUB_TOKEN}"     "$url")
  if [[ "$http_status" == "200" ]]; then
    success "Verified ${IMAGE}:${tag} on Docker Hub."
  else
    warn "Could not verify ${IMAGE}:${tag} (HTTP ${http_status}). Check https://hub.docker.com/r/${IMAGE}/tags manually."
  fi
}

verify_tag "$VERSION"
verify_tag "latest"

# ── Logout ────────────────────────────────────────────────────────────────────
docker logout > /dev/null 2>&1
success "Logged out."

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}────────────────────────────────────────${NC}"
echo -e "${GREEN}  Done!${NC}"
echo -e "  ${IMAGE}:${VERSION}"
echo -e "  ${IMAGE}:latest"
echo -e "${GREEN}────────────────────────────────────────${NC}"
echo ""