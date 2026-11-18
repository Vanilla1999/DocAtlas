"""Reference-guided reconstruction pass on the surviving v17 Blender rig.

Geometry is generated with explicit quad rings and deliberately shaped limbs;
the original v17 file is only READ. The new v18 file is independent.
Blender 5.3.0; materials are node-based and self-contained.
"""

import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "plush_v18"
OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT / "Plush-v17-Reconstruction.blend"))
scene = bpy.context.scene
rig = bpy.data.objects["ARM_Recovered_Plush_v17"]
rig.name = "ARM_Plush_v18_ReferenceMatch"

# All original v17 geometry and studio controls are superseded in this new scene;
# the original file on disk and its four actions are preserved independently.
for obj in list(bpy.data.objects):
    if obj != rig:
        bpy.data.objects.remove(obj, do_unlink=True)
for action in bpy.data.actions:
    if action.name.startswith("AN_v17_"):
        action.name = "LEGACY_" + action.name
        action.use_fake_user = True
if rig.animation_data:
    rig.animation_data.action = None
for pb in rig.pose.bones:
    pb.rotation_mode = 'XYZ'
    pb.location = (0, 0, 0)
    pb.rotation_euler = (0, 0, 0)
    pb.scale = (1, 1, 1)


def col(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c


GEO = col("V18_01 • primary seamless forms")
FACE = col("V18_02 • eyes, teeth and mouth")
SEWN = col("V18_03 • patches, pads, seams")
RENDER = col("V18_04 • preview studio / exclude from export")

# New rest pose matched against the frontal 3-view source frame, crown = 4.78 m.
rest = {
    "Root": ((0,0,.01),(0,0,1.82)),
    "Pelvis": ((0,0,1.77),(0,0,2.18)),
    "Spine": ((0,0,2.11),(0,0,3.12)),
    "Neck": ((0,0,3.07),(0,0,3.47)),
    "Head": ((0,0,3.42),(0,0,4.35)),
    "Jaw": ((0,-.44,3.81),(0,-.44,3.56)),
    "EarBase.L": ((-.45,.03,4.65),(-.48,.04,5.18)),
    "EarTip.L": ((-.48,.04,5.18),(-.57,.08,5.86)),
    "EarBase.R": ((.42,.03,4.65),(.60,.02,5.06)),
    "EarTip.R": ((.60,.02,5.06),(1.23,.03,4.92)),
}
for side,sign in (("L",-1),("R",1)):
    rest.update({
        f"UpperArm.{side}":((sign*.51,0,3.18),(sign*.77,-.01,2.48)),
        f"Forearm.{side}":((sign*.77,-.01,2.48),(sign*.96,-.04,1.82)),
        f"Hand.{side}":((sign*.96,-.04,1.82),(sign*.99,-.04,1.44)),
        f"Thigh.{side}":((sign*.33,0,1.83),(sign*.37,0,.99)),
        f"Shin.{side}":((sign*.37,0,.99),(sign*.38,-.03,.34)),
        f"Foot.{side}":((sign*.38,-.03,.34),(sign*.38,-.34,.22)),
        f"Thumb.{side}":((sign*.82,-.05,1.55),(sign*.74,-.17,1.37)),
    })
    for i, xoff in enumerate((-.155,0,.155),1):
        rest[f"Finger{i}.{side}"] = ((sign*.99+xoff,-.04,1.38),(sign*.99+xoff,-.07,1.16))

bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode="EDIT")
for name,(h,t) in rest.items():
    b=rig.data.edit_bones.get(name)
    if b:
        b.head=h;b.tail=t
for side,sign in (("L",-1),("R",1)):
    for i,xoff in enumerate((-.155,0,.155),1):
        name=f"FingerTip{i}.{side}"
        b=rig.data.edit_bones.new(name)
        b.head=(sign*.99+xoff,-.07,1.16)
        b.tail=(sign*.99+xoff,-.13,.98)
        b.parent=rig.data.edit_bones[f"Finger{i}.{side}"]
    thumb=rig.data.edit_bones.new(f"ThumbTip.{side}")
    thumb.head=(sign*.74,-.17,1.37)
    thumb.tail=(sign*.66,-.26,1.25)
    thumb.parent=rig.data.edit_bones[f"Thumb.{side}"]
bpy.ops.object.mode_set(mode="OBJECT")
rig.show_in_front=False
rig.hide_render=True
rig["MouthOpen"]=0.0
rig.id_properties_ui("MouthOpen").update(min=0.0,max=1.0,description="0 = stitched closed mouth, 1 = wide toothy gape")


def rgba(rgb):
    def ch(n):
        f=n/255
        return f/12.92 if f<.04045 else ((f+.055)/1.055)**2.4
    return (*[ch(c) for c in rgb],1.0)


