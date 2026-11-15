#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$ROOT/assets/hand_landmarker.task}"
URL="https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MIRROR_URL="https://huggingface.co/Leo-TX/mediapipe-hand/resolve/main/hand_landmarker.task"
EXPECTED_BYTES=7819105
EXPECTED_SHA256="fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"

mkdir -p "$(dirname "$DEST")"
TEMP="${DEST}.tmp"
trap 'rm -f "$TEMP"' EXIT

VERIFIED=0
for SOURCE_URL in "$URL" "$MIRROR_URL"; do
  echo "Downloading candidate model from: $SOURCE_URL"
  if ! curl --fail --location --retry 2 --connect-timeout 15 --max-time 120 \
    "$SOURCE_URL" --output "$TEMP"; then
    echo "Download failed; trying the next source..." >&2
    rm -f "$TEMP"
    continue
  fi

  ACTUAL_BYTES="$(wc -c < "$TEMP" | tr -d '[:space:]')"
  if [[ "$ACTUAL_BYTES" != "$EXPECTED_BYTES" ]]; then
    echo "Rejected candidate: expected $EXPECTED_BYTES bytes, got $ACTUAL_BYTES" >&2
    rm -f "$TEMP"
    continue
  fi

  ACTUAL_SHA256="$(shasum -a 256 "$TEMP" | awk '{print $1}')"
  if [[ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]]; then
    echo "Rejected candidate: SHA-256 mismatch ($ACTUAL_SHA256)" >&2
    rm -f "$TEMP"
    continue
  fi

  mv "$TEMP" "$DEST"
  VERIFIED=1
  echo "Verified model: $DEST"
  echo "Source: $SOURCE_URL"
  echo "Bytes: $ACTUAL_BYTES"
  echo "SHA-256: $ACTUAL_SHA256"
  break
done

if [[ "$VERIFIED" != "1" ]]; then
  echo "ERROR: no model source returned the pinned, verified binary" >&2
  exit 1
fi
