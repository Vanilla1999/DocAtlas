"""Independent read-only Blender integration audit for a rigged plush model.

Run:
  blender --background --python audit_v18.py -- /absolute/model.blend
Optional: --triangle-budget 100000 --no-intersections --output /path/report.json

The .blend is loaded and exercised in memory but NEVER saved. Numerical tests
are not proof of visual likeness, robust topology in every pose, or Roblox fit.
"""

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri


CORE_NAMES = ["V18_Torso", "V18_Head"] + [
    f"V18_{part}.{side}"
    for part in ("Arm", "Hand", "Leg", "Foot") for side in ("L", "R")
]
EPS = 1e-8


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("blend")
    p.add_argument("--output", default=str(Path(__file__).parent / "audit_v18.json"))
    p.add_argument("--triangle-budget", type=int)
    p.add_argument("--no-intersections", action="store_true")
    p.add_argument("--max-intersection-pairs", type=int, default=12000)
    return p.parse_args(argv)


def finite(v):
    return all(math.isfinite(float(x)) for x in v)


def quantile(vals, q):
    if not vals:
        return None
    vals = sorted(vals)
    at = q * (len(vals) - 1)
    a = int(at)
    b = min(a + 1, len(vals) - 1)
    return vals[a] * (b - at) + vals[b] * (at - a) if a != b else vals[a]


def bounds(coords):
    if not coords:
        return None
    lo = [min(v[k] for v in coords) for k in range(3)]
    hi = [max(v[k] for v in coords) for k in range(3)]
    return {"min": lo, "max": hi, "size": [b - a for a, b in zip(lo, hi)]}


def capture(obj):
    dep = bpy.context.evaluated_depsgraph_get()
    eo = obj.evaluated_get(dep)
    me = eo.to_mesh()
    me.calc_loop_triangles()
    coords = [eo.matrix_world @ v.co for v in me.vertices]
    edges = [tuple(e.vertices) for e in me.edges]
    triangles = [tuple(t.vertices) for t in me.loop_triangles]
    eo.to_mesh_clear()
    return {"coords": coords, "edges": edges, "triangles": triangles}


def connected_components(n, edges):
    parent = list(range(n))
    size = [1] * n
    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in edges:
        ra, rb = root(a), root(b)
        if ra != rb:
            if size[ra] < size[rb]:
                ra, rb = rb, ra
            parent[rb] = ra
            size[ra] += size[rb]
    counts = Counter(root(i) for i in range(n))
    return sorted(counts.values(), reverse=True)


def mesh_topology(obj, rig):
    me = obj.data
    me.calc_loop_triangles()
    usage = Counter()
    for poly in me.polygons:
        verts = list(poly.vertices)
        for a, b in zip(verts, verts[1:] + verts[:1]):
            usage[tuple(sorted((a, b)))] += 1
    edge_counts = [usage[tuple(sorted(e.vertices))] for e in me.edges]
    comp = connected_components(len(me.vertices), [tuple(e.vertices) for e in me.edges])
    deform_names = {b.name for b in rig.data.bones if b.use_deform} if rig else set()
    group_names = {g.index: g.name for g in obj.vertex_groups}
    sums = []
    counts = []
    for vert in me.vertices:
        ws = [g.weight for g in vert.groups
              if group_names.get(g.group) in deform_names and g.weight > 1e-6]
        sums.append(sum(ws))
        counts.append(len(ws))
    armature_mods = [m for m in obj.modifiers if m.type == "ARMATURE"]
    faces = Counter(len(p.vertices) for p in me.polygons)
    return {
        "vertices": len(me.vertices), "edges": len(me.edges),
        "faces": len(me.polygons), "triangles": len(me.loop_triangles),
        "face_sides": dict(faces),
        "quad_fraction": faces.get(4, 0) / max(1, len(me.polygons)),
        "ngons": sum(v for k, v in faces.items() if k > 4),
        "components": len(comp), "component_vertex_counts": comp[:20],
        "boundary_edges": sum(n == 1 for n in edge_counts),
        "wire_edges": sum(n == 0 for n in edge_counts),
        "overconnected_edges": sum(n > 2 for n in edge_counts),
        "nonmanifold_edges": sum(n != 2 for n in edge_counts),
        "zero_area_faces": sum(p.area < 1e-12 for p in me.polygons),
        "zero_length_edges": sum((me.vertices[e.vertices[0]].co -
                                   me.vertices[e.vertices[1]].co).length < 1e-7
                                  for e in me.edges),
        "nonfinite_vertices": sum(not finite(v.co) for v in me.vertices),
        "armature_modifiers": [m.object.name if m.object else None for m in armature_mods],
        "weights": {
            "unweighted_vertices": sum(c == 0 for c in counts),
            "over_four_influences": sum(c > 4 for c in counts),
            "maximum_influences": max(counts, default=0),
            "normalization_error_gt_1e_4": sum(abs(s - 1) > 1e-4 for s in sums),
            "max_sum_error": max((abs(s - 1) for s in sums), default=0),
        },
        "materials": [m.name if m else None for m in me.materials],
    }


