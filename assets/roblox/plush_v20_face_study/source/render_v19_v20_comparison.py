"""Read-only matched-camera comparison. Run in Blender 5.3 with explicit inputs.

Both scenes use their identical studio light/world setup. Camera, resolution,
samples, color management and compositor bypass are forced to match.
Input files are hashed before and after; this script never saves a .blend.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument('--v19', required=True, type=Path)
    parser.add_argument('--v20', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--quick', action='store_true')
    opts = parser.parse_args(args)
    opts.output_dir.mkdir(parents=True, exist_ok=True)
    report = {'runtime_blender': bpy.app.version_string,
              'description': 'Matched camera and render settings; native materials and geometry; compositor bypassed equally.',
              'camera_location': [-0.9, -9.0, 4.10], 'camera_target': [0, 0, 4.10],
              'orthographic_scale': 2.25, 'models': {}}
    lighting = []
    for label, path in [('v19', opts.v19), ('v20', opts.v20)]:
        path = path.resolve()
        before = sha256(path)
        bpy.ops.wm.open_mainfile(filepath=str(path))
        scene = bpy.context.scene
        rig = bpy.data.objects['ARM_Plush_' + label]
        if rig.animation_data:
            rig.animation_data.action = None
        rig['MouthOpen'] = 1.0
        rig.update_tag()
        bpy.context.view_layer.update()
        light_state = [{'name': o.name, 'type': o.data.type,
                        'location': list(o.location), 'rotation': list(o.rotation_euler),
                        'energy': o.data.energy, 'color': list(o.data.color),
                        'size': o.data.size}
                       for o in sorted(bpy.data.objects, key=lambda x: x.name)
                       if o.type == 'LIGHT']
        lighting.append(light_state)
        camera_data = bpy.data.cameras.new('QA_MatchedFaceCamera')
        camera_data.type = 'ORTHO'
        camera_data.ortho_scale = 2.25
        camera = bpy.data.objects.new('QA_MatchedFaceCamera', camera_data)
        scene.collection.objects.link(camera)
        camera.location = (-.9, -9, 4.10)
        camera.rotation_euler = (Vector((0, 0, 4.10))-camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.camera = camera
        ground = bpy.data.objects.get('Studio_Ground_NotAsset')
        if ground:
            ground.visible_camera = False
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = 24 if opts.quick else 48
        scene.cycles.use_denoising = True
        scene.cycles.seed = 23
        scene.render.resolution_x = 800 if opts.quick else 1100
        scene.render.resolution_y = scene.render.resolution_x
        scene.render.resolution_percentage = 100
        scene.render.use_compositing = False
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0
        scene.render.image_settings.file_format = 'PNG'
        image_path = opts.output_dir / (label + '_matched_face.png')
        scene.render.filepath = str(image_path.resolve())
        bpy.ops.render.render(write_still=True)
        after = sha256(path)
        if before != after:
            raise RuntimeError('Input file changed: ' + str(path))
        report['models'][label] = {'file': str(path), 'sha256_before': before,
                                  'sha256_after': after, 'unchanged': True,
                                  'render': image_path.name, 'lights': light_state}
    report['identical_studio_lights'] = lighting[0] == lighting[1]
    if not report['identical_studio_lights']:
        raise RuntimeError('Studio light settings differ; do not label images matched lighting.')
    with (opts.output_dir/'matched_render_report.json').open('w', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print('MATCHED_COMPARISON_DONE', json.dumps({
        'identical_studio_lights': True,
        'sha256': {key: value['sha256_after'] for key, value in report['models'].items()}}))


if __name__ == '__main__':
    main()
