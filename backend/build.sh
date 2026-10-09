set -ex

# build image (single tag; docker-compose references flow-llmops-api:latest)
docker build -f Dockerfile -t flow-llmops-api:latest .