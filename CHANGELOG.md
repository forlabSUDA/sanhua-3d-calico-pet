# Motionfix All Changelog

- Froze the selected 3D calico cat visual identity.
- Stopped using optical flow as the primary motion source.
- Added key-pose-first processing for all 9 Codex states.
- Rebuilt running-right and running-left with a 2.5D body/leg/tail rig.
- Added measured before/after scale audits and one global row-level visual harmonization pass.
- Simplified waiting to stretch-only in the Codex row and review to one seated observation loop.
- Kept final Codex atlas at 1536x1872, 8x9, 192x208 cells.
- Did not install or overwrite the current Codex pet.

## Per-row pipeline
- idle: clean key poses -> hold/ease master -> codex sampling
- running-right: clean key poses -> 2.5D body/leg/tail rig -> 32-frame master -> codex sampling
- running-left: mirrored 2.5D repaired running-right rig
- waving: clean key poses -> hold/ease master -> codex sampling
- jumping: clean proportional jump key poses -> 24-frame master -> 5-frame Codex row
- failed: full-body sad sit -> sink -> readable side-roll key poses -> 24-frame master -> 8-frame Codex row
- waiting: clean stretch key poses -> 24-frame master -> 6-frame Codex sampling
- running: clean key poses -> hold/ease master -> codex sampling
- review: clean seated observation key poses -> 16-frame master -> 6-frame Codex sampling
