# Docker Hub — Build & Push Instructions

Repository: `carlwainwright/lego-inventory`
Version: `0.2`

---

## Prerequisites

- Docker Desktop installed and running
- Logged in to Docker Hub:

```bash
docker login
# Enter your Docker Hub username and password when prompted
```

---

## 1. Ensure Pipfile.lock is up to date

The Dockerfile uses `Pipfile.lock` for reproducible dependency installs.
If you have added or changed any packages since the last build, regenerate it:

```bash
pipenv lock
```

---

## 2. Build the image

Build and tag in one step directly with Docker:

```bash
docker build \
  -t carlwainwright/lego-inventory:0.2 \
  -t carlwainwright/lego-inventory:latest \
  .
```

> **Why not `docker compose build`?** Docker Compose names images after the
> project folder and service name — in this case it generates
> `lego-inventory-analyzer-lego-inventory:latest`, which is not the tag
> needed for Docker Hub. Using `docker build` directly gives full control
> over the tag.

If you prefer to use Compose, you can still build then retag:

```bash
docker compose build
docker tag lego-inventory-analyzer-lego-inventory carlwainwright/lego-inventory:0.2
docker tag lego-inventory-analyzer-lego-inventory carlwainwright/lego-inventory:latest
```

---

## 3. Verify the image locally

Confirm the image was built and check its size:

```bash
docker images carlwainwright/lego-inventory
```

Spin it up using Docker Compose to verify it works exactly as it will in
production — volumes, environment variables and health check all included:

```bash
docker compose up
```

Visit [http://localhost:5000](http://localhost:5000) to confirm the app loads.
Press `Ctrl+C` to stop, then:

```bash
docker compose down
```

---

## 4. Push to Docker Hub

Push the versioned tag:

```bash
docker push carlwainwright/lego-inventory:0.2
```

Push the `latest` tag if you applied it:

```bash
docker push carlwainwright/lego-inventory:latest
```

---

## 5. Verify on Docker Hub

Open [https://hub.docker.com/r/carlwainwright/lego-inventory/tags](https://hub.docker.com/r/carlwainwright/lego-inventory/tags)
and confirm tag `0.2` appears.

---

## Pulling and running on another machine

Update `docker-compose.yml` to pull from Docker Hub instead of building
locally by replacing the `build` block with an `image` reference:

```yaml
services:
  lego-inventory:
    image: carlwainwright/lego-inventory:0.2   # ← replace build: block with this
    container_name: lego-inventory
    restart: on-failure
    ...
```

Then pull and start:

```bash
docker compose pull
docker compose up -d
```

To update to a newer tag later, change the version in `docker-compose.yml`
and run `docker compose pull && docker compose up -d` again.

---

## Multi-platform build (optional)

If you need the image to run on both Intel (amd64) and Apple Silicon (arm64):

```bash
docker buildx create --use
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t carlwainwright/lego-inventory:0.2 \
  -t carlwainwright/lego-inventory:latest \
  --push \
  .
```

This builds and pushes in one step — no separate `docker push` needed.

---

## Tag reference

| Tag    | Notes                        |
|--------|------------------------------|
| `0.1`  | Initial release              |
| `0.2`  | Inventory DB, import, search |
| `latest` | Always points to most recent stable |