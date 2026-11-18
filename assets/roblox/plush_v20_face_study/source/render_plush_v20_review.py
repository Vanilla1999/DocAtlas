"""Read-only matched-angle review of the saved v20 model in Blender 5.3."""
import argparse
import sys
from pathlib import Path
import bpy

ROOT=Path(__file__).resolve().parent
argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
parser=argparse.ArgumentParser()
parser.add_argument('--blend',type=Path,default=ROOT/'plush_v20'/'Plush-v20-Face-Study.blend')
parser.add_argument('--output-dir',type=Path,default=ROOT/'plush_v20')
options,_=parser.parse_known_args(argv)
OUT=options.output_dir.resolve()
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
scene=bpy.context.scene;rig=bpy.data.objects['ARM_Plush_v20']
quick='--quick' in sys.argv
scene.cycles.samples=24 if quick else 64
scene.cycles.use_denoising=True
scene.render.resolution_x=840 if quick else 1200
scene.render.resolution_y=scene.render.resolution_x
shots=[('front',1,'front_open'),('hero',1,'hero_open'),('profile',1,'profile_open'),
       ('reference_side',1,'reference_side'),('front',0,'front_closed'),
       ('front',.5,'front_half'),('mouth',1,'mouth_detail'),('full',1,'full_open')]
if quick:shots=[('front',1,'front_open'),('hero',1,'hero_open'),('profile',1,'profile_open'),('front',0,'front_closed')]
if '--single-front' in sys.argv:shots=[('front',1,'front_open')]
if '--single-hero' in sys.argv:shots=[('hero',1,'hero_open')]
if '--mouth-detail' in sys.argv:shots=[('mouth',1,'mouth_detail')]
if '--study' in sys.argv:shots=[('hero',1,'hero_open'),('reference_side',1,'reference_side'),('mouth',1,'mouth_detail')]
if '--clay' in sys.argv:
    for collection in bpy.data.collections:
        if collection.name.startswith('V20_07'):collection.hide_render=True
    clay=bpy.data.materials.new('QA_Clay_Only');clay.diffuse_color=(.37,.37,.37,1)
    clay.use_nodes=True
    p=clay.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(.37,.37,.37,1)
    p.inputs['Roughness'].default_value=.78
    scene.view_layers[0].material_override=clay
    shots=[('front',1,'clay_open'),('front',0,'clay_closed'),('profile',1,'clay_profile')]
for camera,value,label in shots:
    rig['MouthOpen']=value;rig.update_tag();bpy.context.view_layer.update()
    scene.camera=bpy.data.objects['CAM_V20_'+camera]
    bpy.data.objects['Studio_Ground_NotAsset'].visible_camera=(camera=='full')
    scene.render.filepath=str(OUT/f'v20_{label}.png')
    bpy.ops.render.render(write_still=True)
print('V20_REVIEW_RENDER_DONE')
