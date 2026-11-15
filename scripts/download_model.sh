#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$ROOT/assets/hand_landmarker.task}"
URL="https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
EXPECTED_BYTES=7819105
EXPECTED_SHA256="fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"

mkdir -p "$(dirname "$DEST")"
TEMP="${DEST}.tmp"
trap 'rm -f "$TEMP"' EXIT

echo "Downloading the pinned MediaPipe Hand Landmarker model from the official Google URL..."
curl --fail --location --retry 2 --connect-timeout 15 --max-time 120 "$URL" --output "$TEMP"

ACTUAL_BYTES="$(wc -c < "$TEMP" | tr -d '[:space:]')"
if [[ "$ACTUAL_BYTES" != "$EXPECTED_BYTES" ]]; then
  echo "ERROR: model size mismatch (expected $EXPECTED_BYTES, got $ACTUAL_BYTES bytes)" >&2
  exit 1
fi

ACTUAL_SHA256="$(shasum -a 256 "$TEMP" | awk '{print $1}')"
if [[ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]]; then
  echo "ERROR: model SHA-256 mismatch (got $ACTUAL_SHA256)" >&2
  exit 1
fi

mv "$TEMP" "$DEST"
echo "Verified model: $DEST"
echo "Bytes: $ACTUAL_BYTES"
echo "SHA-256: $ACTUAL_SHA256"
