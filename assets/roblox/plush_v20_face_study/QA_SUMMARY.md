# V20 — structural QA summary

The exact model below passes the measured mouth-state checks. **Numeric QA is not approval of artistic likeness, Roblox export readiness, or locomotion.**

- Model: `Plush-v20-Face-Study.blend`
- Blender runtime: **5.3.0**; internal saved-file version: `[5, 3, 31]`.
- Evidence: [dense mouth audit](qa/audit_mouth_v20_dense.json) and [scene inventory](qa/audit_scene_v20_final.json).
- Both audits verified the same SHA-256 before and after; neither saved or altered the model.

```text
4ca344d47d4c44ec8944bfed6c0667894cfae4ae6c5da774d88b4051fd9f5674
```

## Measured results

The mouth audit uses the neutral skeletal pose and drives `ARM_Plush_v20["MouthOpen"]`. The five facial meshes are the head shell, inner lip seal, cloth tongue, and two tooth arches. The arches contain 11 upper and 13 lower tooth components.

| Test | Measured result |
|---|---|
| Mouth positions | **41**, from 0 to 1 inclusive, step 0.025 |
| Facial self-crossings | **0** confirmed strict noncoplanar crossings |
| Upper-versus-lower tooth crossings | **0** |
| Exposed tooth-tip crossings against head, seal or tongue | **0** |
| Intersection candidate coverage | **All candidates examined**; no probe was truncated by its 12,000-pair cap |
| Retained torso/neck visible through lower mouth | **0 of 832,017** sampled rays hit torso or neck first |
| Enamel visible through the closed seam | **0 of 46,995** sampled rays hit a tooth first |
| Facial base topology | All five meshes have **0 nonmanifold edges, zero-area faces and zero-length edges** |
| Evaluated facial geometry across 41 positions | **0 nonfinite vertices; 0 zero-area triangles** |
| Skinning across 56 scene asset meshes | **0 unweighted vertices, over-four-influence vertices or normalization errors**; maximum observed influences: **2** |
| Rig-transform follow | Maximum rig-local deviation **2.59 × 10⁻⁷** |
| Sampled exposed-tip distance to soft tissue | Minimum unsigned distance **0.008420** scene units; not a signed penetration or full clearance certificate |

The dense mouth audit completed in 55.8 seconds. All distances and coordinates are rig-local scene units; conversion to engine or physical units was not validated.

## Definitions and thresholds

- **Topology:** an edge is flagged as nonmanifold when it belongs to other than two faces. Zero-area faces/triangles use an area threshold of `1e-12`; zero-length base edges use `1e-7`.
- **Weights:** deform-bone weights greater than `1e-7` are counted. A normalization error means the sum differs from 1 by more than `1e-4`; more than four influences is flagged.
- **Crossings:** BVH candidate pairs undergo strict noncoplanar triangle tests. Self-tests exclude triangles sharing vertices. Coplanar overlap, exact contact and segment endpoints are not certified. The scripts define geometric tolerances; the reports record candidate coverage.
- **Tooth tips:** `QA_FreeToothTips` identifies exposed tips. Only triangles entirely inside this selection enter tip-crossing tests; intentionally embedded roots are excluded. Unsigned distance checks sample 1,771 upper and 2,093 lower evaluated tip vertices per state.
- **Visibility:** orthographic views use yaw −15°, 0° and +15°. Closed-seam probes use a 241 × 65 grid per view. Body probes use a 161 × 65 grid clipped to the lower 55% of the projected evaluated aperture-contour convex hull at each state. A first-hit count measures sampled occlusion, not exhaustive visibility.

## Known limitations and retained findings

The **whole scene is not claimed to be manifold**. Its inherited decorative seam/inlay meshes retain **1,664 boundary edges**. `V20_OrganicSewnBellyInlay` also retains **48 zero-length center edges**. These findings are included in the scene report and are separate from the clean facial cores.

Cosmetic fleece hosts, all `V20_BoucleTuftSeed*` rendering seeds and studio geometry are excluded from structural inventory/weight claims. Instanced fibre collisions and evaluated render polygon budgets are not certified. Separate soft-tissue attachments and embedded roots can intentionally overlap.

The results cover the sampled mouth states and views, not continuous motion, every viewing direction, skeletal stress poses or the full-body collision envelope. They do not validate UVs, baking, engine import, performance, animation quality, or resemblance to the reference. Artistic review remains a separate acceptance step.
