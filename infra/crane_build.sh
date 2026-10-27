#!/usr/bin/env bash
# Daemonless image build for machines without docker/podman and subscriptions without ACR Tasks
# (Azure for Students). Appends one layer (pip deps pinned to the base image's versions + the app code)
# onto the previous image with `crane` (github.com/google/go-containerregistry).
# Usage: BASE_IMAGE=<acr>.azurecr.io/echo-pitch:<old> NEW_IMAGE=<acr>.azurecr.io/echo-pitch:<tag> infra/crane_build.sh
set -euo pipefail
CRANE=${CRANE:-crane}
PY=${PY_VER:-3.12}
work=$(mktemp -d)
site="$work/root/usr/local/lib/python$PY/site-packages"
mkdir -p "$site" "$work/root/app"
# pin every package already in the base image to its exact version
"$CRANE" export "$BASE_IMAGE" - | tar t 2>/dev/null | grep -o "site-packages/[^/]*\.dist-info" | sort -u |
  sed -E 's#site-packages/(.*)-([^-]+)\.dist-info#\1==\2#' > "$work/constraints.txt"
grep -v '^#' requirements.txt | grep -v '^pytest' > "$work/req.txt"
pip install -q --no-compile --target "$site" --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 \
  --python-version "$PY" --only-binary=:all: -c "$work/constraints.txt" -r "$work/req.txt"
cp -r generator analytics agents app echo_mcp web data "$work/root/app/"
find "$work/root" -name __pycache__ -prune -exec rm -rf {} +
tar -C "$work/root" --owner=0 --group=0 -cf "$work/layer.tar" usr app
"$CRANE" append -b "$BASE_IMAGE" -f "$work/layer.tar" -t "$NEW_IMAGE"
echo "pushed $NEW_IMAGE"
