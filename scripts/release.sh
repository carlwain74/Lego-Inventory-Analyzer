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

# Write token to a temp file to avoid subshell stdin issues on macOS
DOCKER_CONFIG_TMP=$(mktemp)
trap 'rm -f "$DOCKER_CONFIG_TMP"' EXIT

echo "$DOCKER_HUB_TOKEN" > "$DOCKER_CONFIG_TMP"

if ! docker login --username "$DOCKER_USER" --password-stdin < "$DOCKER_CONFIG_TMP"; then
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
push_tag() {
  local tag="$1"
  local exit_code
  info "Pushing ${IMAGE}:${tag}…"
  set +e
  docker push "${IMAGE}:${tag}"
  exit_code=$?
  set -e
  if [[ $exit_code -ne 0 ]]; then
    error "Push failed for ${IMAGE}:${tag} (exit code ${exit_code}).

  Possible causes:
    - PAT does not have Read & Write scope
    - PAT has expired
    - Repository does not exist on Docker Hub

  Regenerate your token at: https://hub.docker.com/settings/security
  Ensure 'Read & Write' access is selected."
  fi
  success "Pushed ${tag}."
}

push_tag "$VERSION"
push_tag "latest"

# ── Verify pushed tags via Docker Hub API ────────────────────────────────────
info "Verifying pushed tags on Docker Hub…"

# Use python3 to POST the login request safely — avoids shell quoting issues
# with the JSON payload when building it via curl -d
HUB_JWT=$(python3 - "$DOCKER_USER" "$DOCKER_HUB_TOKEN" << 'PYEOF'
import sys, json, urllib.request
user, token = sys.argv[1], sys.argv[2]
payload = json.dumps({"username": user, "password": token}).encode()
req = urllib.request.Request(
    "https://hub.docker.com/v2/users/login",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)
try:
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read().decode())
        print(data.get("token", ""))
except Exception:
    print("")
PYEOF
)

if [[ -z "$HUB_JWT" ]]; then
  warn "Could not obtain Docker Hub JWT for verification. Skipping tag checks."
else
  verify_tag() {
    local tag="$1"
    local url="https://hub.docker.com/v2/repositories/${IMAGE}/tags/${tag}/"
    local http_status
    http_status=$(curl -s -o /dev/null -w "%{http_code}" \
      -H "Authorization: JWT ${HUB_JWT}" \
      "$url")
    if [[ "$http_status" == "200" ]]; then
      success "Verified ${IMAGE}:${tag} on Docker Hub."
    else
      warn "Could not verify ${IMAGE}:${tag} (HTTP ${http_status}). Check https://hub.docker.com/r/${IMAGE}/tags manually."
    fi
  }

  verify_tag "$VERSION"
  verify_tag "latest"
fi

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