def mat(name, rgb, roughness=.88, fabric=False, glow=0):
    m=bpy.data.materials.new(name)
    m.diffuse_color=rgba(rgb)
    m.use_nodes=True
    nodes=m.node_tree.nodes
    links=m.node_tree.links
    p=nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value=rgba(rgb)
    p.inputs["Roughness"].default_value=roughness
    p.inputs["Metallic"].default_value=0
    if "Specular IOR Level" in p.inputs:
        p.inputs["Specular IOR Level"].default_value=.14
    if glow:
        p.inputs["Emission Color"].default_value=rgba(rgb)
        p.inputs["Emission Strength"].default_value=glow
    if fabric:
        p.inputs["Sheen Weight"].default_value=.19
        if "Sheen Tint" in p.inputs:
            p.inputs["Sheen Tint"].default_value=rgba(rgb)
        tex=nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value=55
        tex.inputs["Detail"].default_value=2.5
        tex.inputs["Roughness"].default_value=.8
        vor=nodes.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value=105
        mix=nodes.new("ShaderNodeMixRGB")
        mix.blend_type="MULTIPLY"
        mix.inputs[0].default_value=.35
        bump=nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value=.48
        bump.inputs["Distance"].default_value=.045
        links.new(tex.outputs["Fac"],mix.inputs[1])
        links.new(vor.outputs["Distance"],mix.inputs[2])
        links.new(mix.outputs[0],bump.inputs["Height"])
        links.new(bump.outputs["Normal"],p.inputs["Normal"])
        colors=nodes.new("ShaderNodeValToRGB")
        colors.color_ramp.elements[0].position=.22
        colors.color_ramp.elements[1].position=.79
        colors.color_ramp.elements[0].color=tuple(min(.92,c*.69) for c in rgba(rgb)[:3])+(1,)
        colors.color_ramp.elements[1].color=tuple(min(.92,c*1.72) for c in rgba(rgb)[:3])+(1,)
        links.new(tex.outputs["Fac"],colors.inputs["Fac"])
        links.new(colors.outputs["Color"],p.inputs["Base Color"])
    return m


FUR=mat("MAT_Fabric_DeepInkBoucle",(28,35,80),fabric=True)
PATCH=mat("MAT_Fabric_OatmealPatch",(151,133,113),fabric=True)
THREAD=mat("MAT_Thread_WarmTan",(190,159,118),fabric=True)
MOUTH=mat("MAT_Mouth_DeepVelvet",(15,11,24),roughness=1)
IVORY=mat("MAT_Teeth_Ivory",(217,208,174),roughness=.72)
PADS=mat("MAT_Pads_WornCream",(143,129,112),fabric=True)
EYE=mat("MAT_Eyes_WarmGlow",(255,219,153),roughness=.3,glow=3.5)
SOCKET=mat("MAT_Socket_IndigoShadow",(17,21,52),roughness=.9)


def mesh_obj(name,vertices,faces,material,weights=None,collection=GEO):
    dat=bpy.data.meshes.new(name+"_mesh")
    dat.from_pydata(vertices,[],faces)
    dat.update()
    obj=bpy.data.objects.new(name,dat)
    collection.objects.link(obj)
    # Parenting the skinned geometry is essential: moving the whole rig in a
    # Roblox scene must move the rest meshes too (not only rotate bones).
    obj.parent=rig
    dat.materials.append(material)
    if weights is None:
        weights=[{"Spine":1.0}]*len(vertices)
    groups={k:obj.vertex_groups.new(name=k) for k in sorted({k for v in weights for k in v})}
    for i,wmap in enumerate(weights):
        total=sum(wmap.values())
        for k,v in wmap.items():
            if v>0:
                groups[k].add([i],v/total,"REPLACE")
    md=obj.modifiers.new("Skin by v18 rig","ARMATURE")
    md.object=rig
    md.use_deform_preserve_volume=True
    for poly in dat.polygons:
        poly.use_smooth=True
    return obj


def subdiv(obj,level=1):
    md=obj.modifiers.new("Surface smoothing / quads","SUBSURF")
    md.levels=level
    md.render_levels=level
    first_mat=obj.data.materials[0] if obj.data.materials else None
    if first_mat in (FUR,PATCH):
        tx=bpy.data.textures.get("TEX_v18_PlushNubs")
        if tx is None:
            tx=bpy.data.textures.new("TEX_v18_PlushNubs",type="CLOUDS")
            tx.noise_scale=.063
            tx.noise_depth=2
        dp=obj.modifiers.new("Bouclé relief / viewport and render","DISPLACE")
        dp.texture=tx
        dp.texture_coords='LOCAL'
        if obj.name.startswith("V18_Hand."):
            dp.strength=.017
        else:
            dp.strength=.045 if first_mat==FUR else .018
        dp.mid_level=.48


def ellipsoid(name,at,scale,material,bone,collection=GEO,segments=28,rings=18):
    vv=[(at[0],at[1],at[2]+scale[2])];ff=[]
    for i in range(1,rings):
        phi=math.pi*i/rings
        for j in range(segments):
            theta=2*math.pi*j/segments
            vv.append((at[0]+scale[0]*math.sin(phi)*math.cos(theta),
                       at[1]+scale[1]*math.sin(phi)*math.sin(theta),
                       at[2]+scale[2]*math.cos(phi)))
            if i>1:
                a=1+(i-2)*segments+j;b=1+(i-2)*segments+(j+1)%segments
                c=1+(i-1)*segments+(j+1)%segments;d=1+(i-1)*segments+j
                ff.append((a,d,c,b))
    bottom=len(vv)
    vv.append((at[0],at[1],at[2]-scale[2]))
    for j in range(segments):
        ff.append((0,1+j,1+(j+1)%segments))
        lo=1+(rings-2)*segments
        ff.append((lo+j,bottom,lo+(j+1)%segments))
    return mesh_obj(name,vv,ff,material,[{bone:1} for _ in vv],collection)