def deformation(before, after):
    a, b = before["coords"], after["coords"]
    if len(a) != len(b) or before["edges"] != after["edges"]:
        return {"comparable": False, "reason": "Evaluated topology changed"}
    distances = [(v - w).length for v, w in zip(a, b)]
    ratios = []
    for i, j in before["edges"]:
        l0 = (a[i] - a[j]).length
        if l0 > 1e-7:
            ratios.append((b[i] - b[j]).length / l0)
    return {
        "comparable": True,
        "max_displacement": max(distances, default=0),
        "rms_displacement": math.sqrt(sum(d*d for d in distances) / max(1, len(distances))),
        "nonfinite_vertices": sum(not finite(v) for v in b),
        "edge_length_ratio": {
            "minimum": min(ratios, default=0), "p01": quantile(ratios, .01),
            "median": quantile(ratios, .5), "p99": quantile(ratios, .99),
            "maximum": max(ratios, default=0),
            "fraction_below_0_25": sum(x < .25 for x in ratios)/max(1, len(ratios)),
            "fraction_above_2": sum(x > 2 for x in ratios)/max(1, len(ratios)),
        },
    }


def strict_segment_hits_triangle(a, b, t):
    ray = b - a
    if ray.length_squared < 1e-14:
        return False
    point = intersect_ray_tri(t[0], t[1], t[2], ray, a, True)
    if point is None:
        return False
    u = (point - a).dot(ray) / ray.length_squared
    # Exclude endpoint touching. Adjacent triangles are also removed upstream.
    return 1e-6 < u < 1 - 1e-6


def intersection_probe(snapshot, cap):
    verts, tris = snapshot["coords"], snapshot["triangles"]
    if not tris:
        return {"candidate_pairs": 0, "confirmed_noncoplanar_crossings": 0}
    tree = BVHTree.FromPolygons(verts, tris, all_triangles=True, epsilon=0.0)
    raw = tree.overlap(tree)
    pairs = sorted({(a,b) if a < b else (b,a) for a,b in raw
                    if a != b and not set(tris[a]).intersection(tris[b])})
    confirmed=[]; coplanar=[]; degenerate=0
    for ia, ib in pairs[:cap]:
        ta=[verts[i] for i in tris[ia]]; tb=[verts[i] for i in tris[ib]]
        na=(ta[1]-ta[0]).cross(ta[2]-ta[0]); nb=(tb[1]-tb[0]).cross(tb[2]-tb[0])
        if na.length < 1e-10 or nb.length < 1e-10:
            degenerate += 1
            continue
        na.normalize(); nb.normalize()
        if abs(na.dot(nb)) > 1 - 1e-5 and abs(na.dot(tb[0]-ta[0])) < 1e-6:
            coplanar.append((ia,ib))
            continue
        hit = any(strict_segment_hits_triangle(ta[i],ta[(i+1)%3],tb) for i in range(3))
        hit |= any(strict_segment_hits_triangle(tb[i],tb[(i+1)%3],ta) for i in range(3))
        if hit:
            confirmed.append((ia,ib))
    return {
        "candidate_pairs": len(pairs), "examined_pairs": min(cap,len(pairs)),
        "examined_all_candidates": len(pairs) <= cap,
        "confirmed_noncoplanar_crossings": len(confirmed),
        "confirmed_examples": confirmed[:12],
        "coplanar_candidates_not_classified": len(coplanar),
        "degenerate_candidates_skipped": degenerate,
        "scope": "Within one evaluated object. Shared-vertex triangles excluded; coplanar overlap and contacts not certified. No inter-object test.",
    }


