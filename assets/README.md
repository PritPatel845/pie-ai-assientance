# Third-party model notices

## MediaPipe Hand Landmarker (float16, version 1)

- Upstream: Google AI Edge / MediaPipe
- Official URL: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
- Expected size: 7,819,105 bytes
- SHA-256: `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`
- License: Apache License 2.0 (Google MediaPipe model distribution)
- Model overview: https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker

The model is not currently committed in this repository. Download it explicitly with
`scripts/download_model.sh`; it tries the official Google URL first and then a Hugging Face
mirror containing the byte-identical model. Both sources must pass the exact byte-size and
SHA-256 checks before the file is moved into `assets/hand_landmarker.task`. Do not bypass
this check.

Verified mirror: https://huggingface.co/Leo-TX/mediapipe-hand/resolve/main/hand_landmarker.task

Model checksum corroboration: Google's canonical model URL is used by the official
MediaPipe examples; independent copies of this exact model report the same SHA-256.
