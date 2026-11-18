"""Read-only scene inventory and base-topology/weight audit; not a game export test."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_mouth_v19 import base_mesh_checks


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument('blend')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    path = Path(args.blend).resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(path))
    rig = bpy.data.objects['ARM_Plush_v19']
    meshes = [o for o in bpy.context.scene.objects
              if o.type == 'MESH' and o.name.startswith('V19_')
              and not o.name.startswith('V19_Fleece_')
              and o.name != 'V19_BoucleTuftSeed']
    details = {o.name: base_mesh_checks(o, rig) for o in meshes}
    attributes = ('vertices', 'faces', 'triangles', 'nonmanifold_edges',
                  'zero_area_faces', 'zero_length_edges', 'nonfinite_vertices')
    totals = {key: sum(d[key] for d in details.values()) for key in attributes}
    weight_totals = {key: sum(d['weights'][key] for d in details.values())
                     for key in ('unweighted_vertices', 'over_four_influences',
                                 'normalization_errors_gt_1e_4')}
    weight_totals['maximum_influences'] = max(d['weights']['maximum_influences'] for d in details.values())
    external_images = []
    for img in bpy.data.images:
        if img.source == 'FILE' and img.filepath and not img.packed_file:
            external_images.append({'name': img.name, 'path': img.filepath,
                                    'exists': Path(bpy.path.abspath(img.filepath)).exists()})
    report = {
        'file': str(path), 'runtime_blender': bpy.app.version_string,
        'saved_file_version': list(bpy.data.version),
        'sha256': digest, 'input_blend_unchanged': hashlib.sha256(path.read_bytes()).hexdigest() == digest,
        'asset_mesh_objects': len(meshes), 'armature_bones': len(rig.data.bones),
        'root_bones': [b.name for b in rig.data.bones if b.parent is None],
        'base_mesh_totals': totals, 'weight_totals': weight_totals,
        'objects_without_rig_parent': [n for n, d in details.items() if not d['parent_chain_reaches_rig']],
        'objects_without_target_armature_modifier': [n for n, d in details.items() if rig.name not in d['armature_modifiers']],
        'external_unpacked_image_dependencies': external_images,
        'procedural_fleece_hosts': [o.name for o in bpy.context.scene.objects if o.name.startswith('V19_Fleece_')],
        'actions': [a.name for a in bpy.data.actions],
        'meshes': details,
        'limitations': [
            'Base/control mesh counts, not evaluated subdivision or instanced-fleece polygon budgets.',
            'Decorative fleece hosts/seed and studio geometry excluded from topology and weights.',
            'No collision or stress-pose certificate for the full body.',
            'Does not certify UVs, baked maps, Roblox import, animation quality or artistic likeness.'
        ]
    }
    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('SCENE_QA', json.dumps({key: value for key, value in report.items()
                                if key not in ('meshes', 'procedural_fleece_hosts', 'actions')}))


if __name__ == '__main__':
    main()
