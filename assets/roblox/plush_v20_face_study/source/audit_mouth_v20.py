"""Independent, read-only mouth-state audit for a Blender 5.3 plush asset.

Example:
  blender -b --python audit_mouth_v20.py -- /absolute/model.blend --output report.json

No .blend is saved. The SHA-256 of the input file is checked before and after.
The only write is the requested JSON report. Numeric checks do not certify
likeness, pleasant deformation, an engine export, or all possible contacts.

Optional author annotations (no annotations required for normal discovery):
  obj["qa_role"] = head | lip | interior | upper_teeth | lower_teeth
  Tongue meshes should use qa_role="interior" so exposed-tip tests include them.
  vertex group "QA_MouthAperture": the one mouth opening boundary
  vertex group "QA_FreeToothTips": exposed tooth tips, excluding embedded roots
  obj["qa_skip"] = True: omit decorative fibres from this structural audit
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
from mathutils.kdtree import KDTree


ROLES = {"head", "lip", "interior", "upper_teeth", "lower_teeth", "teeth"}
SOFT_ROLES = {"head", "lip", "interior"}
TEETH_ROLES = {"upper_teeth", "lower_teeth", "teeth"}


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("blend")
    p.add_argument("--output", default=str(Path(__file__).parent / "audit_mouth_v20.json"))
    p.add_argument("--prefix", default="V20_")
    p.add_argument("--states", default="0,0.125,0.25,0.375,0.5,0.625,0.75,0.875,1")
    p.add_argument("--dense", action="store_true", help="Override --states with 41 positions at step 0.025.")
    p.add_argument("--max-pairs", type=int, default=12000)
    p.add_argument("--max-samples", type=int, default=2500)
    p.add_argument("--no-intersections", action="store_true")
    return p.parse_args(argv)


def finite(v):
    return all(math.isfinite(float(x)) for x in v)


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    a = int(pos)
    b = min(a + 1, len(ordered) - 1)
    return ordered[a] * (b-pos) + ordered[b] * (pos-a) if a != b else ordered[a]


def bounds(coords):
    if not coords:
        return None
    lo = [min(p[k] for p in coords) for k in range(3)]
    hi = [max(p[k] for p in coords) for k in range(3)]
    return {"min": lo, "max": hi, "size": [hi[k]-lo[k] for k in range(3)]}


def discover_role(obj):
    explicit = str(obj.get("qa_role", "")).lower()
    if explicit in ROLES:
        return explicit
    n = obj.name.lower().replace("_", "").replace("-", "")
    if ("upper" in n and "lower" in n) and ("teeth" in n or "fang" in n):
        return "teeth"
    if "upperteeth" in n or "upperfang" in n:
        return "upper_teeth"
    if "lowerteeth" in n or "lowerfang" in n:
        return "lower_teeth"
    if "teeth" in n or "fang" in n:
        return "teeth"
    if "liprim" in n or "mouthrim" in n or n.endswith("lip"):
        return "lip"
    if "mouthinterior" in n or "oralcavity" in n or "mouthcavity" in n or "tongue" in n:
        return "interior"
    if "headshell" in n or n.endswith("head"):
        return "head"
    return None


def ancestry_reaches(obj, target):
    seen = set()
    while obj is not None and obj.name not in seen:
        if obj == target:
            return True
        seen.add(obj.name)
        obj = obj.parent
    return False


def components(n, edges):
    par = list(range(n))
    def root(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for a, b in edges:
        a, b = root(a), root(b)
        if a != b:
            par[b] = a
    return sorted(Counter(root(i) for i in range(n)).values(), reverse=True)


def base_mesh_checks(obj, rig):
    m = obj.data
    m.calc_loop_triangles()
    usage = Counter()
    for face in m.polygons:
        ids = list(face.vertices)
        for a, b in zip(ids, ids[1:] + ids[:1]):
            usage[tuple(sorted((a, b)))] += 1
    counts = [usage[tuple(sorted(e.vertices))] for e in m.edges]
    group_names = {g.index:g.name for g in obj.vertex_groups}
    deform = {b.name for b in rig.data.bones if b.use_deform}
    sums = []
    influences = []
    used_bones = set()
    for v in m.vertices:
        weights = [(group_names[g.group], g.weight) for g in v.groups
                   if group_names.get(g.group) in deform and g.weight > 1e-7]
        sums.append(sum(w for _,w in weights))
        influences.append(len(weights))
        used_bones.update(n for n,_ in weights)
    chains = {}
    for name in sorted(used_bones):
        bone = rig.data.bones[name]
        chain = [name]
        while bone.parent:
            bone = bone.parent
            chain.append(bone.name)
        chains[name] = chain
    comp = components(len(m.vertices), [tuple(e.vertices) for e in m.edges])
    keys = obj.data.shape_keys
    return {
        "role":discover_role(obj), "vertices":len(m.vertices),
        "faces":len(m.polygons), "triangles":len(m.loop_triangles),
        "quad_fraction":sum(len(p.vertices)==4 for p in m.polygons)/max(1,len(m.polygons)),
        "ngons":sum(len(p.vertices)>4 for p in m.polygons),
        "components":len(comp), "component_vertex_counts":comp[:32],
        "boundary_edges":sum(c==1 for c in counts),
        "wire_edges":sum(c==0 for c in counts),
        "overconnected_edges":sum(c>2 for c in counts),
        "nonmanifold_edges":sum(c!=2 for c in counts),
        "zero_area_faces":sum(p.area<1e-12 for p in m.polygons),
        "zero_length_edges":sum((m.vertices[e.vertices[0]].co-m.vertices[e.vertices[1]].co).length<1e-7 for e in m.edges),
        "nonfinite_vertices":sum(not finite(v.co) for v in m.vertices),
        "weights":{
            "unweighted_vertices":sum(n==0 for n in influences),
            "maximum_influences":max(influences,default=0),
            "over_four_influences":sum(n>4 for n in influences),
            "normalization_errors_gt_1e_4":sum(abs(x-1)>1e-4 for x in sums),
            "max_sum_error":max((abs(x-1) for x in sums),default=0),
        },
        "armature_modifiers":[m.object.name if m.object else None for m in obj.modifiers if m.type=="ARMATURE"],
        "parent_chain_reaches_rig":ancestry_reaches(obj,rig),
        "bone_parent_chains":chains,
        "shape_keys":[k.name for k in keys.key_blocks] if keys else [],
        "shape_key_drivers":[fc.data_path for fc in keys.animation_data.drivers]
            if keys and keys.animation_data else [],
        "qa_groups_present":[g.name for g in obj.vertex_groups if g.name.startswith("QA_")],
    }


def snapshot(obj, rig):
    dep = bpy.context.evaluated_depsgraph_get()
    eo = obj.evaluated_get(dep)
    me = eo.to_mesh()
    me.calc_loop_triangles()
    matrix = rig.matrix_world.inverted() @ eo.matrix_world
    pts = [matrix @ v.co for v in me.vertices]
    groups = {g.name:g.index for g in eo.vertex_groups}
    selections = {}
    for group in ("QA_MouthAperture", "QA_FreeToothTips"):
        index = groups.get(group)
        if index is not None:
            selections[group] = [v.index for v in me.vertices
                if any(g.group==index and g.weight>.5 for g in v.groups)]
    data = {"coords":pts, "triangles":[tuple(t.vertices) for t in me.loop_triangles],
            "edges":[tuple(e.vertices) for e in me.edges], "groups":selections,
            "world_matrix":eo.matrix_world.copy(), "rig_matrix":rig.matrix_world.copy()}
    eo.to_mesh_clear()
    return data


def tree(s):
    return BVHTree.FromPolygons(s["coords"],s["triangles"],all_triangles=True,epsilon=0)


def segment_crosses(a,b,triangle):
    ray = b-a
    if ray.length_squared < 1e-14:
        return False
    hit = intersect_ray_tri(triangle[0],triangle[1],triangle[2],ray,a,True)
    if hit is None:
        return False
    t = (hit-a).dot(ray)/ray.length_squared
    return 1e-6 < t < 1-1e-6


def classify_pair(ta,tb):
    na = (ta[1]-ta[0]).cross(ta[2]-ta[0])
    nb = (tb[1]-tb[0]).cross(tb[2]-tb[0])
    if min(na.length,nb.length) < 1e-10:
        return "degenerate"
    na.normalize(); nb.normalize()
    if abs(na.dot(nb)) > 1-1e-5 and abs(na.dot(tb[0]-ta[0])) < 1e-6:
        return "coplanar_unclassified"
    if any(segment_crosses(ta[i],ta[(i+1)%3],tb) for i in range(3)) or any(
           segment_crosses(tb[i],tb[(i+1)%3],ta) for i in range(3)):
        return "crossing"
    return "no_strict_crossing"


def intersections(a,b,cap,same=False):
    if any(not finite(p) for p in a["coords"]+b["coords"]):
        return {"skipped":"nonfinite geometry"}
    raw = tree(a).overlap(tree(b))
    if same:
        pairs = sorted({(min(i,j),max(i,j)) for i,j in raw
                        if i!=j and not set(a["triangles"][i]).intersection(a["triangles"][j])})
    else:
        pairs = sorted(set(raw))
    tally = Counter(); examples = []
    for i,j in pairs[:cap]:
        ta = [a["coords"][k] for k in a["triangles"][i]]
        tb = [b["coords"][k] for k in b["triangles"][j]]
        category = classify_pair(ta,tb)
        tally[category] += 1
        if category=="crossing" and len(examples)<12:
            examples.append([i,j])
    example_geometry=[]
    for i,j in examples[:4]:
        ta=[a["coords"][k] for k in a["triangles"][i]]
        tb=[b["coords"][k] for k in b["triangles"][j]]
        example_geometry.append({"triangle_a":i,"triangle_b":j,
            "a_vertices_rig_local":[list(p) for p in ta],
            "b_vertices_rig_local":[list(p) for p in tb],
            "a_centroid_rig_local":list(sum(ta,Vector())/3),
            "b_centroid_rig_local":list(sum(tb,Vector())/3)})
    return {"candidate_pairs":len(pairs), "examined_pairs":min(cap,len(pairs)),
            "examined_all":len(pairs)<=cap,
            "confirmed_noncoplanar_crossings":tally["crossing"],
            "coplanar_candidates_not_classified":tally["coplanar_unclassified"],
            "degenerate_candidates_skipped":tally["degenerate"],
            "examples":examples,
            "example_geometry":example_geometry,
            "scope":"Strict noncoplanar triangle crossings only. Shared vertices excluded for self tests; contact/overlap in a common plane is not certified."}


def sample_indices(ids,limit):
    step = max(1, math.ceil(len(ids)/max(1,limit)))
    return ids[::step]


def symmetry(coords,limit):
    if not coords or any(not finite(p) for p in coords):
        return None
    kd = KDTree(len(coords))
    for i,p in enumerate(coords): kd.insert(p,i)
    kd.balance()
    ids = sample_indices(list(range(len(coords))),limit)
    distances = [kd.find(Vector((-coords[i].x,coords[i].y,coords[i].z)))[2] for i in ids]
    return {"samples":len(ids), "median_error":percentile(distances,.5),
            "p95_error":percentile(distances,.95), "max_error":max(distances,default=0),
            "note":"Nearest mirrored vertex, rig-local X=0. Surface relief or intentional asymmetry may contribute; not a likeness score."}


def snapshot_checks(s,limit):
    pts = s["coords"]
    areas = [((pts[b]-pts[a]).cross(pts[c]-pts[a])).length*.5 for a,b,c in s["triangles"]]
    result = {"vertices":len(pts),"triangles":len(s["triangles"]),
              "bounds_rig_local":bounds(pts), "nonfinite_vertices":sum(not finite(p) for p in pts),
              "zero_area_triangles":sum(a<1e-12 for a in areas),
              "min_triangle_area":min(areas,default=None),
              "mirror_symmetry":symmetry(pts,limit)}
    aperture = [pts[i] for i in s["groups"].get("QA_MouthAperture",[])]
    if aperture:
        bb = bounds(aperture)
        result["aperture"] = {"selected_vertices":len(aperture), "bounds":bb,
            "width":bb["size"][0], "height":bb["size"][2],
            "depth_spread":bb["size"][1],
            "x_midline_offset":(bb["min"][0]+bb["max"][0])*.5,
            "mirror_symmetry":symmetry(aperture,limit)}
    return result


def teeth_clearance(teeth_snap,soft_snaps,limit,cap=0):
    selected = teeth_snap["groups"].get("QA_FreeToothTips",[])
    if not selected:
        return {"tested":False,"reason":"No QA_FreeToothTips group. Tooth roots intentionally embed in soft tissue; a whole-tooth distance would be misleading."}
    ids = sample_indices(selected,limit)
    trees = [(name,tree(s)) for name,s in soft_snaps.items()]
    distances = []; near = Counter(); closest_examples = []
    for i in ids:
        p = teeth_snap["coords"][i]
        candidates = []
        for name,t in trees:
            hit = t.find_nearest(p)
            if hit is not None and hit[0] is not None:
                candidates.append((hit[3],name,hit[0]))
        if candidates:
            distance,name,surface = min(candidates,key=lambda x:x[0])
            distances.append(distance)
            if distance<.001:near[name]+=1
            closest_examples.append({"vertex":i,"distance":distance,"soft_object":name,
                "tip_point_rig_local":list(p),"surface_point_rig_local":list(surface)})
    selected_set=set(selected)
    free_triangles=[i for i,t in enumerate(teeth_snap["triangles"]) if all(v in selected_set for v in t)]
    tip_snap={"coords":teeth_snap["coords"],"triangles":[teeth_snap["triangles"][i] for i in free_triangles]}
    crossings={}
    if cap and free_triangles:
        for name,soft in soft_snaps.items():
            check=intersections(tip_snap,soft,cap)
            check["examples_original_triangle_ids"]=[[free_triangles[a],b] for a,b in check.get("examples",[])]
            crossings[name]=check
    return {"tested":True,"tip_samples":len(ids),"minimum_unsigned_surface_distance":min(distances,default=None),
            "p05_unsigned_surface_distance":percentile(distances,.05),
            "samples_within_1mm_by_soft_object":dict(near),
            "closest_samples":sorted(closest_examples,key=lambda x:x["distance"])[:6],
            "free_tip_triangles":len(free_triangles),"free_tip_soft_crossings":crossings,
            "note":"Distances are unsigned and cannot establish inside/outside. Separate free-tip triangle crossing probes exclude roots and report strict noncoplanar intersections, not general clearance certification."}


def set_mouth(rig,value):
    rig["MouthOpen"] = value
    rig.update_tag()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    bpy.context.view_layer.update()


def root_follow(rig,objects):
    old = rig.matrix_world.copy()
    before = {o.name:snapshot(o,rig) for o in objects}
    rig.matrix_world = Matrix.Translation((.21,-.17,.13)) @ Matrix.Rotation(.31,4,'Z') @ old
    bpy.context.view_layer.update()
    result = {}
    for o in objects:
        after = snapshot(o,rig)
        a,b = before[o.name]["coords"],after["coords"]
        if len(a)!=len(b):
            result[o.name]={"comparable":False}
        else:
            errors = [(p-q).length for p,q in zip(a,b)]
            result[o.name]={"comparable":True,"max_rig_local_error":max(errors,default=0),
                            "rms_error":math.sqrt(sum(x*x for x in errors)/max(1,len(errors)))}
    rig.matrix_world = old
    bpy.context.view_layer.update()
    return result


def closed_mouth_visibility(rig,objects,roles):
    """Conservative orthographic enamel visibility through the closed seam.

    Geometry-node fleece instances and unrelated scene objects are deliberately
    excluded. A tooth-first ray therefore means enamel is unoccluded by the
    structural head, not a promise about a noisy/fuzzy material render.
    """
    set_mouth(rig,0)
    snaps={o.name:snapshot(o,rig) for o in objects}
    apertures=[s["coords"][i] for s in snaps.values()
               for i in s["groups"].get("QA_MouthAperture",[])]
    if not apertures:
        return {"tested":False,"reason":"No QA_MouthAperture contour to define the closed seam region."}
    bb=bounds(apertures)
    xmin,xmax=bb["min"][0]-.045,bb["max"][0]+.045
    zmin,zmax=bb["min"][2]-.045,bb["max"][2]+.045
    cz=(zmin+zmax)*.5
    nx,nz=241,65
    targets=[(name,tree(s)) for name,s in snaps.items()]
    views={}
    for degrees in (-15,0,15):
        a=math.radians(degrees)
        direction=Vector((math.sin(a),math.cos(a),0))
        right=Vector((math.cos(a),-math.sin(a),0))
        center=Vector((0,0,cz))
        hits=Counter();examples=[]
        for iz in range(nz):
            z=zmin+(zmax-zmin)*iz/(nz-1)
            for ix in range(nx):
                x=xmin+(xmax-xmin)*ix/(nx-1)
                origin=center-direction*3+right*x+Vector((0,0,z-cz))
                intersections=[]
                for name,bvh in targets:
                    hit=bvh.ray_cast(origin,direction,8)
                    if hit[0] is not None:
                        intersections.append((hit[3],name,hit[0]))
                if not intersections:
                    hits['miss']+=1
                    continue
                distance,name,point=min(intersections,key=lambda v:v[0])
                hits[name]+=1
                if roles[name] in TEETH_ROLES and len(examples)<24:
                    examples.append({"tooth_object":name,"screen_x":x,"screen_z":z,
                                     "hit_point_rig_local":list(point)})
        tooth_first=sum(count for name,count in hits.items() if roles.get(name) in TEETH_ROLES)
        views[str(degrees)]={"total_rays":nx*nz,"first_hit_counts":dict(hits),
            "tooth_first_rays":tooth_first,"tooth_fraction_of_all_rays":tooth_first/(nx*nz),
            "tooth_hit_examples":examples}
    return {"tested":True,"grid":[nx,nz],"screen_x_range":[xmin,xmax],"z_range":[zmin,zmax],
            "views_degrees":views,
            "scope":"Closed MouthOpen=0; orthographic rays at yaw -15/0/+15 degrees; structural head and tooth meshes only. Cosmetic fleece can additionally occlude enamel. Sampling is not an exhaustive visibility proof."}


def convex_hull_2d(points):
    points=sorted(set(points))
    def cross(o,a,b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lo=[];hi=[]
    for p in points:
        while len(lo)>=2 and cross(lo[-2],lo[-1],p)<=0:
            lo.pop()
        lo.append(p)
    for p in reversed(points):
        while len(hi)>=2 and cross(hi[-2],hi[-1],p)<=0:
            hi.pop()
        hi.append(p)
    return lo[:-1]+hi[:-1]


def body_in_aperture_visibility(rig,mouth_snaps,body_objects):
    """Probe retained torso/neck visibility in the current lower mouth aperture.

    A manifold mouth can still contain a separate torso/neck. This explicitly
    checks their occlusion against the evaluated facial shell and teeth rather
    than treating mouth-only triangle tests as whole-character validation.
    """
    aperture=[s["coords"][i] for s in mouth_snaps.values()
              for i in s["groups"].get("QA_MouthAperture",[])]
    if not aperture or not body_objects:
        return {"tested":False,"reason":"Needs QA_MouthAperture and retained torso/neck context objects."}
    snaps=dict(mouth_snaps)
    snaps.update({o.name:snapshot(o,rig) for o in body_objects})
    targets=[(n,tree(s)) for n,s in snaps.items() if s["triangles"]]
    body_names={o.name for o in body_objects}
    nx,nz=161,65
    views={}
    for degrees in (-15,0,15):
        angle=math.radians(degrees)
        right=Vector((math.cos(angle),math.sin(angle),0))
        direction=Vector((-math.sin(angle),math.cos(angle),0))
        polygon=convex_hull_2d([(p.dot(right),p.z) for p in aperture])
        if len(polygon)<3:
            continue
        xmin,xmax=min(p[0] for p in polygon),max(p[0] for p in polygon)
        zmin,zmax=min(p[1] for p in polygon),max(p[1] for p in polygon)
        hits=Counter();examples=[];body_points=[];ray_count=0
        for iz in range(nz):
            z=zmin+(zmax-zmin)*.55*iz/(nz-1)
            for ix in range(nx):
                x=xmin+(xmax-xmin)*ix/(nx-1)
                if not all((b[0]-a[0])*(z-a[1])-(b[1]-a[1])*(x-a[0])>1e-6
                           for a,b in zip(polygon,polygon[1:]+polygon[:1])):
                    continue
                ray_count+=1
                origin=right*x+Vector((0,0,z))-direction*5
                nearest=None
                for name,bvh in targets:
                    point,normal,index,distance=bvh.ray_cast(origin,direction,12)
                    if point is not None and (nearest is None or distance<nearest[0]):
                        nearest=(distance,name,point)
                if nearest is None:
                    hits["miss"]+=1
                    continue
                distance,name,point=nearest
                hits[name]+=1
                if name in body_names:
                    body_points.append(point)
                    if len(examples)<12:
                        examples.append({"body_object":name,"hit_point_rig_local":list(point)})
        views[str(degrees)]={"rays_inside_aperture":ray_count,"first_hit_counts":dict(hits),
            "body_first_rays":sum(hits[n] for n in body_names),
            "body_first_hit_bounds":bounds(body_points),"body_hit_examples":examples}
    return {"tested":True,"grid":[nx,nz],"context_objects":sorted(body_names),"views_degrees":views,
            "scope":"Lower55% of projected evaluated aperture-contour convex hull; yaw -15/0/+15. Evaluated mouth, torso and neck surfaces only. Fleece instances omitted; positive body-first counts flag unoccluded retained body, while zero counts are sampled occlusion evidence, not all-angle or all-fibre certification."}


def main():
    opt = args(); start = time.time()
    path = Path(opt.blend).resolve()
    sha_before = hashlib.sha256(path.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(path))
    rigs = [o for o in bpy.data.objects if o.type=="ARMATURE"]
    rig = next((o for o in rigs if "MouthOpen" in o),rigs[0] if len(rigs)==1 else None)
    candidates = [o for o in bpy.data.objects if o.type=="MESH" and o.name.startswith(opt.prefix)
                  and not o.get("qa_skip",False)
                  and not o.name.startswith(opt.prefix+"Fleece_")]
    objects = [o for o in candidates if discover_role(o) is not None]
    body_objects=[o for o in candidates if o not in objects and not o.hide_render
                  and ("torso" in o.name.lower() or "neck" in o.name.lower())]
    roles = {o.name:discover_role(o) for o in objects}
    states = [i/40 for i in range(41)] if opt.dense else [float(x.strip()) for x in opt.states.split(",")]
    report = {"file":str(path),"sha256_before":sha_before,"runtime_blender":bpy.app.version_string,
              "saved_file_version":list(bpy.data.version),
              "saved_file_version_at_least_5_3":tuple(bpy.data.version)>=(5,3,0),
              "reported_build_software":bpy.context.scene.get("SoftwareBuiltWith"),
              "rig":rig.name if rig else None,"discovered_objects":roles,
              "soft_collision_objects":[n for n,r in roles.items() if r in SOFT_ROLES],
              "tongue_objects":[n for n in roles if "tongue" in n.lower()],
              "states_requested":states,
              "limitations":["Independent structural and mouth-state checks, not a character-likeness score.",
                 "No all-pose, UV/bake, Roblox import, physical contact or animation approval.",
                 "Separate head/lip/interior meshes can intentionally overlap at seams; those cross-object contacts are not certified.",
                 "Self-intersection probes exclude coplanar overlap and shared-vertex triangles; capped probes report incompleteness.",
                 "Mirror symmetry includes evaluated procedural relief and need not be exactly zero."]}
    if rig is None or "MouthOpen" not in rig or not objects:
        report["fatal"]="Missing MouthOpen armature or discoverable mouth meshes; set --prefix or qa_role metadata."
    else:
        if rig.animation_data:
            rig.animation_data.action=None
            for track in rig.animation_data.nla_tracks:track.mute=True
        for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
        report["bones"]=len(rig.data.bones)
        report["root_bones"]=[b.name for b in rig.data.bones if b.parent is None]
        report["topology"]={o.name:base_mesh_checks(o,rig) for o in objects}
        report["body_context_topology"]={o.name:base_mesh_checks(o,rig) for o in body_objects}
        report["mouth_states"]={}
        for value in states:
            set_mouth(rig,value)
            snaps={o.name:snapshot(o,rig) for o in objects}
            item={"meshes":{name:snapshot_checks(s,opt.max_samples) for name,s in snaps.items()},
                  "shape_key_values":{o.name:{k.name:k.value for k in o.data.shape_keys.key_blocks}
                      for o in objects+body_objects if o.data.shape_keys}}
            if not opt.no_intersections:
                item["self_intersections"]={name:intersections(s,s,opt.max_pairs,True) for name,s in snaps.items()}
                uppers=[n for n in snaps if roles[n]=="upper_teeth"]
                lowers=[n for n in snaps if roles[n]=="lower_teeth"]
                item["upper_lower_tooth_crossings"]={u+" vs "+l:intersections(snaps[u],snaps[l],opt.max_pairs)
                    for u in uppers for l in lowers}
            soft={n:s for n,s in snaps.items() if roles[n] in SOFT_ROLES}
            item["free_tooth_tip_clearances"]={n:teeth_clearance(s,soft,opt.max_samples,0 if opt.no_intersections else opt.max_pairs)
                 for n,s in snaps.items() if roles[n] in TEETH_ROLES}
            item["body_in_aperture_visibility"]=body_in_aperture_visibility(rig,snaps,body_objects)
            report["mouth_states"][str(value)]=item
        set_mouth(rig,.5)
        report["rig_transform_follow"]=root_follow(rig,objects+body_objects)
        report["closed_mouth_visibility"]=closed_mouth_visibility(rig,objects,roles)
    report["sha256_after"]=hashlib.sha256(path.read_bytes()).hexdigest()
    report["input_blend_unchanged"]=report["sha256_after"]==sha_before
    report["elapsed_seconds"]=round(time.time()-start,2)
    out=Path(opt.output).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    brief={k:report.get(k) for k in ("file","runtime_blender","saved_file_version","rig","discovered_objects",
                                   "input_blend_unchanged","elapsed_seconds","fatal")}
    brief["states"]={k:{"self_crossings":{n:d.get("confirmed_noncoplanar_crossings")
                        for n,d in v.get("self_intersections",{}).items()},
                       "tooth_crossings":{n:d.get("confirmed_noncoplanar_crossings")
                        for n,d in v.get("upper_lower_tooth_crossings",{}).items()},
                       "free_tip_soft_crossings":{n:{s:d.get("confirmed_noncoplanar_crossings")
                        for s,d in tooth.get("free_tip_soft_crossings",{}).items()}
                        for n,tooth in v.get("free_tooth_tip_clearances",{}).items()}}
                     for k,v in report.get("mouth_states",{}).items()}
    brief["report"]=str(out)
    brief["closed_tooth_first_rays"]={angle:v["tooth_first_rays"] for angle,v in report.get("closed_mouth_visibility",{}).get("views_degrees",{}).items()}
    brief["body_first_rays_by_state"]={value:{angle:v["body_first_rays"]
        for angle,v in state.get("body_in_aperture_visibility",{}).get("views_degrees",{}).items()}
        for value,state in report.get("mouth_states",{}).items()}
    print("MOUTH_QA",json.dumps(brief,ensure_ascii=False))


if __name__=="__main__":
    main()

