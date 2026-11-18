"""Read-only, rig-local v19/v20 form comparison; never a likeness percentage.

blender -b --python compare_face_metrics.py -- --v19 old.blend --v20 new.blend --output comparison.json
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


def bounds(points):
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    return {'min': lo, 'max': hi, 'dimensions_xyz': [hi[i]-lo[i] for i in range(3)]}


def snapshot(obj, rig):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    matrix = rig.matrix_world.inverted() @ evaluated.matrix_world
    points = [matrix @ v.co for v in mesh.vertices]
    triangles = [tuple(t.vertices) for t in mesh.loop_triangles]
    edges = [tuple(e.vertices) for e in mesh.edges]
    group = evaluated.vertex_groups.get('QA_MouthAperture')
    aperture = [points[v.index] for v in mesh.vertices
                if group and any(g.group == group.index and g.weight > .5 for g in v.groups)]
    evaluated.to_mesh_clear()
    return points, triangles, edges, aperture


def components(count, edges):
    parents = list(range(count))
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    for a, b in edges:
        a, b = root(a), root(b)
        if a != b:
            parents[b] = a
    sizes = sorted(Counter(root(i) for i in range(count)).values(), reverse=True)
    return {'count': len(sizes), 'vertex_counts': sizes}


def measure(path):
    path = path.resolve()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(path))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    heads = [o for o in meshes if o.get('qa_role') == 'head']
    if len(heads) != 1:
        raise RuntimeError(f'{path.name}: expected exactly one qa_role=head object, found {len(heads)}')
    head = heads[0]
    rig = next(m.object for m in head.modifiers if m.type == 'ARMATURE' and m.object)
    if 'MouthOpen' not in rig:
        raise RuntimeError(f'{rig.name}: missing MouthOpen control')
    if rig.animation_data:
        rig.animation_data.action = None
        for track in rig.animation_data.nla_tracks:
            track.mute = True
    for bone in rig.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    eyes = sorted((o for o in meshes if 'InsetGlowEye.' in o.name), key=lambda o: o.name)
    teeth = sorted((o for o in meshes if o.get('qa_role') in ('upper_teeth', 'lower_teeth')),
                   key=lambda o: o.name)
    if len(eyes) != 2 or len(teeth) != 2:
        raise RuntimeError(f'{path.name}: expected two eye insets and two tooth arches')
    result = {'file': str(path), 'sha256_before': before,
              'runtime_blender': bpy.app.version_string, 'saved_file_version': list(bpy.data.version),
              'head_object': head.name, 'rig': rig.name, 'states': {}}
    for label, value in (('closed', 0.0), ('open', 1.0)):
        rig['MouthOpen'] = value
        rig.update_tag()
        bpy.context.scene.frame_set(bpy.context.scene.frame_current)
        bpy.context.view_layer.update()
        points, triangles, edges, aperture = snapshot(head, rig)
        if not aperture:
            raise RuntimeError(f'{head.name}: missing evaluated QA_MouthAperture selection')
        hb, ab = bounds(points), bounds(aperture)
        width = hb['dimensions_xyz'][0]
        center_band = .025 * width
        lip_band = [p for p in aperture if abs(p.x) <= center_band]
        if not lip_band:
            raise RuntimeError(f'{head.name}: no aperture vertices in centerline sampling band')
        upper_lip_z = max(p.z for p in lip_band)
        eye_centers = {}
        for eye in eyes:
            eye_points = snapshot(eye, rig)[0]
            eye_centers[eye.name] = list(sum(eye_points, Vector()) / len(eye_points))
        eye_z = sum(center[2] for center in eye_centers.values()) / len(eye_centers)
        bvh = BVHTree.FromPolygons(points, triangles, all_triangles=True, epsilon=0)
        origin = Vector((0, .43, hb['min'][2]-2))
        hit, normal, index, distance = bvh.ray_cast(origin, Vector((0, 0, 1)), hb['dimensions_xyz'][2]+4)
        rear = {'ray_origin': list(origin), 'ray_direction': [0, 0, 1],
                'fixed_xy': [0, .43], 'hit': hit is not None,
                'underside_z': float(hit.z) if hit is not None else None,
                'point': list(hit) if hit is not None else None,
                'normal': list(normal) if normal is not None else None,
                'triangle_index': index}
        dental = {}
        for tooth in teeth:
            tp, _, te, _ = snapshot(tooth, rig)
            dental[tooth.get('qa_role')] = {'object': tooth.name,
                'base': components(len(tooth.data.vertices), [tuple(e.vertices) for e in tooth.data.edges]),
                'evaluated': components(len(tp), te)}
        result['states'][label] = {
            'mouth_open': value, 'head_bounds': hb, 'aperture_bounds': ab,
            'aperture_selected_vertices': len(aperture),
            'aperture_height_over_width': ab['dimensions_xyz'][2]/ab['dimensions_xyz'][0],
            'crown_z': hb['max'][2], 'upper_lip_center_z': upper_lip_z,
            'upper_lip_center_band_abs_x_max': center_band,
            'upper_lip_aperture_max_z': ab['max'][2],
            'crown_to_upper_lip_over_head_width': (hb['max'][2]-upper_lip_z)/width,
            'eye_centers': eye_centers, 'mean_eye_center_z': eye_z,
            'eye_center_to_upper_lip_over_head_width': (eye_z-upper_lip_z)/width,
            'teeth_components': dental, 'rear_skull_underside_probe': rear}
    closed, opened = (result['states'][k] for k in ('closed', 'open'))
    c_rear, o_rear = (s['rear_skull_underside_probe']['underside_z'] for s in (closed, opened))
    result['open_minus_closed'] = {
        'crown_z': opened['crown_z']-closed['crown_z'],
        'upper_lip_center_z': opened['upper_lip_center_z']-closed['upper_lip_center_z'],
        'rear_skull_underside_z': o_rear-c_rear if c_rear is not None and o_rear is not None else None,
        'outer_chin_z': opened['head_bounds']['min'][2]-closed['head_bounds']['min'][2]}
    result['sha256_after'] = hashlib.sha256(path.read_bytes()).hexdigest()
    result['input_blend_unchanged'] = result['sha256_after'] == before
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--v19', type=Path, required=True)
    parser.add_argument('--v20', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    args = parser.parse_args(argv)
    report = {'purpose': 'Direct geometric form comparison, explicitly not a likeness score or percentage.',
              'coordinate_space': 'Rig-local Blender units; canonical bone pose, legacy actions disabled in memory.',
              'definitions': {
                  'head': 'Evaluated qa_role=head mesh only; no ears, eyes, decorative fleece or body.',
                  'aperture': 'Evaluated vertices whose QA_MouthAperture weight exceeds 0.5.',
                  'upper_lip_center': 'Highest aperture vertex within abs(x)<=2.5% of evaluated head width.',
                  'eye_center': 'Arithmetic centroid of each evaluated luminous eye-inset mesh.',
                  'crown': 'Maximum Z of evaluated head mesh, excluding ears.',
                  'rear_underside': 'First head-BVH hit from below at fixed rig-local x=0, y=0.43.',
                  'teeth': 'Connected components calculated from mesh edges, not object names or intended tooth count.'},
              'limitations': [
                  'Not a reference-image similarity metric; camera perspective and artistic likeness are not scored.',
                  'Closed-aperture total height includes smile curvature and must not be interpreted as the lip-contact gap.',
                  'Rear underside is one fixed probe, not a complete rear-head silhouette analysis.',
                  'Endpoint measurements do not certify all intermediate states, collisions, animation or game export.']}
    report['v19'] = measure(args.v19)
    report['v20'] = measure(args.v20)
    report['v20_minus_v19'] = {}
    for state in ('closed', 'open'):
        old, new = (report[v]['states'][state] for v in ('v19', 'v20'))
        keys = ('crown_z', 'upper_lip_center_z', 'mean_eye_center_z',
                'crown_to_upper_lip_over_head_width', 'eye_center_to_upper_lip_over_head_width',
                'aperture_height_over_width')
        delta = {key: new[key]-old[key] for key in keys}
        for field in ('head_bounds', 'aperture_bounds'):
            delta[field+'_dimensions_xyz'] = [a-b for a, b in zip(new[field]['dimensions_xyz'], old[field]['dimensions_xyz'])]
        old_z, new_z = (s['rear_skull_underside_probe']['underside_z'] for s in (old, new))
        delta['rear_skull_underside_z'] = new_z-old_z if old_z is not None and new_z is not None else None
        report['v20_minus_v19'][state] = delta
    out = args.output.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print('FACE_METRICS', json.dumps({'output': str(out),
          'inputs_unchanged': all(report[v]['input_blend_unchanged'] for v in ('v19', 'v20')),
          'v20_minus_v19': report['v20_minus_v19']}))


if __name__ == '__main__':
    main()