def tube(name,points,radii_x,radii_y,material,bones,collection=GEO,
         ang=20,subdivisions=5,transitions=None,blend=.14):
    src=[Vector(p) for p in points]
    centers=[]
    for i in range(len(src)-1):
        a=src[max(0,i-1)];b=src[i];c=src[i+1];d=src[min(len(src)-1,i+2)]
        for j in range(subdivisions):
            t=j/subdivisions
            centers.append(.5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
    centers.append(src[-1])
    verts=[];faces=[];weights=[]
    for i,p in enumerate(centers):
        t=i/(len(centers)-1)
        tang=(centers[min(len(centers)-1,i+1)]-centers[max(0,i-1)]).normalized()
        xaxis=Vector((1,0,0))
        xaxis=(xaxis-tang*xaxis.dot(tang)).normalized()
        yaxis=tang.cross(xaxis).normalized()
        def rr(values):
            k=t*(len(values)-1);i0=min(len(values)-2,int(k));f=k-i0
            return values[i0]*(1-f)+values[i0+1]*f
        rx=rr(radii_x);ry=rr(radii_y)
        for j in range(ang):
            angle=2*math.pi*j/ang
            v=p+xaxis*rx*math.cos(angle)+yaxis*ry*math.sin(angle)
            verts.append(tuple(v))
            if len(set(bones))==1:
                weights.append({bones[0]:1})
            else:
                boundaries=transitions or [i/len(bones) for i in range(1,len(bones))]
                assigned=False
                for bi,bound in enumerate(boundaries):
                    if t < bound-blend/2:
                        weights.append({bones[bi]:1});assigned=True;break
                    if t <= bound+blend/2:
                        f=(t-(bound-blend/2))/blend
                        weights.append({bones[bi]:1-f,bones[bi+1]:f})
                        assigned=True;break
                if not assigned:weights.append({bones[-1]:1})
            if i:
                prev=(i-1)*ang+j;nextprev=(i-1)*ang+(j+1)%ang
                curr=i*ang+j;nextcurr=i*ang+(j+1)%ang
                faces.append((prev,nextprev,nextcurr,curr))
    faces.extend([tuple(reversed(range(ang))),tuple((len(centers)-1)*ang+j for j in range(ang))])
    return mesh_obj(name,verts,faces,material,weights,collection)


def lines(name,segments,material,bone,depth=.010,collection=SEWN):
    crv=bpy.data.curves.new(name+"_curve","CURVE")
    crv.dimensions="3D"
    crv.bevel_depth=depth
    crv.bevel_resolution=2
    for path in segments:
        if len(path)<2:continue
        sp=crv.splines.new("POLY")
        sp.points.add(len(path)-1)
        for pt,v in zip(sp.points,path):
            pt.co=(*v,1)
    obj=bpy.data.objects.new(name,crv)
    collection.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.convert(target="MESH")
    obj=bpy.context.object
    obj.data.materials.append(material)
    obj.parent=rig
    # Unlike screenshot-only ornaments, stitches are actually attached to bones.
    vg=obj.vertex_groups.new(name=bone)
    vg.add(list(range(len(obj.data.vertices))),1,"REPLACE")
    md=obj.modifiers.new("Skin stitching","ARMATURE")
    md.object=rig
    md.use_deform_preserve_volume=True
    obj.select_set(False)
    return obj


def drive_mouth(shapekey):
    fc=shapekey.driver_add("value")
    d=fc.driver;d.type="SCRIPTED"
    v=d.variables.new();v.name="aperture";v.type="SINGLE_PROP"
    v.targets[0].id=rig
    v.targets[0].data_path='["MouthOpen"]'
    d.expression="max(0,min(1,aperture))"


# Torso constructed from height-dependent elliptical rings; it is not a stack of balls.
body_profiles=[
    (1.64,.24,.27), (1.73,.39,.35), (1.87,.52,.42),
    (2.07,.60,.44), (2.34,.62,.45), (2.62,.58,.42),
    (2.90,.52,.39), (3.12,.42,.33), (3.33,.30,.26),
]
v=[];f=[];w=[];N=48
for k,(z,rx,ry) in enumerate(body_profiles):
    for i in range(N):
        a=2*math.pi*i/N
        x=rx*math.cos(a)
        y=ry*math.sin(a)
        v.append((x,y,z))
        if z<2.10:w.append({"Pelvis":1.0})
        elif z<2.40:
            q=(z-2.10)/.30;w.append({"Pelvis":1-q,"Spine":q})
        else:w.append({"Spine":1.0})
        if k:
            prev=(k-1)*N+i;pn=(k-1)*N+(i+1)%N
            curr=k*N+i;cn=k*N+(i+1)%N
            f.append((prev,pn,cn,curr))
f.append(tuple(reversed(range(N))))
f.append(tuple((len(body_profiles)-1)*N+i for i in range(N)))
torso=mesh_obj("V18_Torso",v,f,FUR,w)
subdiv(torso,2)
neck=tube("V18_NeckBridge",[(0,0,3.06),(0,0,3.22),(0,0,3.38),(0,0,3.53)],
          [.245,.255,.285,.320],[.24,.255,.285,.31],FUR,
          ["Spine","Neck","Head"],ang=32,subdivisions=5)
subdiv(neck,1)


# The head is a continuous closed shell with an actual inward mouth tunnel.
# Front annulus and cavity share one perimeter: no dark polygon is glued on top.
HC=4.06;HX=.79;HZ=.72;HY=.62;MO=3.80;SEGS=64;FR=14;BR=13;CR=6
closed=[];opened=[];faces=[]
def front_coord(t,phi,opening):
    c=math.cos(phi);s=math.sin(phi)
    inner_w=.66+.018*opening
    inner_h=.035+.340*opening
    inner_z=3.82-.025*opening
    xi=inner_w*c;zi=inner_z+inner_h*s
    xo=HX*c;zo=HC+HZ*s
    x=xi+(xo-xi)*t
    z=zi+(zo-zi)*t
    q=min(.999,(x/HX)**2+((z-HC)/HZ)**2)
    y=-HY*math.sqrt(1-q)
    # The near lip protrudes minimally; cheeks remain soft instead of a muzzle.
    y-=.018*(1-t)**2
    return (x,y,z)
for k in range(FR+1):
    t=k/FR
    for j in range(SEGS):
        a=2*math.pi*j/SEGS
        closed.append(front_coord(t,a,0))
        opened.append(front_coord(t,a,1))
        if k:
            last=(k-1)*SEGS+j;lastn=(k-1)*SEGS+(j+1)%SEGS
            curr=k*SEGS+j;currn=k*SEGS+(j+1)%SEGS
            faces.append((last,curr,currn,lastn))
outer_start=len(closed)-SEGS
for k in range(1,BR+1):
    alpha=(math.pi/2)*k/(BR+1)
    rr=math.cos(alpha);y=HY*math.sin(alpha)
    ring_start=len(closed)
    for j in range(SEGS):
        a=2*math.pi*j/SEGS
        pt=(HX*rr*math.cos(a),y,HC+HZ*rr*math.sin(a))
        closed.append(pt);opened.append(pt)
    for j in range(SEGS):
        prev=outer_start+j if k==1 else ring_start-SEGS+j
        prevn=outer_start+(j+1)%SEGS if k==1 else ring_start-SEGS+(j+1)%SEGS
        faces.append((prev,ring_start+j,ring_start+(j+1)%SEGS,prevn))
# A single pole gives the back of the head a real closed, non-degenerate cap.
rear_pole=len(closed)
closed.append((0,HY,HC));opened.append((0,HY,HC))
last_ring=outer_start+BR*SEGS
for j in range(SEGS):
    faces.append((last_ring+j,rear_pole,last_ring+(j+1)%SEGS))
# Aperture tunnel: inside normals face the cavity. The throat ends in a closed cap.
for k in range(1,CR+1):
    t=k/CR
    ring_start=len(closed)
    for j in range(SEGS):
        a=2*math.pi*j/SEGS
        c=front_coord(0,a,0);o=front_coord(0,a,1)
        def tunnel(p,opening):
            x,y,z=p
            q=1-.88*t
            return (x*q,y+.53*t, (3.82-.025*opening)+(z-(3.82-.025*opening))*q)
        closed.append(tunnel(c,0));opened.append(tunnel(o,1))
    for j in range(SEGS):
        prev=j if k==1 else ring_start-SEGS+j
        prevn=(j+1)%SEGS if k==1 else ring_start-SEGS+(j+1)%SEGS
        faces.append((prev,prevn,ring_start+(j+1)%SEGS,ring_start+j))
last_inner_ring=len(closed)-SEGS
throat_pole=len(closed)
closed.append((0,-HY+.53,3.82));opened.append((0,-HY+.53,3.795))
for j in range(SEGS):
    faces.append((last_inner_ring+(j+1)%SEGS,throat_pole,last_inner_ring+j))
head=mesh_obj("V18_Head",closed,faces,FUR,[{"Head":1} for _ in closed])
head.shape_key_add(name="Basis",from_mix=False)
open_key=head.shape_key_add(name="MouthOpen",from_mix=False)
for i,pt in enumerate(opened):
    open_key.data[i].co=pt
drive_mouth(open_key)
subdiv(head,1)
# Narrow mouth-lip loops are smaller than typical fleece tufts. Protect their
# topology from displacement while retaining visible boucle on the head.
mask=head.vertex_groups.new(name="V18_HeadBoucleMask")
front_count=(FR+1)*SEGS
back_count=BR*SEGS+1
for i in range(len(head.data.vertices)):
    if i<front_count:
        t=(i//SEGS)/FR
        amount=t*t*(3-2*t)
    elif i<front_count+back_count:
        amount=1.0
    else:
        amount=0.0
    mask.add([i],max(.001,amount),'REPLACE')
head.modifiers.get("Bouclé relief / viewport and render").vertex_group=mask.name

# The inner tunnel uses a second material on its own polygons (same manifold).
head.data.materials.append(MOUTH)
for poly in head.data.polygons:
    if poly.index>=FR*SEGS+BR*SEGS+SEGS:
        poly.material_index=1


print("V18_CORE_READY",len(head.data.vertices),len(torso.data.vertices))


# Two thick textile ears, one upright and one smoothly folded over.
left_ear=[(-.45,.03,4.63),(-.47,.03,4.83),(-.50,.04,5.15),
          (-.53,.06,5.48),(-.56,.08,5.76),(-.58,.08,5.84)]
right_ear=[(.43,.03,4.64),(.45,.03,4.80),(.52,.04,4.98),
           (.70,.04,5.08),(.95,.05,5.07),(1.18,.06,4.91)]
for side,pts in (("L",left_ear),("R",right_ear)):
    ear=tube(f"V18_Ear.{side}",pts,[.15,.20,.22,.215,.16,.06],[.12,.15,.17,.17,.14,.055],
             FUR,[f"EarBase.{side}",f"EarTip.{side}"],ang=24,subdivisions=6)
    subdiv(ear,1)
    # A subtle longitudinal seam (the upright ear additionally has tan cross-stitches).
    centerline=[]
    for i,p in enumerate(pts):
        centerline.append((p[0],p[1]-.205,p[2]))
    lines(f"V18_Ear_Seam.{side}",[centerline],SOCKET,f"EarBase.{side}",.007)
upright_stitches=[]
for i in range(9):
    t=(i+1)/11
    z=4.75+(5.65-4.75)*t
    x=-.46-.095*t
    upright_stitches.append([(x-.087,-.205,z-.020),(x+.087,-.205,z+.020)])
lines("V18_Ear_TanStitches",upright_stitches,THREAD,"EarBase.L",.014)


# Continuous, non-segmented sleeves. Upper rings are recessed in the torso,
# with gentle blending across upper/forearm/hand bone influences.
for side,sign in (("L",-1),("R",1)):
    path=[(sign*.43,.01,3.22),(sign*.54,0,3.06),(sign*.73,-.01,2.65),
          (sign*.82,-.02,2.40),(sign*.95,-.04,1.90),(sign*.97,-.04,1.73)]
    ob=tube(f"V18_Arm.{side}",path,[.21,.265,.245,.23,.20,.165],
            [.22,.255,.24,.23,.21,.17],FUR,
            [f"UpperArm.{side}",f"Forearm.{side}",f"Hand.{side}"],
            ang=24,subdivisions=6,transitions=[.49,.92],blend=.18)
    subdiv(ob,1)
    # One arm seam near the elbow, one near the wrist (without hard cuffs).
    stitched=[]
    for cz,cx,r in ((2.63,sign*.75,.232),(1.84,sign*.96,.205)):
        for i in range(9):
            a=2*math.pi*i/9
            xx=cx+r*math.cos(a)
            yy=-.03+r*math.sin(a)
            stitched.append([(xx,yy,cz-.038),(xx,yy,cz+.038)])
    lines(f"V18_Arm_TackSeams.{side}",stitched,THREAD,f"Forearm.{side}",.013)


def hand_geometry(side,sign):
    """One coherent quad-dominant palm + fingers + thumb shell.

    Three 2x2 bottom quad patches and a side thumb patch are genuine holes in
    the palm cage, extruded to closed loops. No detached marbles/finger balls.
    """
    nx,ny,nz=12,4,6
    cx=sign*.99;cy=-.04
    width=.53;depth=.36;zlo=1.365;zhi=1.83
    vx=[];faces=[];weights=[];cache={}
    def coord(i,j,k):
        # Smooth square-to-disc mapping: round fingertips of the palm without
        # detaching their real extrusion loops from the palm's topology.
        u=2*i/nx-1;v=2*j/ny-1
        wrist=1-.19*(k/nz)**1.5
        xx=cx+.5*width*wrist*u*math.sqrt(1-v*v/2)
        yy=cy+.5*depth*v*math.sqrt(1-u*u/2)
        zz=zlo+(zhi-zlo)*k/nz
        return (xx,yy,zz)
    def get(i,j,k):
        key=(i,j,k)
        if key not in cache:
            cache[key]=len(vx)
            vx.append(coord(i,j,k))
            weights.append({f"Hand.{side}":1})
        return cache[key]
    root_i=(1,5,9)
    def finger_hole(i,j):
        return any(i0<=i<i0+2 for i0 in root_i) and 1<=j<3
    xthumb=nx if sign<0 else 0
    def thumb_hole(j,k):
        return 1<=j<3 and 1<=k<3
    # The six parametric box surfaces, with individual finger/thumb openings.
    for i in range(nx):
        for j in range(ny):
            if not finger_hole(i,j):
                faces.append((get(i,j,0),get(i,j+1,0),get(i+1,j+1,0),get(i+1,j,0)))
            faces.append((get(i,j,nz),get(i+1,j,nz),get(i+1,j+1,nz),get(i,j+1,nz)))
    for i in range(nx):
        for k in range(nz):
            faces.append((get(i,0,k),get(i+1,0,k),get(i+1,0,k+1),get(i,0,k+1)))
            faces.append((get(i,ny,k),get(i,ny,k+1),get(i+1,ny,k+1),get(i+1,ny,k)))
    for j in range(ny):
        for k in range(nz):
            if not (xthumb==0 and thumb_hole(j,k)):
                faces.append((get(0,j,k),get(0,j,k+1),get(0,j+1,k+1),get(0,j+1,k)))
            if not (xthumb==nx and thumb_hole(j,k)):
                faces.append((get(nx,j,k),get(nx,j+1,k),get(nx,j+1,k+1),get(nx,j,k+1)))
    # A closed 8-point boundary around each 2x2 finger patch.
    for n,i0 in enumerate(root_i,1):
        boundary=[(i0,1),(i0+1,1),(i0+2,1),(i0+2,2),
                  (i0+2,3),(i0+1,3),(i0,3),(i0,2)]
        previous=[get(i,j,0) for i,j in boundary]
        midx=sum(coord(i,j,0)[0] for i,j in boundary)/8
        midy=cy
        first=f"Finger{n}.{side}"; tip=f"FingerTip{n}.{side}"
        for ring in range(1,7):
            t=ring/6
            cur=[]
            for i,j in boundary:
                xyz=coord(i,j,0)
                a=math.atan2((xyz[1]-midy)/(.10),(xyz[0]-midx)/(.075))
                widthr=(.095*(1-.24*t))*math.sin(math.pi*(.23+.73*t))**.10
                depthr=.112*(1-.30*t)
                xx=midx+widthr*math.cos(a)
                yy=midy+depthr*math.sin(a)-.162*t*t
                zz=zlo-.325*t
                cur.append(len(vx))
                vx.append((xx,yy,zz))
                if t<.45: weights.append({first:1})
                elif t<.65:weights.append({first:.5,tip:.5})
                else:weights.append({tip:1})
            for j in range(8):
                faces.append((previous[j],previous[(j+1)%8],cur[(j+1)%8],cur[j]))
            previous=cur
        # No n-gon; the tiny fingertip cap triangulates to an actual tip point.
        cap=len(vx)
        vx.append((midx,midy-.165,zlo-.333))
        weights.append({tip:1})
        for j in range(8):faces.append((previous[j],previous[(j+1)%8],cap))
    # Thumb exits the palm's inner lateral surface through its own real hole.
    jjkk=[(1,1),(2,1),(3,1),(3,2),(3,3),(2,3),(1,3),(1,2)]
    prev=[get(xthumb,j,k) for j,k in jjkk]
    midz=sum(coord(xthumb,j,k)[2] for j,k in jjkk)/8
    midy=cy
    thumb=f"Thumb.{side}";tip=f"ThumbTip.{side}"
    for ring in range(1,6):
        t=ring/5;cur=[]
        for j,k in jjkk:
            x,y,z=coord(xthumb,j,k)
            a=math.atan2((z-midz)/.10,(y-midy)/.10)
            rr=.11*(1-.50*t)
            cur.append(len(vx))
            vx.append((x-sign*.245*t,midy+rr*math.cos(a)-.10*t,midz+rr*math.sin(a)-.19*t))
            weights.append({thumb:1} if t<.6 else {tip:1})
        for j in range(8):faces.append((prev[j],prev[(j+1)%8],cur[(j+1)%8],cur[j]))
        prev=cur
    cap=len(vx)
    vx.append((cx-sign*.5*width-sign*.245,midy-.10,midz-.19))
    weights.append({tip:1})
    for j in range(8):faces.append((prev[j],prev[(j+1)%8],cap))
    obj=mesh_obj(f"V18_Hand.{side}",vx,faces,FUR,weights)
    # Correct normals in a consistent pass; no topology changes occur here.
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
    bm.to_mesh(obj.data);bm.free()
    subdiv(obj,2)
    # Oatmeal circular palm pad and fingertip pads, attached to their own bones.
    ellipsoid(f"V18_PalmPad.{side}",(cx,cy-.191,1.55),(.148,.027,.151),PADS,f"Hand.{side}",SEWN)
    for n,i0 in enumerate(root_i,1):
        mx=cx+width*((i0+1)/nx-.5)
        y=cy-.175
        ellipsoid(f"V18_FingerPad{n}.{side}",(mx,y,1.075),(.049,.024,.056),PADS,
                  f"FingerTip{n}.{side}",SEWN,segments=20,rings=12)
    ellipsoid(f"V18_ThumbPad.{side}",(cx-sign*(width*.5+.245),cy-.12,midz-.15),
              (.037,.065,.064),PADS,f"ThumbTip.{side}",SEWN,segments=20,rings=12)
    return obj


for side,sign in (("L",-1),("R",1)):
    hand_geometry(side,sign)


# Plush long legs and paw-shaped feet. Toe divisions are sculpted clefts;
# no detached round toe beads or shoe-like sole discs.
for side,sign in (("L",-1),("R",1)):
    leg=tube(f"V18_Leg.{side}",
             [(sign*.34,.02,1.86),(sign*.36,.01,1.54),
              (sign*.37,-.01,1.08),(sign*.38,-.02,.67),(sign*.38,-.04,.35)],
             [.20,.225,.23,.21,.195],[.22,.235,.22,.205,.19],FUR,
             [f"Thigh.{side}",f"Shin.{side}"],ang=28,subdivisions=6,
             transitions=[.49],blend=.17)
    subdiv(leg,1)
    levels=[(.018,.20,.30,-.26),(.07,.26,.40,-.25),(.14,.31,.46,-.24),
            (.24,.32,.44,-.22),(.34,.275,.33,-.15),(.43,.20,.20,-.08)]
    verts=[];faces=[];weight=[];N2=32
    for k,(z,rx,ry,cy) in enumerate(levels):
        for j in range(N2):
            a=2*math.pi*j/N2
            x=sign*.38+rx*math.cos(a)
            y=cy+ry*math.sin(a)
            if y<cy and z<.28:
                # Three shallow forward lobes are part of one foot mesh.
                q=(x-sign*.38)/rx
                toe_wave=math.cos(3*math.pi*q)
                front_factor=max(0,min(1,(-math.sin(a)-.15)/.85))
                y-=.137*toe_wave*front_factor
                z=max(.012,z+.052*toe_wave*front_factor*min(1,(.34-z)/.18))
            verts.append((x,y,z));weight.append({f"Foot.{side}":1})
            if k:
                last=(k-1)*N2+j;lastn=(k-1)*N2+(j+1)%N2
                curr=k*N2+j;currn=k*N2+(j+1)%N2
                faces.append((last,lastn,currn,curr))
    faces.append(tuple(reversed(range(N2))))
    faces.append(tuple((len(levels)-1)*N2+j for j in range(N2)))
    foot=mesh_obj(f"V18_Foot.{side}",verts,faces,FUR,weight)
    subdiv(foot,1)
    # Toe clefts on the main foot, not extra beads.
    clefts=[]
    for offset in (-.115,.115):
        x=sign*.38+offset
        clefts.append([(x,-.57,.074),(x,-.645,.13),(x,-.655,.22)])
    lines(f"V18_ToeClefts.{side}",clefts,SOCKET,f"Foot.{side}",.010)
    # Knee stitches on the leg surface, spaced vertically along the fold.
    knee=[]
    for i in range(7):
        a=2*math.pi*i/7
        knee.append([(sign*.37+.23*math.cos(a),-.01+.23*math.sin(a),.97-.034),
                     (sign*.37+.23*math.cos(a),-.01+.23*math.sin(a),.97+.034)])
    lines(f"V18_Knee_Tacks.{side}",knee,THREAD,f"Shin.{side}",.012)


print("V18_LIMBS_READY")


# Teeth share a single compact mesh, but have genuinely separate rounded roots
# and unequal curved tips. Both rows are retracted into the throat when shut.
tooth_v=[];tooth_open=[];tooth_f=[];tooth_weights=[]
tooth_angles=12
def tooth_row(top):
    row_x=[-.57,-.445,-.315,-.17,0,.17,.315,.445,.57]
    if not top:
        row_x=[x+.023 for x in row_x]
    lengths=([.155,.255,.335,.235,.250,.220,.335,.255,.155] if top
             else [.16,.19,.26,.33,.26,.315,.265,.20,.16])
    for idx,(x,ln) in enumerate(zip(row_x,lengths)):
        rx=.066 if idx not in (2,6) else .085
        if idx in (0,8):rx=.054
        ratio=min(.99,x/.678)
        phi=math.acos(ratio)
        if not top:phi=-phi
        rim=front_coord(0,phi,1)
        direction=-1 if top else 1
        base_y=rim[1]+.023
        start=len(tooth_v)
        for ring,(t,fac) in enumerate(((0, .80),(.12,1),(.40,.82),(.69,.48),(.90,.18),(1,.023))):
            px=x+direction*(.025 if x>0 else -.025)*t*t
            py=base_y-.052*t+math.sin(t*math.pi)*.011
            pz=rim[2]+direction*ln*t
            for j in range(tooth_angles):
                a=2*math.pi*j/tooth_angles
                xyz=(px+rx*fac*math.cos(a),py+.051*fac*math.sin(a),pz)
                tooth_open.append(xyz)
                # Closed basis hides the teeth behind the small mouth slit.
                tooth_v.append((xyz[0],-.15+.02*t,3.82+direction*.012*t))
                tooth_weights.append({"Head":1})
                if ring:
                    u=start+(ring-1)*tooth_angles+j
                    un=start+(ring-1)*tooth_angles+(j+1)%tooth_angles
                    v=start+ring*tooth_angles+j
                    vn=start+ring*tooth_angles+(j+1)%tooth_angles
                    tooth_f.append((u,un,vn,v))
        tip=len(tooth_v)
        tooth_v.append((x,-.13,3.82+direction*.012))
        tooth_open.append((px,py,pz+direction*.004))
        tooth_weights.append({"Head":1})
        for j in range(tooth_angles):
            tooth_f.append((start+5*tooth_angles+j,
                           start+5*tooth_angles+(j+1)%tooth_angles,tip))
        tooth_f.append(tuple(reversed(range(start,start+tooth_angles))))

tooth_row(True)
tooth_row(False)
teeth=mesh_obj("V18_IrregularUpperAndLowerFangs",tooth_v,tooth_f,IVORY,tooth_weights,FACE)
teeth.shape_key_add(name="Basis",from_mix=False)
tooth_key=teeth.shape_key_add(name="MouthOpen",from_mix=False)
for i,v in enumerate(tooth_open):tooth_key.data[i].co=v
drive_mouth(tooth_key)
subdiv(teeth,1)

# No pupils, cartoon eyelids or glossy eyeballs. Light is very local to the
# small warm cream disks and reads as embedded in the deep indigo textile.
for side,sgn in (("L",-1),("R",1)):
    cx=sgn*.295
    ellipsoid(f"V18_InsetEyeSocket.{side}",(cx,-.522,4.365),
              (.122,.031,.128),SOCKET,"Head",FACE)
    ellipsoid(f"V18_SoftWhiteEye.{side}",(cx,-.547,4.366),
              (.103,.033,.107),EYE,"Head",FACE)

# An actual curved inlay, conforming at each vertex to the varying torso
# radius: no large flat oval or hovering decal.
def torso_profile(z):
    for low,high in zip(body_profiles,body_profiles[1:]):
        if z<=high[0]:
            t=max(0,min(1,(z-low[0])/(high[0]-low[0])))
            return (low[1]*(1-t)+high[1]*t,low[2]*(1-t)+high[2]*t)
    return body_profiles[-1][1:]

def front_on_torso(x,z,offset=.012):
    rx,ry=torso_profile(z)
    return -ry*math.sqrt(max(.001,1-(x/rx)**2))-offset

patch_v=[];patch_f=[];patch_w=[];patch_rings=8;patch_segs=48
def patch_pt(r,a):
    jitter=1+.032*math.sin(3*a+.40)+.016*math.sin(7*a)
    x=.413*r*math.cos(a)*jitter
    z=2.49+.55*r*math.sin(a)*jitter
    return (x,front_on_torso(x,z,.017),z)
for k in range(patch_rings+1):
    r=k/patch_rings
    for j in range(patch_segs):
        a=2*math.pi*j/patch_segs
        patch_v.append(patch_pt(r,a))
        z=patch_v[-1][2]
        if z>2.36:patch_w.append({"Spine":1})
        elif z<2.08:patch_w.append({"Pelvis":1})
        else:
            t=(z-2.08)/.28
            patch_w.append({"Spine":t,"Pelvis":1-t})
        if k:
            p=(k-1)*patch_segs+j;pn=(k-1)*patch_segs+(j+1)%patch_segs
            c=k*patch_segs+j;cn=k*patch_segs+(j+1)%patch_segs
            patch_f.append((p,pn,cn,c))
patch=mesh_obj("V18_OrganicSewnBellyInlay",patch_v,patch_f,PATCH,patch_w,SEWN)
subdiv(patch,1)
belly_stitches=[]
for j in range(30):
    a=2*math.pi*j/30
    o=patch_pt(1.075,a);i=patch_pt(.91,a)
    belly_stitches.append([(o[0],o[1]-.006,o[2]),
                           (i[0],i[1]-.024,i[2])])
lines("V18_BellyBlanketStitches",belly_stitches,THREAD,"Spine",.014)

# Quiet stitched cheeks and a subtle back zipper seam; every curve skins to
# the same rig, including what would otherwise float in animation.
for sgn,side in ((-1,"L"),(1,"R")):
    cheek=[]
    for i in range(4):
        x=sgn*(.635+i*.027)
        z=3.835+(i-1.5)*.021
        cheek.append([(x-.027,-.385,z-.025),(x+.027,-.385,z+.025)])
    lines(f"V18_CheekStitches.{side}",cheek,THREAD,"Head",.011)

back_stitch=[]
back_path=[]
for i in range(24):
    z=1.91+i*(1.13/23)
    rx,ry=torso_profile(z)
    back_path.append((0,ry+.008,z))
    if i%2==0:
        back_stitch.append([(-.058,ry+.012,z-.015),(.058,ry+.012,z+.015)])
lines("V18_HandsewnSpine",[back_path],SOCKET,"Spine",.010)
lines("V18_SpineTanTacks",back_stitch,THREAD,"Spine",.011)
ellipsoid("V18_StitchedTail",(0,.519,2.04),(.235,.225,.234),FUR,"Pelvis",SEWN)
lines("V18_TailRootSeam",[[(.17,.595,2.09),(.19,.59,2.03),(.16,.59,1.97)]],
      THREAD,"Pelvis",.008)

# Quiet tan under-paw soles, visible from below when crawling or lifted.
for side,sign in (("L",-1),("R",1)):
    ellipsoid(f"V18_PlantarPad.{side}",(sign*.38,-.255,.035),
              (.235,.326,.023),PADS,f"Foot.{side}",SEWN)
    for n,dx in enumerate((-.123,0,.123),1):
        # The claws are genuinely tapering curved volumes, not floating spheres.
        xx=sign*.99+dx
        claw=tube(f"V18_Claw{n}.{side}",
                  [(xx,-.10,1.043),(xx,-.16,1.013),(xx,-.191,.974)],
                  [.024,.018,.001],[.027,.018,.001],IVORY,
                  [f"FingerTip{n}.{side}",f"FingerTip{n}.{side}"],
                  FACE,ang=12,subdivisions=4)
        subdiv(claw,1)

print("V18_DETAILS_READY",len(bpy.data.objects),len(teeth.data.vertices))


# Studio-only diagnostic scene: cameras, lights, neutral world. Studio assets
# live in a separate collection so a Roblox importer can exclude them.
ground_mat=mat("MAT_Studio_WarmGrey",(206,201,208),roughness=.95)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.013))
ground=bpy.context.object
ground.name="Studio_Ground_ExcludedFromExport"
for old in list(ground.users_collection):old.objects.unlink(ground)
RENDER.objects.link(ground)
ground.data.materials.append(ground_mat)

