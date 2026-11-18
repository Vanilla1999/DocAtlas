"""Render saved v19 model without changing its .blend bytes."""
import sys
from pathlib import Path
import bpy

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'plush_v19'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Plush-v19-Mouth-Refinement.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['ARM_Plush_v19']
quick='--quick' in sys.argv
scene.cycles.samples=28 if quick else 64
scene.cycles.use_denoising=True
scene.render.resolution_x=860 if quick else 1100
scene.render.resolution_y=scene.render.resolution_x
shots=[('front',1,'front_open'),('hero',1,'hero_open'),('profile',1,'profile_open'),
       ('front',0,'front_closed'),('front',.5,'front_half'),('full',1,'full_open')]
if quick:shots=[('front',1,'front_open'),('profile',1,'profile_open'),('front',0,'front_closed')]
if '--single-front' in sys.argv:shots=[('front',1,'front_open')]
if '--presentation' in sys.argv:shots=[('hero',1,'hero_open'),('full',1,'full_open')]
for camera,value,label in shots:
    rig['MouthOpen']=value;rig.update_tag();bpy.context.view_layer.update()
    scene.camera=bpy.data.objects['CAM_V19_'+camera]
    # Preview-only studio adjustment: remove the distant finite-plane horizon
    # from closeups; keep a larger shadow-receiving floor in the full-body shot.
    # No character geometry, material or saved .blend bytes are modified.
    ground=bpy.data.objects['Studio_Ground_NotAsset']
    ground.visible_camera=(camera=='full')
    ground.scale=(10,10,10)
    scene.render.filepath=str(OUT/f'v19_{label}.png')
    bpy.ops.render.render(write_still=True)
print('V19_REVIEW_RENDER_DONE')
