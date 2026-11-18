# v19 — independent geometry checks and review limits

The delivered `.blend` was reopened in the **official Blender 5.3.0 Linux build** (`02f0899d78e3`) and tested read-only. Its internal file version is `[5, 3, 31]` (the last value is Blender's file subversion, not a different application release).

SHA-256 of `Plush-v19-Mouth-Refinement.blend`:

```text
b0501650b048ac5dde37cfb5e1e9bb864e7dd46c6d0407e6000a0c3ceb731ca5
```

Both auditors checked the input checksum before and after; neither changed the model. Renders are made by reopening the saved file in a separate read-only process.

The preview renderer hides the finite studio floor from closeup camera rays and extends it for the full-body shot to avoid a distracting background horizon. These presentation-only changes do not alter the character or the saved file.

## Mouth deformation — 41 states

The independent mouth auditor sampled `MouthOpen = 0, 0.025, …, 1`. It checked the evaluated head, soft inner-lip closure and both dental arches. The retained torso and new neck were additionally checked for topology, normalized skinning, rig transform following and visibility through the lower aperture.

| Check | Observed result |
| --- | --- |
| Self-crossings of head / inner closure / upper teeth / lower teeth | 0 confirmed noncoplanar crossings in every sampled state |
| Upper versus lower tooth crossings | 0 in every sampled state |
| Free tooth tips versus head or inner closure | 0 confirmed crossings in every sampled state |
| Intersection candidate truncation | None; all candidate sets examined |
| Closed-mouth enamel visibility | 0 tooth-first hits among 46,995 rays, split across −15°, 0°, +15° yaw |
| Torso or neck visible through lower mouth | 0 body-first hits at all 41 states from those three yaw views |
| Tested six structural meshes | 0 nonmanifold edges, 0 zero-area base faces |
| Evaluated facial meshes | 0 nonfinite vertices, 0 zero-area triangles |
| Maximum mirrored-head vertex error | 0.00000477 Blender units |
| Maximum aperture X-midline offset | 0.0000000596 Blender units |
| Maximum rig-transform following error | 0.000000259 Blender units |

The collision probe uses actual triangle intersection tests, not just overlapping bounding boxes. Coplanar contacts and shared-vertex triangles are not certified. The free-tip test intentionally excludes embedded tooth roots. The visibility probe tests evaluated structural surfaces, not every curled textile instance. Passing samples are evidence of the tested configurations, **not proof for every continuous intermediate pose or every camera angle**.

## Shape measurements

These are evaluated geometry measurements, not a claimed percentage of visual similarity:

| Measurement | Result |
| --- | --- |
| Open aperture height / width | 0.749 |
| Closed head height / width, excluding ears | 0.899 |
| Open head height / width, excluding ears | 1.137 |
| Outer chin downward travel | 0.381 Blender units |
| Top-of-head vertical change | 0.000394 Blender units |
| Head control mesh | 3,746 vertices; 3,840 faces; 95% quads |

The image-derived target ratios in `source/reference_mouth_spec.json` are approximate and affected by perspective. They help guide the silhouette; they are not calibrated reconstruction data.

## Whole-scene inventory

`qa/audit_scene_v19.json` checks 54 character control meshes, excluding the studio, procedural-fleece hosts and fibre seed.

- 23,950 base vertices, 23,828 base faces, 45,936 triangulated base faces.
- 38 bones, one `Root`, all inspected character meshes parented to the armature and carrying its modifier.
- No unweighted vertices, no weight-normalization errors, at most two deform-bone influences per vertex.
- No nonfinite vertices or zero-area base faces.
- No external unpacked image dependencies.

These counts **do not include evaluated subdivision or procedural fleece** and must not be used as a Roblox runtime polygon budget.

### Known inherited decorative topology

The full scene is not claimed to be watertight. Older v18 stitch tubes, toe-cleft overlays and the belly inlay retain **1,664 boundary edges in total**; the belly inlay also retains **48 zero-length edges**. There are no wire or overconnected edges in those items. These are separate decorative surfaces, not the rebuilt structural head, dental arches, torso or neck. They should be baked, omitted or cleaned as part of a deliberate game-LOD/export pass.

## Visual review and remaining work

The actual model was reviewed in closed, intermediate and open front views, an open profile, a three-quarter close-up and a full-body view. Numerical checks caught tooth/cavity conflicts and the retained torso intruding into the mouth; visual checks additionally caught fleece around the eyes and the overly bright folded-ear lining.

This is an iterative art revision, not an exact match to the reference. Fleece softness, dental asymmetry and the body/hand/foot treatment can still receive an art pass. The older `LEGACY_` animation clips remain unretargeted. UV/bake work, an explicit LOD budget, engine import, movement retargeting and all-pose stress tests have **not** been completed or certified.

## Reproduce

See the commands in `README.md`. Detailed evidence is in:

- `qa/audit_mouth_v19_dense.json` — every sampled mouth state, intersections, symmetry, visibility and checksums;
- `qa/audit_scene_v19.json` — per-object topology, hierarchy, weights and scene dependencies.