world=bpy.data.worlds.new("V18_Studio_WarmFill")
scene.world=world
world.use_nodes=True
bg=world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value=(.70,.69,.73,1)
bg.inputs["Strength"].default_value=.82

def aim(ob,point):
    direction=Vector(point)-ob.location
    ob.rotation_euler=direction.to_track_quat('-Z','Y').to_euler()

def area_light(name,position,power,size,color):
    ld=bpy.data.lights.new(name,'AREA')
    ld.energy=power
    ld.shape='DISK';ld.size=size
    ld.color=color
    lo=bpy.data.objects.new(name,ld)
    RENDER.objects.link(lo)
    lo.location=position
    aim(lo,(0,0,2.55))

area_light("V18_Key_Softbox",(-4,-5,7.2),920,5.0,(1.0,.90,.80))
area_light("V18_Fill_Softbox",(4,-3,4.7),690,4.5,(.76,.82,1.0))
area_light("V18_Back_Softbox",(.8,4.0,6.1),1050,3.0,(.77,.82,1.0))

cameras={}
for name,position,scale in (("front",(0,-11,3.0),6.55),
                            ("side",(12,0,3.0),6.55),
                            ("back",(0,11,3.0),6.55),
                            ("hand",(3,-6,1.49),1.5)):
    camera_dat=bpy.data.cameras.new("CAM_v18_"+name)
    camera_dat.type='ORTHO'
    camera_dat.ortho_scale=scale
    camera=bpy.data.objects.new("CAM_v18_"+name,camera_dat)
    RENDER.objects.link(camera)
    camera.location=position
    aim(camera,(0,0,2.94) if name!="hand" else (.73,-.05,1.31))
    cameras[name]=camera

