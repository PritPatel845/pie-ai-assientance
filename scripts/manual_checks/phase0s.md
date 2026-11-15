# Phase 0S manual hardware checks

Run only on the target Apple Silicon Mac after resolving the MediaPipe/OpenCV install
strategy and installing the \`[mac]\` extra. Grant Camera and Accessibility permissions
only when macOS prompts for them.

## Read-only preflight

1. Run \`scripts/manual_checks/audit_macos.command\`.
2. Confirm the report says \`arm64\`, Python 3.12, and that cv2, numpy, MediaPipe Tasks,
   PyAutoGUI, Quartz, and AppKit import successfully.
3. Confirm the PyAutoGUI \`playpause\` key is available.
4. Confirm \`assets/hand_landmarker.task\` reports 7,819,105 bytes and SHA-256
   \`fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1\`.
5. If any dependency/API check fails, stop and record the exact output; do not silently
   change the pinned package versions.

## Camera and gesture checks

1. Run \`.venv/bin/python -m pie --no-actions --no-voice\`.
2. Confirm the camera preview opens and the HUD updates for palm, fist, pinch, thumb up/down,
   two-, three-, and four-finger poses.
3. Press q; confirm the preview closes and the camera indicator turns off.
4. In a safe environment, run without \`--no-actions\`, hold an open palm for two seconds,
   move the cursor, and pinch to double-click.
5. Confirm the application has Camera and Accessibility permissions for the Python executable.
6. Verify quitting always releases held game keys and closes the camera.

## Media and app automation

1. With Spotify running, test the play and pause voice commands; repeat with Music running.
2. Verify the system \`playpause\` fallback when neither app is running.
3. Confirm screenshots are saved to the Desktop with the \`Pie Screenshot\` filename.
4. Verify open-app lookup only searches the four approved application roots.

Record macOS version, Python path/version, package versions, test results, and any failures
in \`docs/HANDOFF.md\`. Do not mark Phase 0S accepted until every item above passes.
