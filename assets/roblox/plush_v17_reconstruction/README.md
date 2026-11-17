# Plush monster — Blender reconstruction v17

This is a **new approximation** of the plush rabbit monster based on the surviving textual project notes. The original `Plush-v16-Paw-Fix.blend` and reference videos were unavailable. This file is **not a byte-for-byte restoration** and has not been visually approved against the lost concept.

## Files

- `Plush-v17-Reconstruction.blend`: editable Blender scene, geometry, materials, skeleton and four actions.
- `recover_plush_v17.py`: deterministic script that recreates the scene using Blender Python; no external textures or add-ons.
- `Plush-v17-*.png`: rendered Blender previews, not AI concept pictures.
- `QA-Reconstruction-v17.json`: structural and basic motion checks.

## In Blender

Tested in Blender **4.3.2**. Open the `.blend`, select `ARM_Recovered_Plush_v17`, and choose an action in the Dope Sheet → Action Editor:

| Action | Frames | Purpose |
| --- | --- | --- |
| `AN_v17_Walk_InPlace_40f_24fps` | 1–41 | Stylized slow walk loop, root stays in place |
| `AN_v17_Idle_Breath_96f` | 1–97 | Subtle breathing and ear lag |
| `AN_v17_Alert_32f` | 1–33 | Quick attention response |
| `AN_v17_Jaw_Open_Close_32f` | 1–33 | Operable jaw |

The `03 • Photo studio` collection is only for renders. Exclude it from game exports. Pose bones allow moving the whole body, fingers, ears and the lower jaw.

## Design restored from notes

- Indigo textile material, asymmetric long ears and circular luminous eyes.
- Rounded head, embroidered grin, teeth and movable lower jaw.
- Large cloth sleeves, palms, three soft fingers plus a thumb, and padded short feet.
- Belly patch with visible stitches and a small stuffed tail.

## Known limitations

- Silhouette, eye placement and exact proportions cannot be verified against the missing original video.
- It is an editable **reconstruction draft**, **not game-ready**. The topology is made of overlapping soft pieces; intersections and extreme poses need more refinement.
- The walk is authored **in-place** as a first pass, without IK foot pinning; contact and acceleration need rework after receiving a new visual reference.
- No Roblox Studio import, collision, performance budget, facial blend shapes or FBX export has been approved.

After a new reference image/video is provided, the next pass should prioritize hand/foot silhouettes, head-to-body ratio, and a side-view contact-locked crawl/walk.
