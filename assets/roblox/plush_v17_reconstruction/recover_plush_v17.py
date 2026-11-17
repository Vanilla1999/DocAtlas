"""Rebuild a new, editable plush creature from surviving verbal design notes.

This is a reconstruction, NOT a recovery of the missing v16 .blend bytes.
Run: blender --background --python recover_plush_v17.py
"""

import math
from pathlib import Path

import bpy
from mathutils import Vector


OUT = Path(__file__).resolve().parent / "plush_v17_recovered"
OUT.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.film_transparent = False
scene.render.engine = "CYCLES"
scene.cycles.samples = 22
scene.cycles.use_denoising = False
scene.render.resolution_x = 800
scene.render.resolution_y = 800
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "AgX"
scene.world = bpy.data.worlds.new("Neutral studio world")
scene.world.color = (0.10, 0.10, 0.10)
scene.render.filepath = str(OUT / "Plush-v17-Hero.png")
scene.view_settings.exposure = -1.35
scene.frame_start, scene.frame_end, scene.render.fps = 1, 41, 24


def collection(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c


CHAR = collection("01 • Recovered plush / geometry")
DETAIL = collection("02 • Cloth, stitches, features")
STUDIO = collection("03 • Photo studio (hide for game export)")


def place_in(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def linear(rgb):
    def one(x):
        x = x / 255.0
        return x / 12.92 if x < 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return tuple(one(x) for x in rgb) + (1.0,)


def material(name, rgb, roughness=0.90, cloth=False, emission=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = linear(rgb)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    principled = nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = linear(rgb)
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Metallic"].default_value = 0.0
    if emission:
        principled.inputs["Emission Color"].default_value = linear(rgb)
        principled.inputs["Emission Strength"].default_value = emission
    if cloth:
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 145.0
        noise.inputs["Detail"].default_value = 2.0
        noise.inputs["Roughness"].default_value = 0.77
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.16
        bump.inputs["Distance"].default_value = 0.017
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], principled.inputs["Normal"])
        principled.inputs["Sheen Weight"].default_value = 0.38
        principled.inputs["Sheen Roughness"].default_value = 0.89
    return mat


FUR = material("Ink-blue plush | fine textile relief", (14, 22, 75), cloth=True)
FUR_LIGHT = material("Fabric edge | cool violet blue", (31, 41, 95), cloth=True)
FUR_DARK = material("Stitched shadow | navy", (9, 14, 43), cloth=True)
PATCH = material("Faded lilac belly patch", (86, 87, 152), cloth=True)
PADS = material("Soft paw pads | slate mauve", (103, 101, 157), cloth=True)
INNER_EAR = material("Inner ears | lavender grey", (83, 78, 136), cloth=True)
THREAD = material("Cotton thread | faded periwinkle", (108, 110, 164), roughness=1)
MOUTH = material("Velvet mouth cavity", (12, 10, 27))
TONGUE = material("Muted plum tongue", (126, 65, 99), cloth=True)
TOOTH = material("Soft ivory fabric teeth", (216, 216, 212), roughness=.5)
EYE = material("Pale luminous eyes", (189, 241, 255), roughness=.16, emission=2.5)
EYERING = material("Dark stitched eye sockets", (14, 19, 50), roughness=.8)


# Create a small standard armature. All mesh vertices are stored in world space,
# so one armature modifier per part deforms them without fragile bone parenting.
arm_data = bpy.data.armatures.new("Plush_v17_Armature")
rig = bpy.data.objects.new("ARM_Recovered_Plush_v17", arm_data)
CHAR.objects.link(rig)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")


def add_bone(name, head, tail, parent=None, deform=True):
    b = arm_data.edit_bones.new(name)
    b.head = head
    b.tail = tail
    if parent:
        b.parent = arm_data.edit_bones[parent]
    b.use_deform = deform
    return b


add_bone("Root", (0, 0, 0.02), (0, 0, 1.20), deform=False)
add_bone("Pelvis", (0, 0, 1.25), (0, 0, 1.69), "Root")
add_bone("Spine", (0, 0, 1.66), (0, 0, 2.30), "Pelvis")
add_bone("Neck", (0, 0, 2.29), (0, 0, 2.57), "Spine")
add_bone("Head", (0, 0, 2.54), (0, 0, 3.36), "Neck")
add_bone("Jaw", (0, -.66, 2.90), (0, -.69, 2.63), "Head")
for side, sign in (("L", -1), ("R", 1)):
    add_bone(f"UpperArm.{side}", (sign*.70, 0, 2.27), (sign*.88, 0, 1.58), "Spine")
    add_bone(f"Forearm.{side}", (sign*.88, 0, 1.58), (sign*.99, -.04, 1.04), f"UpperArm.{side}")
    add_bone(f"Hand.{side}", (sign*.99, -.04, 1.04), (sign*1.00, -.085, .78), f"Forearm.{side}")
    for fi, offset in enumerate((-.155, 0, .155), 1):
        add_bone(f"Finger{fi}.{side}",
                 (sign*1.00 + offset, -.105, .76),
                 (sign*1.00 + offset*1.08, -.16, .55), f"Hand.{side}")
    add_bone(f"Thumb.{side}", (sign*.84, -.075, .94),
             (sign*.75, -.23, .78), f"Hand.{side}")
    add_bone(f"Thigh.{side}", (sign*.40, 0, 1.36), (sign*.43, 0, .75), "Pelvis")
    add_bone(f"Shin.{side}", (sign*.43, 0, .75), (sign*.44, -.06, .41), f"Thigh.{side}")
    add_bone(f"Foot.{side}", (sign*.44, -.06, .41), (sign*.44, -.37, .28), f"Shin.{side}")
add_bone("EarBase.L", (-.50, .01, 3.72), (-.55, 0, 4.27), "Head")
add_bone("EarTip.L", (-.55, 0, 4.27), (-.67, 0, 4.85), "EarBase.L")
add_bone("EarBase.R", (.53, .01, 3.72), (.71, -.02, 4.28), "Head")
add_bone("EarTip.R", (.71, -.02, 4.28), (1.22, -.08, 4.12), "EarBase.R")
bpy.ops.object.mode_set(mode="OBJECT")
rig.select_set(False)
rig.show_in_front = False
rig.hide_render = True


def skin(obj, bone, col=CHAR, weights=None):
    place_in(obj, col)
    if obj.type != "MESH":
        raise RuntimeError(f"Expected mesh: {obj.name}")
    if weights is None:
        weights = [{bone: 1.0} for _ in obj.data.vertices]
    names = {name for d in weights for name in d}
    vgs = {n: obj.vertex_groups.new(name=n) for n in names}
    for i, entry in enumerate(weights):
        total = sum(entry.values())
        for n, w in entry.items():
            if w:
                vgs[n].add([i], w / total, "REPLACE")
    mod = obj.modifiers.new("Poseable / armature weights", "ARMATURE")
    mod.object = rig
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def sphere(name, at, scale, mat, bone, col=CHAR, segments=32, rings=20, rotate=(0, 0, 0), shape=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1)
    obj = bpy.context.object
    obj.name = name
    obj.location = at
    obj.scale = scale
    obj.rotation_euler = rotate
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if shape:
        for v in obj.data.vertices:
            shape(v)
    obj.data.materials.append(mat)
    return skin(obj, bone, col)


def mesh(name, vertices, faces, mat, bone, weights=None, col=CHAR):
    dat = bpy.data.meshes.new(name + "_mesh")
    dat.from_pydata(vertices, [], faces)
    dat.update()
    obj = bpy.data.objects.new(name, dat)
    col.objects.link(obj)
    dat.materials.append(mat)
    return skin(obj, bone, col, weights)


def thread_lines(name, segments, mat=THREAD, bone="Head", thickness=.011, col=DETAIL):
    crv = bpy.data.curves.new(name + "_curve", "CURVE")
    crv.dimensions = "3D"
    crv.resolution_u = 2
    crv.bevel_depth = thickness
    crv.resolution_u = 2
    crv.bevel_resolution = 2
    for points in segments:
        if len(points) < 2:
            continue
        sp = crv.splines.new("POLY")
        sp.points.add(len(points) - 1)
        for p, loc in zip(sp.points, points):
            p.co = (*loc, 1)
    obj = bpy.data.objects.new(name, crv)
    col.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    obj.data.materials.append(mat)
    skin(obj, bone, col)
    obj.select_set(False)
    return obj


def catmull(points, subdivisions=5):
    p = [Vector(a) for a in points]
    out = []
    for i in range(len(p) - 1):
        a = p[max(0, i-1)]; b=p[i]; c=p[i+1]; d=p[min(len(p)-1,i+2)]
        for j in range(subdivisions):
            t = j/subdivisions
            out.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
    out.append(p[-1])
    return out


def ribbon_tube(name, points, width, depth, mat, bones, split_at=.53, col=CHAR):
    centers = catmull(points, 5)
    n = len(centers)
    resolution = 16
    vertices=[]; faces=[]; weights=[]
    for i, center in enumerate(centers):
        t=i/(n-1)
        tang=(centers[min(i+1,n-1)]-centers[max(0,i-1)]).normalized()
        # For all ears and drooping sleeve tubes, the horizontal axis is across the fabric.
        across=Vector((1,0,0))
        across=(across-tang*across.dot(tang)).normalized()
        deep=tang.cross(across).normalized()
        envelope=math.sin(math.pi*t)**.48
        w=width(t)*envelope if callable(width) else width*envelope
        dep=depth(t)*envelope if callable(depth) else depth*envelope
        for j in range(resolution):
            a=2*math.pi*j/resolution
            vert=center+across*w*math.cos(a)+deep*dep*math.sin(a)
            vertices.append(tuple(vert))
            # Blend around the flexible joint, so the shape doesn't hinge like a rod.
            u=max(0.0,min(1.0,(t-(split_at-.16))/.32))
            weights.append({bones[0]:1-u,bones[1]:u} if u>0 and u<1 else
                           {bones[0]:1.0} if u<=0 else {bones[1]:1.0})
        if i:
            for j in range(resolution):
                k=(j+1)%resolution
                faces.append(((i-1)*resolution+j,(i-1)*resolution+k,i*resolution+k,i*resolution+j))
    faces.extend([tuple(reversed(range(resolution))),tuple((n-1)*resolution+j for j in range(resolution))])
    return mesh(name,vertices,faces,mat,bones[0],weights,col)


def ear_panel(name, points, mat, bones):
    """A narrow curved fabric inset lying on the ear surface (not a second tube)."""
    centers=catmull(points,5)
    verts=[]; weights=[]; faces=[]
    for i,center in enumerate(centers):
        t=i/(len(centers)-1)
        tangent=(centers[min(len(centers)-1,i+1)]-centers[max(i-1,0)]).normalized()
        across=Vector((1,0,0)); across=(across-tangent*across.dot(tangent)).normalized()
        deep=tangent.cross(across).normalized()
        w=.104*math.sin(math.pi*t)**.65
        for s in (-1,1):
            v=center + s*w*across - .117*deep
            verts.append(tuple(v))
            blend=max(0,min(1,(t-.38)/.30))
            weights.append({bones[0]:1-blend,bones[1]:blend} if 0<blend<1 else
                           {bones[0]:1} if blend<=0 else {bones[1]:1})
        if i:
            faces.append((2*i-2,2*i-1,2*i+1,2*i))
    return mesh(name,verts,faces,mat,bones[0],weights,col=DETAIL)


def torso_shape(v):
    z=(v.co.z-1.81)/.88
    if z>.1:
        v.co.x*=1-.11*min(1,z)
    if v.co.y<0:
        v.co.y-=.035*(1-z*z)


sphere("Torso / one soft silhouette",(0,0,1.81),(.81,.60,.88),FUR,"Spine", shape=torso_shape)
sphere("Lower tummy fill",(0,.03,1.39),(.67,.56,.42),FUR,"Pelvis")
sphere("Neck / plush bridge",(0,0,2.40),(.42,.42,.31),FUR,"Neck")


def head_shape(v):
    z=(v.co.z-3.15)/.79
    # Generous soft cheeks, but a less spherical top.
    v.co.x*=1+.085*(-z)
    v.co.y*=1+.024*(-z)


sphere("Big soft head / cheek sculpt",(0,-.012,3.15),(.88,.71,.80),FUR,"Head", shape=head_shape)


def face_y(x,z):
    d=(x/.935)**2 + ((z-3.15)/.81)**2
    return -.012-.71*math.sqrt(max(.025,1-d))-.025


# Ears: one alert and tall, the other folded over.
ribbon_tube("Ear L / tall soft taper",
            [(-.50,.02,3.77),(-.53,.03,4.02),(-.56,.02,4.31),(-.60,.035,4.64),(-.65,.06,4.84)],
            lambda t:.235*(1-.30*t),lambda t:.113*(1-.45*t),FUR,
            ("EarBase.L","EarTip.L"),.53)
ribbon_tube("Ear R / flopped and heavy",
            [(.53,.02,3.77),(.62,.01,4.04),(.75,-.03,4.30),(.97,-.05,4.37),(1.19,-.055,4.22)],
            lambda t:.238*(1-.27*t),lambda t:.117*(1-.36*t),FUR,
            ("EarBase.R","EarTip.R"),.55)

# An interior strip follows the surface, rather than extruding a blocky inset.
ear_panel("Ear front soft insert L",
          [(-.50,.02,3.77),(-.53,.03,4.02),(-.56,.02,4.31),(-.60,.035,4.64),(-.65,.06,4.84)],
          INNER_EAR,("EarBase.L","EarTip.L"))
ear_panel("Ear front soft insert R",
          [(.53,.02,3.77),(.62,.01,4.04),(.75,-.03,4.30),(.97,-.05,4.37),(1.19,-.055,4.22)],
          INNER_EAR,("EarBase.R","EarTip.R"))

# Glowing circular eyes with dark embroidered rims.
for side, sgn in (("L",-1),("R",1)):
    x=sgn*.335; z=3.37; y=face_y(x,z)-.055
    sphere(f"Eye socket {side}",(x,y+.023,z),(.174,.061,.182),EYERING,"Head",DETAIL)
    sphere(f"Glowing eye {side}",(x,y-.022,z),(.130,.049,.142),EYE,"Head",DETAIL)
    sphere(f"Small eye reflection {side}",(x-.037,y-.066,z+.047),(.033,.015,.037),TOOTH,"Head",DETAIL, segments=16,rings=12)
    sphere(f"Round cheek {side}",(sgn*.53,face_y(sgn*.53,3.01)-.032,3.015),(.23,.04,.14),FUR_LIGHT,"Head",DETAIL)

sphere("Soft stitched nose",(0,face_y(0,3.12)-.055,3.12),(.102,.060,.066),PATCH,"Head",DETAIL)

# Mouth cavity remains on the head. Jaw and its lower teeth follow the Jaw bone.
mouth_cavity=sphere("Mouth cavity / dark fabric",(0,face_y(0,2.86)-.055,2.84),(.600,.060,.120),MOUTH,"Head",DETAIL)
sphere("Tongue inside mouth",(0,face_y(0,2.80)-.12,2.772),(.275,.028,.062),TONGUE,"Head",DETAIL)
sphere("Movable lower jaw / fabric",(0,face_y(0,2.72)-.010,2.68),(.61,.24,.17),FUR,"Jaw",DETAIL)

teeth=[]
for i in range(7):
    x=(i-3)*.145
    z=2.897+.035*(abs(x)/.45)**1.6
    y=face_y(x,z)-.112
    teeth.append(sphere(f"Top tooth {i+1}",(x,y+.018,z-.028),(.039,.036,.064),TOOTH,"Head",DETAIL,segments=16,rings=12))
    if i in (0,2,4,6):
        teeth.append(sphere(f"Lower tooth {i+1}",(x,face_y(x,2.74)-.080,2.753),(.038,.035,.056),TOOTH,"Jaw",DETAIL,segments=16,rings=12))


def jaw_driver(key):
    fcurve=key.driver_add("value")
    d=fcurve.driver
    d.type="SCRIPTED"
    var=d.variables.new()
    var.name="jaw_z"
    var.type="TRANSFORMS"
    var.targets[0].id=rig
    var.targets[0].bone_target="Jaw"
    var.targets[0].transform_type="LOC_Z"
    var.targets[0].transform_space="LOCAL_SPACE"
    d.expression="max(0,min(1,-jaw_z/0.29))"


# Opening the jaw also exposes the mouth cavity and teeth. In ordinary walk
# poses the stitched grin is narrow and the teeth are concealed.
mouth_cavity.shape_key_add(name="Basis",from_mix=False)
open_cavity=mouth_cavity.shape_key_add(name="MouthOpen",from_mix=False)
for i,v in enumerate(mouth_cavity.data.vertices):
    orig=v.co.copy()
    mouth_cavity.data.shape_keys.key_blocks["Basis"].data[i].co.z=2.84+(orig.z-2.84)*.24
    open_cavity.data[i].co.z=2.84+(orig.z-2.84)*2.00
jaw_driver(open_cavity)
for tooth in teeth:
    original=[v.co.copy() for v in tooth.data.vertices]
    mid=sum(original,Vector())/len(original)
    tooth.shape_key_add(name="Basis",from_mix=False)
    show=tooth.shape_key_add(name="ShowWhenJawOpens",from_mix=False)
    for i,v in enumerate(original):
        tooth.data.shape_keys.key_blocks["Basis"].data[i].co=mid+(v-mid)*.02+Vector((0,.15,0))
        show.data[i].co=v
    jaw_driver(show)

# A smile-shaped dark embroidered mouth line, cheek stitching and brows.
smile=[]
for j in range(31):
    x=-.65+1.30*j/30
    z=2.93-.085*(1-(x/.65)**2)
    smile.append((x,face_y(x,z)-.066,z))
thread_lines("Smiling upper lip | embroidered",[smile],FUR_DARK,"Head",.019)
thread_lines("Lower smile welt",[[(x,face_y(x,2.74)-.092,2.74-.025*(1-(x/.57)**2))
                 for x in (-.57,-.45,-.30,-.15,0,.15,.30,.45,.57)]],FUR_DARK,"Jaw",.015)
smile_stitches=[]
for side,sign in (("L",-1),("R",1)):
    for i in range(4):
        x=sign*(.54+i*.065)
        z=2.925+i*.047
        y=face_y(x,z)-.070
        smile_stitches.append([(x-.031,y-.002,z-.027),(x+.030,y-.005,z+.028)])
thread_lines("Short cheek sutures / both sides",smile_stitches,THREAD,"Head",.011)

# Belly inset follows the surface of the elliptical torso without a hard plate edge.
def belly_front(x,z):
    q=(x/.82)**2+((z-1.81)/.88)**2
    return -.60*math.sqrt(max(.025,1-q))-.060

patch_verts=[(0,belly_front(0,1.80)-.022,1.80)]
for i in range(48):
    a=2*math.pi*i/48
    x=.455*math.cos(a)
    z=1.79+.465*math.sin(a)
    patch_verts.append((x,belly_front(x,z)-.050,z))
patch_faces=[(0,1+i,1+(i+1)%48) for i in range(48)]
mesh("Belly patch | sewn into torso",patch_verts,patch_faces,PATCH,"Spine",col=DETAIL)

seams=[]
for i in range(48):
    a=2*math.pi*i/48
    b=2*math.pi*(i+1)/48
    aa=(.455*math.cos(a),1.79+.465*math.sin(a))
    bb=(.455*math.cos(b),1.79+.465*math.sin(b))
    seams.append([(aa[0],belly_front(*aa)-.042,aa[1]),(bb[0],belly_front(*bb)-.042,bb[1])])
thread_lines("Belly patch rim / cotton seam",seams,THREAD,"Spine",.012)
short=[]
for i in range(24):
    a=2*math.pi*i/24
    def pf(r):
        x=r*math.cos(a); z=1.79+r*1.025*math.sin(a)
        return x,belly_front(x,z)-.053,z
    short.append([pf(.422),pf(.497)])
thread_lines("Belly patch individual tack stitches",short,THREAD,"Spine",.014)


# Long loose sleeves and rounded paws are deliberately larger than the legs.
for side,sgn in (("L",-1),("R",1)):
    ribbon_tube(f"Soft continuous sleeve {side}",
                [(sgn*.70,0,2.29),(sgn*.80,0,2.05),(sgn*.86,.0,1.75),
                 (sgn*.92,-.015,1.43),(sgn*.99,-.045,1.08)],
                lambda t:.257+.025*math.sin(math.pi*t),
                lambda t:.247+.025*math.sin(math.pi*t),FUR,
                (f"UpperArm.{side}",f"Forearm.{side}"),.53)
    sphere(f"Padded shoulder {side}",(sgn*.75,0,2.19),(.254,.258,.286),FUR,
           f"UpperArm.{side}")
    sphere(f"Paw palm {side}",(sgn*1.00,-.080,.88),(.282,.242,.266),FUR,
           f"Hand.{side}")
    for i,off in enumerate((-.160,0,.160),1):
        x=sgn*1.00+off
        sphere(f"Soft paw finger {i} {side}",(x,-.121,.663),(.112,.158,.210),FUR,
               f"Finger{i}.{side}",segments=24,rings=16)
        sphere(f"Finger pad {i} {side}",(x,-.258,.611),(.072,.032,.080),PADS,
               f"Finger{i}.{side}",DETAIL,segments=20,rings=12)
    sphere(f"Paw thumb {side}",(sgn*.765,-.173,.82),(.137,.145,.176),FUR,
           f"Thumb.{side}",segments=24,rings=16,rotate=(.26,0,sgn*.34))
    sphere(f"Thumb pad {side}",(sgn*.735,-.283,.79),(.077,.033,.090),PADS,
           f"Thumb.{side}",DETAIL,segments=20,rings=12)
    sphere(f"Main palm pad {side}",(sgn*1.00,-.318,.84),(.169,.035,.142),PADS,
           f"Hand.{side}",DETAIL)

    # Narrow sleeve seam: textile tailoring, not glove cuffs.
    cuff=[]
    for i in range(37):
        a=2*math.pi*i/36
        cuff.append((sgn*.99+.222*math.cos(a),-.047+.228*math.sin(a),1.057))
    thread_lines(f"Wrist sewing {side}",[cuff],FUR_LIGHT,f"Forearm.{side}",.006)

    # Short plush legs and substantial rounded foot paws with three front toes.
    ribbon_tube(f"Stuffed leg {side}",
                [(sgn*.40,.02,1.42),(sgn*.43,0,1.13),(sgn*.43,0,.85),(sgn*.44,-.055,.40)],
                lambda t:.290-.056*t,lambda t:.260-.025*t,FUR,
                (f"Thigh.{side}",f"Shin.{side}"),.50)
    sphere(f"Round foot {side}",(sgn*.44,-.260,.263),(.307,.435,.250),FUR,
           f"Foot.{side}")
    for i,off in enumerate((-.166,0,.166),1):
        sphere(f"Stuffed foot toe {i} {side}",(sgn*.44+off,-.542,.218),(.111,.158,.143),FUR,
               f"Foot.{side}",segments=24,rings=16)
        sphere(f"Toe embroidery {i} {side}",(sgn*.44+off,-.682,.217),(.067,.014,.067),PADS,
               f"Foot.{side}",DETAIL,segments=20,rings=12)
    sphere(f"Sewn fabric sole {side}",(sgn*.44,-.290,.065),(.245,.331,.024),PADS,
           f"Foot.{side}",DETAIL,segments=28,rings=16)

    # Ankle stitching around the top of the sock-like foot.
    ankle=[]
    for i in range(33):
        a=2*math.pi*i/32
        ankle.append((sgn*.44+.225*math.cos(a),-.084+.228*math.sin(a),.435))
    thread_lines(f"Ankle fabric seam {side}",[ankle],THREAD,f"Shin.{side}",.010)

sphere("Tiny stuffed bunny tail",(0,.594,1.39),(.222,.218,.214),FUR_LIGHT,"Pelvis")


# Optional environment only for previews: never exported with the character.
studio_mat = material("Studio floor | muted grey blue", (75, 85, 103), roughness=.98)
bpy.ops.mesh.primitive_plane_add(size=200, location=(0,0,-.012))
floor=bpy.context.object
floor.name="STUDIO / floor"
floor.data.materials.append(studio_mat)
place_in(floor,STUDIO)


def area(name, loc, power, scale, color):
    d=bpy.data.lights.new(name,"AREA")
    o=bpy.data.objects.new(name,d)
    STUDIO.objects.link(o)
    o.location=loc
    direction=Vector((0,0,2.35))-o.location
    o.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()
    d.energy=power; d.shape="DISK"; d.size=scale; d.color=color


area("Large softbox / key",(-3.7,-5,6),680,4.2,(.78,.85,1))
area("Warm softbox / fill",(3.8,-2,4.2),440,3.7,(1,.82,.85))
area("Blue edge light",(.0,3.7,4.8),900,3.0,(.58,.70,1))


def camera(name, at, target, ortho=6.0):
    d=bpy.data.cameras.new(name)
    o=bpy.data.objects.new(name,d)
    STUDIO.objects.link(o)
    o.location=at
    direction=Vector(target)-o.location
    o.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()
    d.type="ORTHO"; d.ortho_scale=ortho
    return o


hero_cam=camera("Hero / three-quarter",(6.4,-9,4.2),(0,0,2.40),5.65)
front_cam=camera("Front / proportions",(0,-10,3.70),(0,0,2.42),5.60)
side_cam=camera("Side / gait",(9,-.01,3.45),(0,0,2.40),5.60)
scene.camera=hero_cam


# Rig actions (in place): the game engine, rather than these actions, moves the NPC.
for pb in rig.pose.bones:
    pb.rotation_mode="XYZ"


def reset_pose():
    for pb in rig.pose.bones:
        pb.location=(0,0,0)
        pb.rotation_euler=(0,0,0)
        pb.scale=(1,1,1)


def apply_pose(values, frame):
    reset_pose()
    for name,prop in values.items():
        pb=rig.pose.bones[name]
        if "r" in prop: pb.rotation_euler=prop["r"]
        if "l" in prop: pb.location=prop["l"]
    for name,prop in values.items():
        pb=rig.pose.bones[name]
        if "r" in prop: pb.keyframe_insert(data_path="rotation_euler",frame=frame,group=name)
        if "l" in prop: pb.keyframe_insert(data_path="location",frame=frame,group=name)


def new_action(name):
    action=bpy.data.actions.new(name)
    if not rig.animation_data: rig.animation_data_create()
    rig.animation_data.action=action
    return action


def key_walk(t,frame):
    cycle=2*math.pi*t
    left=math.sin(cycle)
    bounce=.010*(1-math.cos(2*cycle))
    p={"Pelvis":{"l":(.027*math.sin(cycle),0,bounce-.018),"r":(0,.022*math.sin(cycle),.012*math.sin(cycle))},
       "Spine":{"r":(.018*math.sin(cycle+.6),0,-.030*math.sin(cycle))},
       "Head":{"r":(.023*math.sin(cycle-.5),0,.012*math.sin(cycle))},
       "Thigh.L":{"r":(.18*left,0,0)},
       "Thigh.R":{"r":(-.18*left,0,0)},
       "Shin.L":{"r":(-.04-.095*max(0,-left),0,0)},
       "Shin.R":{"r":(-.04-.095*max(0,left),0,0)},
       "Foot.L":{"r":(-.075*left,0,0)},
       "Foot.R":{"r":(.075*left,0,0)},
       "UpperArm.L":{"r":(-.20*left,0,.019)},
       "UpperArm.R":{"r":(.20*left,0,-.019)},
       "Forearm.L":{"r":(-.075-.045*max(0,left),0,0)},
       "Forearm.R":{"r":(-.075-.045*max(0,-left),0,0)},
       "EarTip.L":{"r":(.048*math.sin(cycle-1.1),0,-.055*math.sin(cycle-1))},
       "EarTip.R":{"r":(.082*math.sin(cycle-1.0),0,.040*math.sin(cycle-.8))}}
    apply_pose(p,frame)


walk=new_action("AN_v17_Walk_InPlace_40f_24fps")
for f in (1,6,11,16,21,26,31,36,41):
    key_walk((f-1)/40,f)
walk.use_fake_user=True

idle=new_action("AN_v17_Idle_Breath_96f")
for f in (1,25,49,73,97):
    t=(f-1)/96*2*math.pi
    apply_pose({"Spine":{"l":(0,0,.021*math.sin(t)),"r":(.012*math.sin(t),0,0)},
                "Head":{"r":(.014*math.sin(t+.8),0,.016*math.sin(t*.5))},
                "EarTip.L":{"r":(.025*math.sin(t-.4),0,0)},
                "EarTip.R":{"r":(.035*math.sin(t-1.0),0,0)}},f)
idle.use_fake_user=True

jaw_action=new_action("AN_v17_Jaw_Open_Close_32f")
for f,openness in ((1,0),(9,.8),(17,1),(24,.45),(33,0)):
    apply_pose({"Jaw":{"l":(0,-.015*openness,-.29*openness),
                        "r":(-.07*openness,0,0)},
                "Head":{"r":(-.045*openness,0,0)}},f)
jaw_action.use_fake_user=True

alert=new_action("AN_v17_Alert_32f")
for f,level in ((1,0),(8,.8),(13,1),(21,.9),(33,.8)):
    apply_pose({"Spine":{"r":(-.065*level,0,0)},
                "Head":{"r":(-.16*level,0,.04*level)},
                "UpperArm.L":{"r":(-.04*level,0,-.08*level)},
                "UpperArm.R":{"r":(-.04*level,0,.08*level)},
                "EarBase.R":{"r":(-.09*level,0,-.11*level)}},f)
alert.use_fake_user=True

# Restore the default preview to the walk cycle and make the scene easy to use.
rig.animation_data.action=walk
scene.frame_set(1)
bpy.ops.object.select_all(action="DESELECT")
rig.select_set(True)
bpy.context.view_layer.objects.active=rig

# Documentation lives inside Blender too.
txt=bpy.data.texts.new("READ_ME_FIRST.txt")
txt.write("Recovered plush rabbit monster v17 | NOT the missing v16 binary.\n")
txt.write("Scene rebuilt from written conversation notes, Blender 4.3.2.\n")
txt.write("Rig: ARM_Recovered_Plush_v17; 4 Actions in Action Editor.\n")
txt.write("AN_v17_Walk_InPlace_40f_24fps: 1..41, mouth closed, motion in-place.\n")
txt.write("AN_v17_Jaw_Open_Close_32f: jaw opening; see frames 1..33.\n")
txt.write("Other actions: Idle_Breath and Alert.\n")
txt.write("Hidden photo studio collection is NOT part of the game asset.\n")
txt.write("Not game-ready: topology, IK foot locking, Roblox export, collision are TODO.\n")

scene.render.filepath="//Plush-v17-Hero.png"
blend_path=OUT/"Plush-v17-Reconstruction.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path),compress=True)
print("BLEND_SAVED",blend_path,blend_path.stat().st_size)

# Render representative real Blender frames; do not use AI-generated mockups.
scene.render.filepath=str(OUT/"Plush-v17-Hero.png")
scene.camera=hero_cam
bpy.ops.render.render(write_still=True)
scene.camera=front_cam
scene.render.filepath=str(OUT/"Plush-v17-Front.png")
bpy.ops.render.render(write_still=True)
scene.camera=side_cam
scene.frame_set(11)
scene.render.filepath=str(OUT/"Plush-v17-Walk-Side.png")
bpy.ops.render.render(write_still=True)
rig.animation_data.action=jaw_action
scene.frame_set(17)
scene.camera=hero_cam
scene.render.filepath=str(OUT/"Plush-v17-Open-Mouth.png")
bpy.ops.render.render(write_still=True)

print("DONE",len(bpy.data.objects),len(bpy.data.actions),len(bpy.data.materials))
