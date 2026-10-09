set -ex

# build image (single tag; docker-compose references flow-llmops-web:latest)
docker build -f Dockerfile -t flow-llmops-web:latest .