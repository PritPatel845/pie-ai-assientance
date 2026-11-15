# Third-party model notices

## MediaPipe Hand Landmarker (float16, version 1)

- Upstream: Google AI Edge / MediaPipe
- Official URL: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
- Expected size: 7,819,105 bytes
- SHA-256: `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`
- License: Apache License 2.0 (Google MediaPipe model distribution)
- Model overview: https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker

The model is committed at `assets/hand_landmarker.task` (7,819,105 bytes). The commit was
created by the model-asset CI job only after the official Google download passed the exact
size and SHA-256 checks. The optional `scripts/download_model.sh` downloader tries the
official Google URL first and then a Hugging Face mirror; either source must pass both
checks before the file is accepted.

Verified mirror: https://huggingface.co/Leo-TX/mediapipe-hand/resolve/main/hand_landmarker.task
Model license statement: https://huggingface.co/Leo-TX/mediapipe-hand/blob/main/README.md

Model checksum corroboration: Google's canonical model URL is used by the official
MediaPipe examples; independent copies of this exact model report the same SHA-256.