def save_pose(rig):
    return {p.name: p.matrix_basis.copy() for p in rig.pose.bones}


def reset_pose(rig):
    for p in rig.pose.bones:
        p.matrix_basis = Matrix.Identity(4)


def apply_pose(rig, spec):
    reset_pose(rig)
    missing=[]
    for name, transform in spec.items():
        pb=rig.pose.bones.get(name)
        if not pb:
            missing.append(name)
            continue
        pb.rotation_mode="XYZ"
        if "r" in transform:
            pb.rotation_euler=[math.radians(x) for x in transform["r"]]
        if "l" in transform:
            pb.location=transform["l"]
    bpy.context.view_layer.update()
    return missing


def pose_suite(rig):
    suite={}
    for angle in (45,90,120):
        suite[f"elbows_{angle}"]={f"Forearm.{s}":{"r":(-angle,0,0)} for s in ("L","R")}
    suite["arms_forward"]={f"UpperArm.{s}":{"r":(-85,0,0)} for s in ("L","R")}
    suite["arms_forward"].update({f"Forearm.{s}":{"r":(-15,0,0)} for s in ("L","R")})
    suite["arms_raised"]={"UpperArm.L":{"r":(0,0,-130)},"UpperArm.R":{"r":(0,0,130)}}
    suite["fingers_curl"]={p.name:{"r":(55,0,0)} for p in rig.pose.bones
                           if p.name.startswith("Finger") or p.name.startswith("Thumb")}
    suite["crouch"]={"Spine":{"r":(20,0,0)}}
    for side in ("L","R"):
        suite["crouch"].update({f"Thigh.{side}":{"r":(-60,0,0)},
                               f"Shin.{side}":{"r":(100,0,0)},
                               f"Foot.{side}":{"r":(-35,0,0)}})
    suite["ears_flex"]={"EarTip.L":{"r":(30,0,20)},"EarTip.R":{"r":(30,0,-20)}}
    suite["jaw_open"]={"Jaw":{"l":(0,-.015,-.29),"r":(-4,0,0)}}
    return suite


def rig_follow(rig, objs, baseline):
    old=rig.matrix_world.copy()
    delta=Matrix.Translation((.23,-.19,.14)) @ Matrix.Rotation(math.radians(23),4,"Z")
    rig.matrix_world=delta @ old
    bpy.context.view_layer.update()
    results={}
    for o in objs:
        got=capture(o)["coords"]
        expect=[delta @ v for v in baseline[o.name]["coords"]]
        if len(got)!=len(expect):
            results[o.name]={"comparable":False}
            continue
        errors=[(a-b).length for a,b in zip(got,expect)]
        results[o.name]={"max_error":max(errors,default=0),
                         "rms_error":math.sqrt(sum(e*e for e in errors)/max(1,len(errors)))}
    rig.matrix_world=old
    bpy.context.view_layer.update()
    return results


def action_loops(rig, core):
    results={}
    for action in bpy.data.actions:
        if not any(x in action.name.lower() for x in ("walk","idle","loop","cycle")):
            continue
        reset_pose(rig)
        rig.animation_data.action=action
        a,b=map(float,action.frame_range)
        bpy.context.scene.frame_set(int(a),subframe=a%1)
        first={p.name:p.matrix.copy() for p in rig.pose.bones}
        meshfirst={o.name:capture(o) for o in core}
        bpy.context.scene.frame_set(int(b),subframe=b%1)
        deltas={p.name:max(abs(p.matrix[i][j]-first[p.name][i][j]) for i in range(4) for j in range(4))
                for p in rig.pose.bones}
        mesherrors={}
        for o in core:
            d=deformation(meshfirst[o.name],capture(o))
            mesherrors[o.name]=d.get("max_displacement")
        results[action.name]={"start":a,"end":b,"max_bone_matrix_delta":max(deltas.values(),default=0),
                              "bones_above_1e_4":{n:v for n,v in deltas.items() if v>1e-4},
                              "mesh_endpoint_max_displacement":mesherrors,
                              "note":"Endpoint closure does not prove velocity continuity or correct foot planting."}
    rig.animation_data.action=None
    reset_pose(rig)
    return results


