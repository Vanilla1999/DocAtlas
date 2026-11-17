"""Minimal integration-style smoke inspection of the reconstructed .blend."""

import json
from pathlib import Path

import bpy
from mathutils import Vector


ROOT=Path(__file__).resolve().parent
F=ROOT/"plush_v17_recovered"/"Plush-v17-Reconstruction.blend"
bpy.ops.wm.open_mainfile(filepath=str(F))
scene=bpy.context.scene
rig=bpy.data.objects["ARM_Recovered_Plush_v17"]
assert rig.type=="ARMATURE"
assert scene.render.fps==24
assert len(rig.data.bones)>=30
action_names=sorted(a.name for a in bpy.data.actions)
assert len(action_names)==4
assert all(name.startswith("AN_v17_") for name in action_names)
assert rig.animation_data.action.name=="AN_v17_Walk_InPlace_40f_24fps"


def foot_bottom(side):
    depsgraph=bpy.context.evaluated_depsgraph_get()
    items=[o for o in bpy.data.objects if o.name.endswith(f"foot toe 1 {side}")
           or o.name.endswith(f"foot toe 2 {side}") or o.name.endswith(f"foot toe 3 {side}")
           or o.name==f"Round foot {side}"]
    values=[]
    for obj in items:
        eo=obj.evaluated_get(depsgraph)
        me=eo.to_mesh()
        values.extend((eo.matrix_world @ vert.co).z for vert in me.vertices)
        eo.to_mesh_clear()
    return round(min(values),4)


frames=[]
for f in (1,6,11,16,21,26,31,36,41):
    scene.frame_set(f)
    frames.append({"frame":f,"left_foot_min_z":foot_bottom("L"),
                   "right_foot_min_z":foot_bottom("R")})
assert abs(frames[0]["left_foot_min_z"]-frames[-1]["left_foot_min_z"])<.0001
assert abs(frames[0]["right_foot_min_z"]-frames[-1]["right_foot_min_z"])<.0001

rig.animation_data.action=bpy.data.actions["AN_v17_Jaw_Open_Close_32f"]
scene.frame_set(1)
p1=rig.pose.bones["Jaw"].matrix.copy()
scene.frame_set(17)
p2=rig.pose.bones["Jaw"].matrix.copy()
assert (p1.translation-p2.translation).length>.1

geometry=[o for o in bpy.data.objects if o.type=="MESH" and o.name!="STUDIO / floor"]
assert len(geometry)>=60
unrigged=[o.name for o in geometry if not any(m.type=="ARMATURE" for m in o.modifiers)]
print("UNRIGGED_MESHES",unrigged)
assert not unrigged

data={"file":F.name,"blender_version":bpy.app.version_string,
      "mesh_parts":len(geometry),"bones":len(rig.data.bones),
      "materials":len(bpy.data.materials),"actions":action_names,
      "walk_contact_probe_meters":frames,"jaw_opens":True,
      "limitations":"Visual quality and Blender-to-Roblox runtime are not verified."}
(ROOT/"plush_v17_recovered"/"QA-Reconstruction-v17.json").write_text(
    json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
print("QA_RECONSTRUCTION",json.dumps(data,ensure_ascii=False))
