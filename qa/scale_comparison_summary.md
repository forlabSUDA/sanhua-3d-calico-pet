# Scale Comparison Summary

Scope: one stable repair pass on the existing 3D calico materials.

Rules enforced:
- per-frame autoscale: disabled
- per-frame bbox fit: disabled
- per-frame recentering: disabled
- row-level scale/baseline/anchor: enabled
- cross-row global visual scale harmonization: enabled

| row | area before | area after | median bbox before | median bbox after | applied factor | min margin after |
| --- | ---: | ---: | --- | --- | ---: | ---: |
| idle | 16415.0 | 11191.0 | 164.0x190.5 | 134.5x157.5 | 0.826016 | 8 |
| running-right | 7281.5 | 7281.5 | 182.0x85.5 | 182.0x85.5 | 1.0 | 4 |
| running-left | 7281.5 | 7281.5 | 182.0x85.5 | 182.0x85.5 | 1.0 | 4 |
| waving | 13232.0 | 11227.5 | 174.0x179.5 | 160.0x165.0 | 0.920018 | 8 |
| jumping | 9874.0 | 9466.0 | 177.0x127.0 | 173.0x124.0 | 0.98 | 7 |
| failed | 10648.0 | 10883.5 | 181.0x96.0 | 183.0x97.0 | 1.01087 | 2 |
| waiting | 13407.0 | 11221.0 | 136.0x188.0 | 124.0x172.0 | 0.913994 | 8 |
| running | 20479.5 | 11221.5 | 177.0x174.5 | 131.0x129.0 | 0.74 | 8 |
| review | 13958.0 | 11199.0 | 130.0x193.0 | 115.0x173.0 | 0.895772 | 8 |

Interpretation:
- Standing/sitting rows were gently reduced where they visually dominated the atlas.
- Running rows were kept at the largest safe row-level size because their full side profile already nearly fills the 192 px width.
- Lying rows keep natural low height but are not separately autoscaled per frame.
- Remaining scale differences are posture-driven, not per-frame zoom popping.
