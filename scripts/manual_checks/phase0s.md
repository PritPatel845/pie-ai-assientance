# Phase 0S manual hardware checks

Run only on the target Mac after installing the [mac] extra and granting permissions.

1. Run `.venv/bin/python -m pie --no-actions --no-voice`.
2. Confirm the camera preview opens and the HUD updates for palm, fist, pinch, thumb up/down,
   two-, three-, and four-finger poses.
3. Press q; confirm the preview closes and the camera indicator turns off.
4. In a safe environment, run without `--no-actions`, hold an open palm for two seconds,
   move the cursor, and pinch to double-click.
5. Confirm the application has Camera and Accessibility permissions for the Python executable.
6. Verify quitting always releases held game keys and closes the camera.