def main():
    args=arguments()
    start=time.time()
    f=Path(args.blend).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(f))
    rig=bpy.data.objects.get("ARM_Recovered_Plush_v17")
    if not rig or rig.type!="ARMATURE":
        armatures=[o for o in bpy.data.objects if o.type=="ARMATURE"]
        rig=armatures[0] if len(armatures)==1 else None
    meshes=[o for o in bpy.data.objects if o.type=="MESH" and o.name.startswith("V18_") and not o.hide_render]
    core=[o for o in meshes if o.name in CORE_NAMES]
    report={"file":str(f),"sha256":hashlib.sha256(f.read_bytes()).hexdigest(),
            "blender":bpy.app.version_string,"rig":rig.name if rig else None,
            "requested_core_names":CORE_NAMES,"missing_core_names":[n for n in CORE_NAMES if n not in bpy.data.objects],
            "mesh_parts":len(meshes),"core_parts":len(core),"triangle_budget":args.triangle_budget,
            "limitations":["Structural/selected-pose audit, not a likeness score.",
                           "Finite geometry and low edge stretch do not prove good deformation.",
                           "Only non-coplanar within-object crossings are confirmed; inter-object overlap is not tested.",
                           "UV quality, texture baking, runtime export, collision and Roblox Studio are not tested."]}
    if not rig:
        report["fatal"]="Rig not resolved"
    else:
        saved_action=rig.animation_data.action if rig.animation_data else None
        saved_frame=bpy.context.scene.frame_current
        if not rig.animation_data:
            rig.animation_data_create()
        rig.animation_data.action=None
        for track in rig.animation_data.nla_tracks:
            track.mute=True
        reset_pose(rig)
        bpy.context.view_layer.update()
        report["bones"]=len(rig.data.bones)
        report["root_bones"]=[b.name for b in rig.data.bones if b.parent is None]
        report["topology"]={o.name:mesh_topology(o,rig) for o in meshes}
        report["total_source_triangles"]=sum(d["triangles"] for d in report["topology"].values())
        report["over_triangle_budget"]=(report["total_source_triangles"]>args.triangle_budget) if args.triangle_budget else None
        report["material_names"]=sorted({m.name for o in meshes for m in o.data.materials if m})
        base={o.name:capture(o) for o in core}
        report["bind_bounds"]={n:bounds(s["coords"]) for n,s in base.items()}
        report["evaluated_core_triangles"]=sum(len(s["triangles"]) for s in base.values())
        if not args.no_intersections:
            report["bind_intersection_probe"]={n:intersection_probe(s,args.max_intersection_pairs) for n,s in base.items()}
        report["stress_poses"]={}
        for name,spec in pose_suite(rig).items():
            missing=apply_pose(rig,spec)
            item={"input_degrees_and_local_translation":spec,"missing_bones":missing,"meshes":{}}
            for obj in core:
                snap=capture(obj)
                detail=deformation(base[obj.name],snap)
                if not args.no_intersections and name in ("elbows_120","fingers_curl","jaw_open"):
                    detail["intersection_probe"]=intersection_probe(snap,args.max_intersection_pairs)
                item["meshes"][obj.name]=detail
            report["stress_poses"][name]=item
        reset_pose(rig)
        bpy.context.view_layer.update()
        report["rig_transform_follow"]=rig_follow(rig,meshes,{o.name:capture(o) for o in meshes})
        report["loop_endpoints"]=action_loops(rig,core)
        rig.animation_data.action=saved_action
        bpy.context.scene.frame_set(saved_frame)
    report["elapsed_seconds"]=round(time.time()-start,2)
    out=Path(args.output).resolve()
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    brief={k:report.get(k) for k in ("file","rig","mesh_parts","core_parts","missing_core_names",
                                   "total_source_triangles","evaluated_core_triangles","elapsed_seconds")}
    brief["report"]=str(out)
    print("INDEPENDENT_AUDIT",json.dumps(brief,ensure_ascii=False))


if __name__=="__main__":
    main()
