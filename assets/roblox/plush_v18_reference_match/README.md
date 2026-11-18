# Plush v18 — Reference Match (Blender 5.3)

Rebuilt and substantially remodeled from the surviving v17 plush creature, guided by **four user-provided movement-concept videos**. This is a reviewable **model/detail and rig-structure pass**, not a claim that the walk/climb animation or Roblox export is finished.

## Open immediately

Open `Plush-v18-Reference-Match.blend` in **Blender 5.3.0**. Its stored scene has the monster in a three-quarter-open, toothy expression and a neutral A-like stance. It is self-contained and does **not** depend on an external image texture, add-on, or an earlier `.blend`.

The rig is named `ARM_Plush_v18_ReferenceMatch`. Select it and change **Custom Properties → MouthOpen** from `0` (seamlike closed mouth) to `1` (wide gape). The mouth opening is a true connected facial surface with a closed inner cavity and driven, irregular ivory teeth, not a black sticker.

## What changed from v17

- Reworked upright torso and long leg proportions using reference-video crown/head/torso/hand ratios.
- Rebuilt full head with a continuous quad-majority mouth annulus, recessed tunnel and a deformable aperture. Removed muzzle/nose/pupils; added small inset warm cream eyes.
- Created non-segmented curved sleeves and **single-piece manifold palm/finger/thumb topology** per hand, with separate rigged palm pads, fingertip patches and tiny claws.
- Rebuilt plush paw feet as coherent meshes with three sculpted forward toe lobes, clefts, and an underside pad.
- Added a softened neck transition, asymmetrically bent pillow-like ears, a stitched belly inset, warm tan tacks, cheek seams, back seam and plush tail.
- Added procedural textile color variation, micro-bump, geometry-level fleece relief and a dedicated neutral preview studio.
- Preserved a 38-bone armature and kept the older v17 actions under `LEGACY_` names so they cannot be mistaken for newly retargeted animations.

## Contents

| Item | Purpose |
| --- | --- |
| `Plush-v18-Reference-Match.blend` | Main editable scene; Blender 5.3 file |
| `previews/` | Genuine Cycles Blender 5.3 renders: front, side, back, closed mouth and triptych |
| `QA_SUMMARY.md` | Numeric model/weight/deformation results and known remaining work |
| `source/build_plush_v18.py` | Entire Blender Python model builder |
| `source/audit_v18.py` | Read-only mesh/rig stress audit |
| `source/recover_plush_v17.py` | Earlier reconstruction generator, as historical provenance |
| `source/Plush-v17-Reconstruction.blend` | Rebuild input used by `build_plush_v18.py` |
| `source/reference_spec.json` | Quantitative, approximate source-video notes |
| `source/audit_v18.json` | Full machine-readable Blender 5.3 audit |

## Rebuild and retest

From this extracted directory, using Blender 5.3.0:

```bash
blender -b -t 4 --python source/build_plush_v18.py
blender -b -t 4 --python source/audit_v18.py -- source/plush_v18/Plush-v18-Reference-Match.blend
```

The builder expects the v17 input `.blend` alongside itself. It saves the new model and original Cycles preview renders to `source/plush_v18/` when launched from that `source/` directory. This is separate from the ready-to-open `.blend` at archive root.

## Export notes / remaining work

This Blender scene is a **high-detail master model**, not a pre-optimized Roblox mesh. Disable/exclude collection `V18_04 • preview studio / exclude from export`. Before production in Roblox Studio, make an explicitly budgeted LOD, bake the procedural boucle relief to UV maps/normal maps, reconcile finger and foot IK, make full animation clips, and test the resulting FBX/glTF inside Roblox. No such runtime tests or animation certification are claimed here.

Source v17 was a reconstruction of lost artwork, **not a recovery of the exact missing v16 bytes**. Source videos are interpreted artistic reference, not ground-truth multi-view 3D scans.