scene.render.engine='CYCLES'
scene.cycles.samples=24
scene.render.resolution_x=760
scene.render.resolution_y=760
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.film_transparent=False
scene.view_settings.view_transform='AgX'
scene.render.image_settings.color_mode='RGBA'
scene.camera=cameras['front']
scene.render.filepath=str(OUT/'v18_front_open.png')
scene.render.use_file_extension=True
scene.render.image_settings.color_depth='8'

# Store reference traceability and honest scope in the file itself.
scene['AssetRevision']='v18 – reference-guided topology and detail pass'
scene['ReferenceSource']='Four user-provided movement concept videos, November 2026'
scene['ReferenceDimensions']='Crown-floor 4.78m; head width 1.58m; hand length ~0.86m'
scene['AnimationStatus']='Model/rig test pass only; legacy v17 actions are NOT retargeted'
scene['SoftwareBuiltWith']='Blender 5.3.0 (official Linux release)'
scene['CharacterRig']=rig.name
scene['RobloxExport']='Exclude collection V18_04; retopo/LOD and animation export still required'

rig['MouthOpen']=.84
bpy.context.view_layer.objects.active=rig
bpy.ops.object.select_all(action='DESELECT')
rig.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Plush-v18-Reference-Match.blend'),compress=True)

# Baseline orthographic comparisons and a true closed-mouth test render.
for name,camera in cameras.items():
    if name=='hand':continue
    scene.camera=camera
    scene.render.filepath=str(OUT/f'v18_{name}_open.png')
    bpy.ops.render.render(write_still=True)
rig['MouthOpen']=.04
scene.camera=cameras['front']
scene.render.filepath=str(OUT/'v18_front_closed.png')
bpy.ops.render.render(write_still=True)
rig['MouthOpen']=.84
print("V18_SAVED",str(OUT/'Plush-v18-Reference-Match.blend'))
