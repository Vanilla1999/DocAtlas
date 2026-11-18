# v18 numerical QA — Blender 5.3.0

Audit script: `source/audit_v18.py`. Full evidence: `source/audit_v18.json`.

| Structural check | Observed result |
| --- | --- |
| Blender executable used for final build and test | **5.3.0**, Linux release |
| Armature | 38 bones, named `ARM_Plush_v18_ReferenceMatch` |
| Main core pieces | 10 (torso, head, 2 arms, 2 single-piece hands, 2 legs, 2 coherent feet) |
| Core geometry in evaluated view | 86,944 triangles (with Catmull-Clark); **not runtime LOD** |
| Main core mesh manifold/boundary errors | **0** on all 10 core pieces |
| Core zero-area faces and nonfinite vertices | **0** on all 10 |
| Core unweighted vertices | **0** |
| Core weights >4 influences, normalization failures | **0** |
| Noncoplanar self-intersections at neutral pose | **0** in the within-object probe on all 10 core pieces |
| Root/whole-rig movement error | ~`1e-7` to `4e-7` meters per core mesh (floating-point range) |

## Deformation stress, limitations

In the automated 90-degree elbow bend, about **1.95% of evaluated arm edges** grow by a factor above `2.0`, and the 99th percentile edge stretch is ~`2.35×`. At 120 degrees the corresponding fraction is ~**2.78%** and the 99th percentile stretch ~`2.79×`. This is an improvement in weighting but still shows the need for corrective shapes / improved bend loops before production animation.

The automated crouch pose produces about **1.33%** of evaluated leg edges above `2×` stretch. Other tested cases include arm reach/raise, finger curl, ear bend and jaw-bone manipulation; the **visual quality of each pose is not certified** by these numeric checks.

The original v17 actions remain for historical reference only. They were not retargeted to the new geometry, and new movement animation clips have not been approved. Root transform, static mesh topology and interpolation tests do not prove good walk cycle foot-locking.

## Reference-fit measurements (approximate)

The videos were inspected as three-view concepts. Their geometry is not metrically calibrated and sometimes varies frame-to-frame. Ratios below use the chosen v18 model proportions:

| Landmark ratio | v18 model | Broad source-video target |
| --- | ---: | ---: |
| Head width / crown-to-floor height | `1.58 / 4.78 = .331` | `.31–.34` |
| Head height / crown-to-floor height | `1.44 / 4.78 = .301` | `.29–.32` |
| Torso max width / head width | `1.24 / 1.58 = .785` | `.74–.82` |
| Shoulder to finger end / crown-to-floor | ~`2.21 / 4.78 = .462` | `.43–.47` |
| Hand length / head width | ~`.85 / 1.58 = .538` | `.48–.57` |
| Glowing eye diameter / head width | `.206 / 1.58 = .130` | `.12–.15` |
| Eye-center spacing / head width | `.59 / 1.58 = .373` | `.34–.38` |
| Wide mouth width / head width | `1.356 / 1.58 = .858` | `.80–.92` |

These ratios do **not** certify character likeness. Orthographic front/side/back images accompany the test for that necessary visual review.

## Remaining to certify

- UV unwrap, texture/normal bake, Roblox runtime mesh budget and true LODs.
- Deformation correctives for 90–120° elbows, knees, low crawl and ledge reach.
- Physical/clipping contacts between separate sewn overlays and the core mesh during poses.
- Rigged finger grasp and foot roll; ground support, no-slide contact in animation.
- Roblox Studio import and animation-state-machine implementation.
