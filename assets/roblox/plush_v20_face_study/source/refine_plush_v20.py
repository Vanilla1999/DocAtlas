"""v20: stuffed facial forms, padded lips and a structured cloth-lined mouth.

Blender 5.3.0. Reads the saved v18 master, never overwrites it.
The facial shell is a hand-designed quad loft, not a boolean-cut sphere.
Run: blender -b --python refine_plush_v20.py [-- --quick | --no-render]
"""

import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'plush_v20'
OUT.mkdir(exist_ok=True)
BASE=ROOT/'plush_v18'/'Plush-v18-Reference-Match.blend'
if not BASE.exists(): BASE=ROOT/'Plush-v18-Reference-Match.blend'
bpy.ops.wm.open_mainfile(filepath=str(BASE))
scene=bpy.context.scene
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
rig.name='ARM_Plush_v20'
if rig.animation_data:rig.animation_data.action=None
for p in rig.pose.bones:
    p.rotation_mode='XYZ';p.location=(0,0,0);p.rotation_euler=(0,0,0);p.scale=(1,1,1)

# Keep the v18 body and editable hand topology, replace the entire facial asset.
remove=('V18_Head','V18_Ear','V18_Cheek','V18_InsetEye','V18_SoftWhiteEye',
        'V18_Irregular','V18_NeckBridge')
for o in list(bpy.data.objects):
    if o!=rig and (o.name.startswith(remove) or o.type in {'CAMERA','LIGHT'}
                   or o.name.startswith('Studio_Ground')):
        bpy.data.objects.remove(o,do_unlink=True)
for o in bpy.data.objects:
    if o.name.startswith('V18_'):o.name=o.name.replace('V18_','V20_',1)
for c in bpy.data.collections:
    if c.name.startswith('V18_'):c.name=c.name.replace('V18_','V20_',1)

# Bury the old sleeve end caps inside the chest rather than leaving the
# pointed shoulders visible as separate conical masses beside the neck.
for side,sign in (('L',-1),('R',1)):
    sleeve=bpy.data.objects.get('V20_Arm.'+side)
    if sleeve:
        for ring in range(7):
            inds=list(range(ring*24,(ring+1)*24))
            center=sum((sleeve.data.vertices[i].co for i in inds),Vector())/24
            t=ring/6
            shift=Vector((sign*(-.15*(1-t)-.02*t),0,-.07*(1-t)-.02*t))
            scale=.65+.35*t
            for i in inds:sleeve.data.vertices[i].co=center+shift+(sleeve.data.vertices[i].co-center)*scale
        sleeve.data.update()

def collection(name):
    c=bpy.data.collections.new(name);scene.collection.children.link(c);return c

HEAD=collection('V20_05 • redesigned facial topology')
DETAIL=collection('V20_06 • inset eyes, felt and stitching')
FLEECE=collection('V20_07 • procedural boucle / render master only')
STUDIO=collection('V20_08 • review studio / exclude from export')

def rgb(rgb8):
    def linear(c):
        f=c/255;return f/12.92 if f<=.04045 else ((f+.055)/1.055)**2.4
    return (*[linear(x) for x in rgb8],1)

def material(name,color,rough=.82,sheen=.0,emission=.0):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color=rgb(color)
    m.use_nodes=True
    n=m.node_tree.nodes;n.clear();l=m.node_tree.links
    p=n.new('ShaderNodeBsdfPrincipled');out=n.new('ShaderNodeOutputMaterial')
    l.new(p.outputs['BSDF'],out.inputs['Surface'])
    p.inputs['Base Color'].default_value=rgb(color)
    p.inputs['Roughness'].default_value=rough
    p.inputs['Specular IOR Level'].default_value=.22
    p.inputs['Sheen Weight'].default_value=sheen
    if emission:
        p.inputs['Emission Color'].default_value=rgb(color)
        p.inputs['Emission Strength'].default_value=emission
    return m,p

FUR=bpy.data.materials['MAT_Fabric_DeepInkBoucle']
FUR.name='MAT_Fabric_NavyVioletBoucle_v20'
FUR,p=material(FUR.name,(25,23,46),.84,.34)
p.inputs['Specular IOR Level'].default_value=.24
p.inputs['Sheen Tint'].default_value=rgb((71,61,101))
n=FUR.node_tree.nodes;l=FUR.node_tree.links
tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=120
tex.inputs['Detail'].default_value=3.2
coord=n.new('ShaderNodeTexCoord');l.new(coord.outputs['Object'],tex.inputs['Vector'])
ramp=n.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].position=.19;ramp.color_ramp.elements[0].color=rgb((21,19,38))
ramp.color_ramp.elements[1].position=.83;ramp.color_ramp.elements[1].color=rgb((38,34,63))
l.new(tex.outputs['Fac'],ramp.inputs['Fac']);l.new(ramp.outputs['Color'],p.inputs['Base Color'])
bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.10
bump.inputs['Distance'].default_value=.0025
l.new(tex.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],p.inputs['Normal'])

INNER,ip=material('MAT_Mouth_VelvetDepth_v20',(33,22,41),.73,.21)
ip.inputs['Specular IOR Level'].default_value=.22
ip.inputs['Sheen Tint'].default_value=rgb((55,37,59))
inn=INNER.node_tree.nodes;inl=INNER.node_tree.links
inoise=inn.new('ShaderNodeTexNoise');inoise.inputs['Scale'].default_value=75
inoise.inputs['Detail'].default_value=2
ibump=inn.new('ShaderNodeBump');ibump.inputs['Strength'].default_value=.18;ibump.inputs['Distance'].default_value=.005
inl.new(inoise.outputs['Fac'],ibump.inputs['Height']);inl.new(ibump.outputs['Normal'],ip.inputs['Normal'])
depth_attr=inn.new('ShaderNodeAttribute');depth_attr.attribute_name='MouthDepth'
depth_ramp=inn.new('ShaderNodeValToRGB')
depth_ramp.color_ramp.elements[0].color=rgb((44,29,50))
depth_ramp.color_ramp.elements[1].color=rgb((8,6,13))
depth_ramp.color_ramp.elements.new(.65).color=rgb((36,23,44))
depth_ramp.color_ramp.elements.new(.87).color=rgb((21,13,29))
inl.new(depth_attr.outputs['Fac'],depth_ramp.inputs['Fac'])
inl.new(depth_ramp.outputs['Color'],ip.inputs['Base Color'])
TONGUE,tgp=material('MAT_Mouth_ClothTongue_v20',(29,17,32),.80,.16)
tgp.inputs['Specular IOR Level'].default_value=.18
tgp.inputs['Sheen Tint'].default_value=rgb((51,31,48))
tg_n=TONGUE.node_tree.nodes;tg_l=TONGUE.node_tree.links
tg_noise=tg_n.new('ShaderNodeTexNoise');tg_noise.inputs['Scale'].default_value=95
tg_bump=tg_n.new('ShaderNodeBump');tg_bump.inputs['Strength'].default_value=.16;tg_bump.inputs['Distance'].default_value=.004
tg_l.new(tg_noise.outputs['Fac'],tg_bump.inputs['Height']);tg_l.new(tg_bump.outputs[0],tgp.inputs['Normal'])
FELT,fp=material('MAT_Ear_InnerWornFelt_v20',(28,21,25),.96,.05)
fp.inputs['Specular IOR Level'].default_value=.10
fp.inputs['Sheen Tint'].default_value=rgb((38,27,30))
fn=FELT.node_tree.nodes;fl=FELT.node_tree.links
feltnoise=fn.new('ShaderNodeTexNoise');feltnoise.inputs['Scale'].default_value=185
feltnoise.inputs['Detail'].default_value=2.5
feltbump=fn.new('ShaderNodeBump');feltbump.inputs['Strength'].default_value=.18
feltbump.inputs['Distance'].default_value=.004
fl.new(feltnoise.outputs['Fac'],feltbump.inputs['Height'])
fl.new(feltbump.outputs['Normal'],fp.inputs['Normal'])
THREAD=bpy.data.materials['MAT_Thread_WarmTan']
THREAD,_=material(THREAD.name,(181,137,88),.84,.18)
EYE,_=material('MAT_Eyes_WarmInset_v20',(255,202,113),.35,0,7.0)
SOCKET,_=material('MAT_Eyes_RecessedShadow_v20',(23,20,39),.88,.22)
TEETH,tp=material('MAT_Teeth_OrganicIvory_v20',(220,209,177),.44)
tn=TEETH.node_tree.nodes;tl=TEETH.node_tree.links
attr=tn.new('ShaderNodeAttribute');attr.attribute_name='ToothTipFade'
tr=tn.new('ShaderNodeValToRGB')
tr.color_ramp.elements[0].color=rgb((111,88,60));tr.color_ramp.elements[0].position=.0
tr.color_ramp.elements[1].color=rgb((229,215,183));tr.color_ramp.elements[1].position=.75
tl.new(attr.outputs['Fac'],tr.inputs['Fac'])
streak=tn.new('ShaderNodeAttribute');streak.attribute_name='EnamelStreak'
enamel_mix=tn.new('ShaderNodeMixRGB');enamel_mix.blend_type='MULTIPLY';enamel_mix.inputs[0].default_value=.16
tl.new(tr.outputs['Color'],enamel_mix.inputs[1]);tl.new(streak.outputs['Color'],enamel_mix.inputs[2])
tl.new(enamel_mix.outputs['Color'],tp.inputs['Base Color'])
enamel_bump=tn.new('ShaderNodeBump');enamel_bump.inputs['Strength'].default_value=.15;enamel_bump.inputs['Distance'].default_value=.0013
tl.new(streak.outputs['Fac'],enamel_bump.inputs['Height']);tl.new(enamel_bump.outputs[0],tp.inputs['Normal'])
enamel_coords=tn.new('ShaderNodeAttribute');enamel_coords.attribute_name='EnamelCoord'
enamel_scale=tn.new('ShaderNodeVectorMath');enamel_scale.operation='MULTIPLY'
enamel_scale.inputs[1].default_value=(8,8,.6)
tl.new(enamel_coords.outputs['Vector'],enamel_scale.inputs[0])
enamel_noise=tn.new('ShaderNodeTexNoise');enamel_noise.inputs['Scale'].default_value=1
enamel_noise.inputs['Detail'].default_value=2.5
tl.new(enamel_scale.outputs['Vector'],enamel_noise.inputs['Vector'])
grain=tn.new('ShaderNodeValToRGB')
grain.color_ramp.elements[0].position=.25;grain.color_ramp.elements[0].color=(.57,.47,.34,1)
grain.color_ramp.elements[1].position=.77;grain.color_ramp.elements[1].color=(1,1,.97,1)
tl.new(enamel_noise.outputs['Fac'],grain.inputs['Fac'])
ivory=tn.new('ShaderNodeMixRGB');ivory.blend_type='MULTIPLY';ivory.inputs[0].default_value=.30
tl.new(enamel_mix.outputs['Color'],ivory.inputs[1]);tl.new(grain.outputs['Color'],ivory.inputs[2])
tl.new(ivory.outputs[0],tp.inputs['Base Color'])
tl.new(enamel_noise.outputs['Fac'],enamel_bump.inputs['Height'])

def mesh(name,verts,faces,mat,weights=None,coll=HEAD,role=None):
    d=bpy.data.meshes.new(name+'_mesh');d.from_pydata(verts,[],faces);d.update()
    o=bpy.data.objects.new(name,d);coll.objects.link(o);o.parent=rig
    d.materials.append(mat)
    weights=weights or [{'Head':1} for _ in verts]
    vg={bn:o.vertex_groups.new(name=bn) for bn in sorted({bn for w in weights for bn in w})}
    for i,w in enumerate(weights):
        total=sum(w.values())
        for bn,v in w.items():
            if v>0:vg[bn].add([i],v/total,'REPLACE')
    arm=o.modifiers.new('Rig deformation','ARMATURE');arm.object=rig
    arm.use_deform_preserve_volume=True
    for f in d.polygons:f.use_smooth=True
    if role:o['qa_role']=role
    return o

def smooth(o,levels=1):
    m=o.modifiers.new('Quad surface smoothing','SUBSURF');m.levels=levels;m.render_levels=levels

def morph(o,opened):
    o.shape_key_add(name='Basis',from_mix=False)
    k=o.shape_key_add(name='MouthOpen',from_mix=False)
    for p,co in zip(k.data,opened):p.co=co
    fc=k.driver_add('value');d=fc.driver;d.type='SCRIPTED'
    var=d.variables.new();var.name='aperture';var.type='SINGLE_PROP'
    var.targets[0].id=rig;var.targets[0].data_path='["MouthOpen"]'
    d.expression='min(1,max(0,aperture))'
    return k

def normalize_normals(o):
    bm=bmesh.new();bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()

def coverage(o,values=None):
    a=o.data.attributes.new('FleeceCoverage','FLOAT','POINT')
    if values is None:values=[1]*len(o.data.vertices)
    for item,v in zip(a.data,values):item.value=v

def quad_rings(rings,close_start=True,close_end=True):
    n=len(rings[0]);verts=[v for r in rings for v in r];faces=[]
    for k in range(1,len(rings)):
        for j in range(n):faces.append(((k-1)*n+j,(k-1)*n+(j+1)%n,k*n+(j+1)%n,k*n+j))
    if close_start:
        pole=len(verts);verts.append(tuple(sum(p[a] for p in rings[0])/n for a in range(3)))
        for j in range(n):faces.append((pole,(j+1)%n,j))
    if close_end:
        pole=len(verts);verts.append(tuple(sum(p[a] for p in rings[-1])/n for a in range(3)))
        start=(len(rings)-1)*n
        for j in range(n):faces.append((start+j,start+(j+1)%n,pole))
    return verts,faces

# Symmetric mouth rim: independent upper arch and deep U-shaped lower jaw.
HX=.80;HC=4.06;TOP=.61;HY=.60;BACKHY=.56;MW=.655;N=128
EYE_Z=4.315
def rim(phi,o):
    c=math.cos(phi);s=math.sin(phi)
    x=MW*c*(1-.035*o*max(0,-s))
    closed=3.83+.08*c*c+.0055*s
    opened=3.94+(.14*s**.66 if s>=0 else -.84*(-s)**.85)
    z=closed*(1-o)+opened*o
    y=-.69+.35*c*c+.055*o*max(0,-s)
    return Vector((x,y,z))

def outer(phi,o):
    c=math.cos(phi);s=math.sin(phi)
    return Vector((HX*c*(1-.045*max(0,-s)),0,
                   HC+(TOP*s if s>=0 else (.68+.44*o)*s)))

def outward(phi,o):
    d=rim(phi+.0005,o)-rim(phi-.0005,o)
    return Vector((d.z,0,-d.x)).normalized()

def sphere_front(x,z,o):
    height=TOP if z>=HC else .68+.44*o
    base=-HY*math.sqrt(max(0,1-(x/HX)**2-((z-HC)/height)**2))
    # Broad sewn/stuffed secondary masses, not isolated cheek spheres.
    orbital=sum(math.exp(-((x-sx)/.205)**2-((z-(EYE_Z+.015))/.22)**2) for sx in (-.285,.285))
    cheek=sum(math.exp(-((x-sx)/.18)**2-((z-3.99)/.26)**2) for sx in (-.57,.57))
    bridge=math.exp(-(x/.021)**2-((z-4.39)/.30)**4)
    return base-.072*orbital-.045*cheek+.012*bridge

FR=18;BR=18;IR=22;LR=4
closed=[];opened=[];faces=[];mats=[];fleecemask=[]
def front_point(phi,k,o):
    p=rim(phi,o);n=outward(phi,o)
    lower=max(0,-math.sin(phi))
    width=(.040+.006*lower)*(1-o)+(.083+.029*lower+.014*abs(math.cos(phi))**4)*o
    if k==0:return p
    if k<=LR:
        t=k/LR
        return p+n*(width*t)+Vector((0,-(.038+.020*o)*math.sin(math.pi*t)-.004*t,0))
    u=(k-LR)/(FR-LR)
    r=p+n*width;q=outer(phi,o)
    x=r.x*(1-u)+q.x*u;z=r.z*(1-u)+q.z*u
    z-=.014*o*max(0,-math.sin(phi))**4*math.sin(math.pi*u)
    natural=sphere_front(x,z,o)
    startnatural=sphere_front(r.x,r.z,o)
    y=natural+(p.y-.004-startnatural)*(1-u)**2
    return Vector((x,y,z))

for k in range(FR+1):
    for j in range(N):
        phi=2*math.pi*j/N
        closed.append(tuple(front_point(phi,k,0)));opened.append(tuple(front_point(phi,k,1)))
        # Eye clearance is evaluated against the live deformed sockets in GN.
        # A fixed vertex mask would leave a long bald patch when the face closes.
        fleecemask.append(0 if k<=1 else (.40 if k==2 else (.80 if k==3 else 1)))
        if k:
            faces.append(((k-1)*N+j,k*N+j,k*N+(j+1)%N,(k-1)*N+(j+1)%N));mats.append(0)
outer_start=FR*N
for k in range(1,BR+1):
    start=len(closed);a=math.pi*.5*k/(BR+1)
    for j in range(N):
        phi=2*math.pi*j/N
        for o,arr in ((0,closed),(1,opened)):
            p=outer(phi,0);delta=outer(phi,o)-p
            # The lower FRONT jaw drops, not the whole back of the skull.
            fade=(1-math.sin(a))**2.5
            arr.append(((p.x+delta.x*fade)*math.cos(a),BACKHY*math.sin(a),
                        HC+(p.z-HC)*math.cos(a)+delta.z*math.cos(a)*fade))
        fleecemask.append(1)
    for j in range(N):
        prev=outer_start if k==1 else start-N
        faces.append((prev+j,start+j,start+(j+1)%N,prev+(j+1)%N));mats.append(0)
pole=len(closed);closed.append((0,BACKHY,HC));opened.append((0,BACKHY,HC));fleecemask.append(1)
for j in range(N):faces.append((pole-N+j,pole,pole-N+(j+1)%N));mats.append(0)

# Interior is a genuine manifold continuation of the aperture, with a throat
# cap behind every section. No nonplanar fan turns back through the lips.
interior_start=len(closed)
for k in range(1,IR+1):
    start=len(closed);t=k/IR
    for j in range(N):
        phi=2*math.pi*j/N
        for o,arr in ((0,closed),(1,opened)):
            p=rim(phi,o);cz=3.84-.16*o
            shrink_x=1-.91*t**(8 if o==0 else 3)
            shrink_z=1-.91*t**2
            # The lips close but the chamber does not collapse to a sheet:
            # upper/lower teeth still have an actual dark pocket behind them.
            s=math.sin(phi)
            chamber=(.33 if s>=0 else .39)*s*math.sin(math.pi*t)**.85*(1-o)
            depth=math.sin(math.pi*.5*t)
            x=p.x*shrink_x;y=p.y*(1-depth)+.27*depth
            z=cz+(p.z-cz)*shrink_z+chamber
            # Three broad longitudinal folds on each inner cheek. They fade
            # before the lip and the throat; no uniform pumpkin-like ribbing.
            folds=sum(amp*math.exp(-((t-at)/width)**2) for at,width,amp in
                      ((.23,.075,.060),(.46,.080,.090),(.67,.095,.065)))
            side=abs(math.cos(phi))**3
            x-=math.copysign(o*folds*side*math.sin(math.pi*t),x) if abs(x)>1e-9 else 0
            y-=o*folds*.85*side*math.sin(math.pi*t)
            # Soft palate arch and a cloth floor under the separate tongue.
            z-=o*.028*max(0,s)**5*math.exp(-((t-.43)/.105)**2)
            z+=o*.016*max(0,-s)**4*math.sin(math.pi*t)**2
            arr.append((x,y,z))
        fleecemask.append(0)
    for j in range(N):
        prev=0 if k==1 else start-N
        faces.append((prev+j,prev+(j+1)%N,start+(j+1)%N,start+j));mats.append(1)
pole=len(closed);closed.append((0,.30,3.84));opened.append((0,.30,3.68));fleecemask.append(0)
for j in range(N):faces.append((pole-N+(j+1)%N,pole,pole-N+j));mats.append(1)

head=mesh('V20_HeadShell',closed,faces,FUR,role='head')
head.data.materials.append(INNER)
for p,m in zip(head.data.polygons,mats):p.material_index=m
normalize_normals(head)
morph(head,opened)
smooth(head,1)
coverage(head,fleecemask)
open_fleece=list(fleecemask);pile_lengths=[1.0]*len(closed)
for i in range((FR+1)*N):
    k=i//N
    if k<=LR:
        open_fleece[i]=(.30,.88,1.0,1.0,1.0)[k]
        pile_lengths[i]=(.40,.60,.82,.94,1.0)[k]
for name,values in (('FleeceOpenCoverage',open_fleece),('FleeceLength',pile_lengths)):
    att=head.data.attributes.new(name,'FLOAT','POINT')
    for v,value in zip(att.data,values):v.value=value
att=head.data.attributes.new('MouthDepth','FLOAT','POINT')
for i,v in enumerate(att.data):
    v.value=0 if i<interior_start else min(1,((i-interior_start)//N+1)/IR)
aperture=head.vertex_groups.new(name='QA_MouthAperture');aperture.add(list(range(N)),1,'REPLACE')
head['design']='Compressed stuffed upper face, orbital pillows, panel seam, padded lip, fixed round back skull, folded cloth cavity'
head['qa_budget_role']='High-detail master; fleece instances are not export LOD'

print('V20_HEAD_READY',len(closed),len(faces))


def make_teeth(upper=True):
    # Individually art-directed crowns; left/right are deliberately not copies.
    # x, length, crown radius, depth ratio, root-depth offset
    descriptors=(
        [(-.594,.112,.026,.65,.002),(-.514,.181,.035,.68,.008),
         (-.400,.389,.070,.82,-.006),(-.266,.226,.051,.65,.010),
         (-.131,.160,.047,.61,-.003),(-.012,.198,.044,.62,.010),
         (.109,.137,.039,.63,.002),(.239,.211,.051,.66,.013),
         (.379,.361,.068,.79,-.002),(.506,.178,.040,.65,.009),
         (.589,.119,.027,.66,.001)]
        if upper else
        [(-.596,.127,.027,.66,.008),(-.517,.184,.037,.70,.002),
         (-.419,.267,.051,.76,.009),(-.307,.218,.046,.68,-.004),
         (-.193,.146,.037,.64,.005),(-.089,.181,.040,.65,.011),
         (.014,.116,.029,.61,.002),(.109,.152,.036,.64,-.004),
         (.214,.202,.043,.68,.010),(.313,.164,.038,.65,.002),
         (.416,.248,.050,.77,.008),(.515,.176,.036,.69,.001),
         (.591,.124,.027,.65,.006)])
    vv=[];oo=[];ff=[];fade=[];streaks=[];enamel_uv=[];tips=[];S=20
    samples=[(0,.78),(.10,.94),(.25,1.0),(.43,.83),(.62,.53),(.80,.26),(.93,.074)]
    for tooth_index,(x,length,rx,depth_ratio,root_offset) in enumerate(descriptors):
        phi=math.acos(x/MW)
        if not upper:phi=-phi
        edge=rim(phi,1);sign=-1 if upper else 1
        canine=length>.30 if upper else length>.24
        inward=(.078 if canine else .021+.012*math.sin(tooth_index*1.7))
        bend_x=-math.copysign(inward,x) if abs(x)>.02 else .012
        lean_x=.010*math.sin(tooth_index*2.14+.3)
        bend_y=(.071 if canine else .035) if upper else (-.050 if canine else -.026)
        twist=.13*math.sin(tooth_index*1.83+.2)
        root_closed_z=(4.02+.025*(1-(x/MW)**2) if upper else 3.60+.11*(x/MW)**2)
        def center(t,endpoint):
            xx=x+lean_x*t+bend_x*t*t
            if endpoint:
                return Vector((xx,edge.y+.071+root_offset+bend_y*t*t,
                               edge.z+(-.014 if upper else .010)+sign*length*t))
            return Vector((xx,edge.y+(.37 if upper else .49)+root_offset+.022*t,
                           root_closed_z+sign*length*t))
        def point(t,a,rad,endpoint):
            c=center(t,endpoint)
            tang=(center(min(1,t+.001),endpoint)-center(max(0,t-.001),endpoint)).normalized()
            right=Vector((1,0,0));right=(right-tang*right.dot(tang)).normalized()
            depth_axis=tang.cross(right).normalized()
            angle=a+twist*(.3+.7*t)
            flute=1+(.035*math.sin(3*a+tooth_index*.71)+.018*math.sin(7*a))*math.sin(math.pi*t)
            return c+rad*flute*(rx*math.cos(angle)*right+rx*depth_ratio*math.sin(angle)*depth_axis)
        start=len(vv)
        for k,(t,rad) in enumerate(samples):
            for j in range(S):
                a=2*math.pi*j/S
                vv.append(tuple(point(t,a,rad,0)));oo.append(tuple(point(t,a,rad,1)))
                fade.append(t)
                streaks.append(.72+.17*math.sin(7*a+.4*math.sin(tooth_index))+.07*math.sin(3*a+tooth_index*.9))
                enamel_uv.append((math.cos(a),math.sin(a),t+3.1*tooth_index))
                if t>=.8:tips.append(len(vv)-1)
                if k:
                    prev=start+(k-1)*S;cur=start+k*S
                    ff.append((prev+j,prev+(j+1)%S,cur+(j+1)%S,cur+j))
        root=len(vv);vv.append(tuple(center(0,0)));oo.append(tuple(center(0,1)))
        fade.append(0);streaks.append(.75);enamel_uv.append((0,0,3.1*tooth_index))
        for j in range(S):ff.append((root,start+(j+1)%S,start+j))
        tip=len(vv);vv.append(tuple(center(1,0)));oo.append(tuple(center(1,1)))
        fade.append(1);streaks.append(.85);tips.append(tip);enamel_uv.append((0,0,1+3.1*tooth_index))
        last=start+(len(samples)-1)*S
        for j in range(S):ff.append((last+j,last+(j+1)%S,tip))
    obj=mesh('V20_UpperTeeth' if upper else 'V20_LowerTeeth',vv,ff,TEETH,
             role='upper_teeth' if upper else 'lower_teeth')
    normalize_normals(obj);morph(obj,oo);smooth(obj,1)
    for name,values in (('ToothTipFade',fade),('EnamelStreak',streaks)):
        a=obj.data.attributes.new(name,'FLOAT','POINT')
        for item,value in zip(a.data,values):item.value=value
    a=obj.data.attributes.new('EnamelCoord','FLOAT_VECTOR','POINT')
    for item,value in zip(a.data,enamel_uv):item.vector=value
    vg=obj.vertex_groups.new(name='QA_FreeToothTips');vg.add(tips,1,'REPLACE')
    obj['ToothCount']=len(descriptors)
    obj['design']='Individually swept elliptical crowns; asymmetric lengths, curvature, fluting and ivory streaks'
    return obj

upper_teeth=make_teeth(True);lower_teeth=make_teeth(False)

# Inner soft lip tissue closes behind the rest smile. On opening it folds into
# the upper gingiva, leaving the real deep cavity entirely unobstructed.
# This is not the visible outer lip and never replaces the open mouth volume.
seal_closed=[];seal_open=[];seal_faces=[];XS=65;CS=16
for k in range(XS):
    s=-1+2*k/(XS-1)
    c0=Vector((.675*s,-.69+.35*s*s+.032,3.83+.08*s*s))
    c1=Vector((.665*s,-.69+.35*s*s+.145,3.94+.14*max(0,1-s*s)**.33+.030))
    for j in range(CS):
        a=2*math.pi*j/CS
        seal_closed.append(tuple(c0+Vector((0,.012*math.sin(a),.025*math.cos(a)))))
        seal_open.append(tuple(c1+Vector((0,.018*math.sin(a),.024*math.cos(a)))))
        if k:
            seal_faces.append(((k-1)*CS+j,(k-1)*CS+(j+1)%CS,k*CS+(j+1)%CS,k*CS+j))
for ring in (0,XS-1):
    pole=len(seal_closed)
    seal_closed.append(tuple(sum((Vector(p) for p in seal_closed[ring*CS:(ring+1)*CS]),Vector())/CS))
    seal_open.append(tuple(sum((Vector(p) for p in seal_open[ring*CS:(ring+1)*CS]),Vector())/CS))
    for j in range(CS):seal_faces.append((ring*CS+j,ring*CS+(j+1)%CS,pole))
seal=mesh('V20_InnerLipSeal',seal_closed,seal_faces,INNER,role='interior')
normalize_normals(seal);morph(seal,seal_open);smooth(seal,1)
seal['design']='Soft inner lip closure folds behind upper lip when opening; no exposed enamel at rest'

# Rounded cloth tongue/floor pad: the video reference has a real raised oval
# with a central groove. It folds deeper into the chamber when the jaw closes.
tongue_rings=[[],[]];TM=26;TS=40
for i in range(TM):
    ph=math.pi*(i+1)/(TM+1);w=math.sin(ph)**.75
    for endpoint in (0,1):
        ring=[]
        for j in range(TS):
            a=2*math.pi*j/TS
            x=(.195 if endpoint==0 else .215)*w*math.cos(a)
            y=(.125 if endpoint==0 else .020)-(.22 if endpoint==0 else .315)*math.cos(ph)
            z=(3.77 if endpoint==0 else 3.435)-(.018 if endpoint==0 else .175)*math.cos(ph)
            z+=(.040 if endpoint==0 else .104)*math.sin(ph)**.8*math.sin(a)
            groove=math.exp(-(x/.037)**2)*w
            z-=(.008 if endpoint==0 else .032)*groove*max(0,math.sin(a))**2
            if endpoint:
                y+=.085*math.exp(-(x/.032)**2)*math.sin(ph)**.55*max(0,math.cos(ph))**2
            else:
                y+=.004*groove*(.7+.3*math.cos(ph))
            x+=.007*math.sin(ph)**2*math.sin(2*ph)
            ring.append((x,y,z))
        tongue_rings[endpoint].append(ring)
tv,tf=quad_rings(tongue_rings[0]);to,_=quad_rings(tongue_rings[1])
tongue=mesh('V20_ClothTongue',tv,tf,TONGUE,role='interior')
normalize_normals(tongue);morph(tongue,to);smooth(tongue,1)
tongue['design']='Muted plum cloth tongue with soft asymmetric volume and a central groove; root embeds in mouth floor'

# Ray-projected features: eye disks and cheek sewing are genuinely embedded
# into the evaluated head in both endpoints, rather than guessed in profile.
from mathutils.bvhtree import BVHTree
def surface_bvh(obj,value=None):
    if value is not None:
        rig['MouthOpen']=value;rig.update_tag();bpy.context.view_layer.update()
    return BVHTree.FromObject(obj,bpy.context.evaluated_depsgraph_get())

head_bvh=[surface_bvh(head,0),surface_bvh(head,1)]
def projected(bvh,x,z,offset=.0):
    co,normal,idx,dist=bvh.ray_cast(Vector((x,-2,z)),Vector((0,1,0)),5)
    if co is None:raise RuntimeError(f'Cannot project feature {x}, {z}')
    if normal.y>0:normal=-normal
    return co+normal*offset,normal

def eye_mesh(name,cx,cz,rx,rz,depth,mat,offset):
    bases=[projected(b,cx,cz,offset) for b in head_bvh]
    vv=[];oo=[];ff=[];S=40;R=14
    def point(phi,theta,endpoint):
        center,n=bases[endpoint]
        rot=Vector((0,-1,0)).rotation_difference(n)
        irregular=1+.013*math.sin(3*theta+.4)+.008*math.sin(5*theta)
        q=Vector((rx*math.sin(phi)*math.cos(theta)*irregular,
                  -depth*math.cos(phi),rz*math.sin(phi)*math.sin(theta)*irregular))
        return tuple(center+rot@q)
    vv.append(point(0,0,0));oo.append(point(0,0,1))
    for i in range(1,R):
        for j in range(S):
            phi=math.pi*i/R;theta=2*math.pi*j/S
            vv.append(point(phi,theta,0));oo.append(point(phi,theta,1))
            if i>1:
                a=1+(i-2)*S;b=1+(i-1)*S
                ff.append((a+j,b+j,b+(j+1)%S,a+(j+1)%S))
    tip=len(vv);vv.append(point(math.pi,0,0));oo.append(point(math.pi,0,1))
    for j in range(S):
        ff.append((0,1+j,1+(j+1)%S))
        a=1+(R-2)*S;ff.append((a+j,tip,a+(j+1)%S))
    obj=mesh(name,vv,ff,mat,coll=DETAIL)
    normalize_normals(obj);morph(obj,oo)
    return obj

for side,sgn in (('L',-1),('R',1)):
    eye_mesh('V20_EyeSocket.'+side,sgn*.285,EYE_Z,.112,.119,.011,FUR,-.006)
    eye_mesh('V20_InsetGlowEye.'+side,sgn*.285,EYE_Z,.102,.109,.014,EYE,.001)

def strand_mesh(name,paths,mat,radius=.01,bones=None,opened_paths=None,coll=DETAIL):
    vv=[];oo=[];ff=[];weights=[];SIDES=6
    for path_idx,path in enumerate(paths):
        openpath=opened_paths[path_idx] if opened_paths else path
        starts=[]
        for i,(p,q) in enumerate(zip(path,openpath)):
            p=Vector(p);q=Vector(q)
            tangent=(Vector(path[min(i+1,len(path)-1)])-Vector(path[max(i-1,0)])).normalized()
            tangent_o=(Vector(openpath[min(i+1,len(path)-1)])-Vector(openpath[max(i-1,0)])).normalized()
            def axes(t):
                a=t.cross(Vector((0,1,0)))
                if a.length<.01:a=t.cross(Vector((1,0,0)))
                a.normalize();return a,t.cross(a).normalized()
            a,b=axes(tangent);c,d=axes(tangent_o);start=len(vv);starts.append(start)
            for j in range(SIDES):
                th=2*math.pi*j/SIDES
                vv.append(tuple(p+radius*(a*math.cos(th)+b*math.sin(th))))
                oo.append(tuple(q+radius*(c*math.cos(th)+d*math.sin(th))))
                weights.append(bones(p) if callable(bones) else {bones or 'Head':1})
                if i:
                    last=starts[-2];ff.append((last+j,last+(j+1)%SIDES,start+(j+1)%SIDES,start+j))
        for end,reverse in ((0,True),(-1,False)):
            pi=len(vv);vv.append(tuple(path[end]));oo.append(tuple(openpath[end]))
            weights.append(bones(Vector(path[end])) if callable(bones) else {bones or 'Head':1})
            start=starts[end]
            for j in range(SIDES):
                ff.append((pi,start+(j+1)%SIDES,start+j) if reverse else (pi,start+j,start+(j+1)%SIDES))
    obj=mesh(name,vv,ff,mat,weights,coll)
    normalize_normals(obj)
    if opened_paths:morph(obj,oo)
    return obj

for side,sgn in (('L',-1),('R',1)):
    paths=[];opaths=[]
    for endpoint,arr in ((0,paths),(1,opaths)):
        def seam_z(x):
            return (3.96+.055*(x-.64)) if endpoint==0 else (4.080-.42*(x-.61))
        # A connected seam crossed by three repair tacks, not floating slashes.
        spine=[]
        for j in range(13):
            xx=.585+.158*j/12
            p,n=projected(head_bvh[endpoint],sgn*xx,seam_z(xx),.009)
            spine.append(tuple(p))
        arr.append(spine)
        for i in range(3):
            xx=.610+.052*i
            path=[]
            for t in (0,.2,.4,.6,.8,1):
                x=xx+(t-.5)*(.014+.008*math.sin(i+1))
                z=seam_z(x)+(t-.5)*(.072+.010*math.cos(i*1.4))
                p,n=projected(head_bvh[endpoint],sgn*x,z,.006+.006*math.sin(math.pi*t))
                path.append(tuple(p))
            arr.append(path)
    strand_mesh('V20_CheekRepairSeam.'+side,paths,THREAD,.008,opened_paths=opaths)

# Fine navy fabric-panel seam continues between the orbital pillows.
paths=[];opaths=[]
for endpoint,arr in ((0,paths),(1,opaths)):
    seam=[]
    for j in range(24):
        z=4.63-(4.63-4.105)*j/23
        x=.003*math.sin(j*.71)
        p,n=projected(head_bvh[endpoint],x,z,.002)
        seam.append(tuple(p))
    arr.append(seam)
strand_mesh('V20_CrownPanelSeam',paths,SOCKET,.0042,opened_paths=opaths)


# Parallel-transport-like ear frame: Y is thickness and the XZ normal follows
# the entire bend, eliminating the pinched angular hook of the old ear.
def catmull(points,t):
    u=t*(len(points)-1);i=min(len(points)-2,int(u));f=u-i
    a=Vector(points[max(0,i-1)]);b=Vector(points[i]);c=Vector(points[i+1]);d=Vector(points[min(len(points)-1,i+2)])
    return .5*(2*b+(-a+c)*f+(2*a-5*b+4*c-d)*f*f+(-a+3*b-3*c+d)*f*f*f)

ear_paths={
 'L':[(-.43,.025,4.64),(-.52,.025,4.94),(-.59,.04,5.28),(-.63,.07,5.61),(-.64,.08,5.78)],
 'R':[(.40,.11,4.64),(.45,.11,4.89),(.65,.07,5.06),(.85,-.05,4.96),(1.03,-.16,4.71),(1.15,-.20,4.44)]
}
ear_paths={side:[(x,y,z-.11) for x,y,z in path] for side,path in ear_paths.items()}
ear_objs={}
for side,path in ear_paths.items():
    rings=[];weights=[];M=34;S=40
    for i in range(M):
        t=i/(M-1);p=catmull(path,t)
        tangent=(catmull(path,min(1,t+.001))-catmull(path,max(0,t-.001))).normalized()
        normal=Vector((tangent.z,0,-tangent.x)).normalized()
        width=(.115*(1-t)+.29*math.sin(math.pi*t)**.56)
        depth=(.08*(1-t)+.145*math.sin(math.pi*t)**.50)
        if side=='R':
            transition=max(0,min(1,(t-.38)/.27))
            transition=transition*transition*(3-2*transition)
            width*=.64+.43*transition
        if t>.93:width=max(.014,width);depth=max(.012,depth)
        rings.append([tuple(p+normal*width*math.cos(2*math.pi*j/S)+Vector((0,depth*math.sin(2*math.pi*j/S),0))) for j in range(S)])
        a=max(0,min(1,(t-.37)/.22))
        weights.extend([{f'EarBase.{side}':1-a,f'EarTip.{side}':a} for _ in range(S)])
    vv,ff=quad_rings(rings);weights.extend([{f'EarBase.{side}':1},{f'EarTip.{side}':1}])
    ear=mesh('V20_PillowEar.'+side,vv,ff,FUR,weights,HEAD)
    normalize_normals(ear);smooth(ear,1);coverage(ear);ear_objs[side]=ear
    if side=='R':
        ear.data.materials.append(FELT)
        for poly in ear.data.polygons:
            if len(poly.vertices)!=4:continue
            k=poly.index//S;j=poly.index%S
            angle=2*math.pi*(j+.5)/S
            if 4<=k<=17 and math.cos(angle)>.32 and math.sin(angle)<.3:
                poly.material_index=1
                for vi in poly.vertices:ear.data.attributes['FleeceCoverage'].data[vi].value=0

# Update ear bone rest positions, preserving their hierarchy and body rig.
bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
for side,path in ear_paths.items():
    base=rig.data.edit_bones[f'EarBase.{side}'];tip=rig.data.edit_bones[f'EarTip.{side}']
    base.head=path[0];base.tail=catmull(path,.48)
    tip.head=base.tail;tip.tail=path[-1]
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()

ebvh=surface_bvh(ear_objs['L'])
ear_tacks=[];ear_spine=[]
for i in range(10):
    t=.18+i*.063+.003*math.sin(i*1.7);p=catmull(ear_paths['L'],t)
    c,n=projected(ebvh,p.x,p.z,.012);ear_spine.append(tuple(c))
    path=[]
    for a in (0,.25,.5,.75,1):
        q,n=projected(ebvh,p.x+(a-.5)*(.16+.013*math.sin(i*2.3)),
                      p.z+(a-.5)*(.018+.012*math.cos(i*1.7)),.012+.006*math.sin(math.pi*a))
        path.append(tuple(q))
    ear_tacks.append(path)
def ear_weight(p):
    t=max(0,min(1,(p.z-4.92)/.30));return {'EarBase.L':1-t,'EarTip.L':t}
strand_mesh('V20_UprightEar_SewnSpine',[ear_spine],THREAD,.009,ear_weight)
strand_mesh('V20_UprightEar_CrossTacks',ear_tacks,THREAD,.012,ear_weight)

# Rounded short neck is buried in the head and shoulders; no rigid collar.
nrings=[];neck_open_rings=[]
for z,rx,y0,ry0,y1,ry1 in ((3.00,.25,.07,.16,.12,.12),
                           (3.14,.24,.10,.14,.16,.08),
                           (3.28,.22,.13,.13,.20,.05),
                           (3.43,.20,.15,.105,.265,.025),
                           (3.59,.18,.22,.09,.33,.04)):
    nrings.append([(rx*math.cos(2*math.pi*j/32),y0+ry0*math.sin(2*math.pi*j/32),z) for j in range(32)])
    neck_open_rings.append([(rx*math.cos(2*math.pi*j/32),y1+ry1*math.sin(2*math.pi*j/32),z) for j in range(32)])
nv,nf=quad_rings(nrings)
nv_open,_=quad_rings(neck_open_rings)
neck=mesh('V20_SoftNeckBridge',nv,nf,FUR,[{'Neck':1} for _ in nv])
normalize_normals(neck);smooth(neck,2);coverage(neck,[1 if p[2]<3.30 else 0 for p in nv])
# Opening the enormous plush jaw also compresses the hidden upper chest and
# moves the soft neck slightly backwards. This preserves the closed join and
# prevents the old torso cap from appearing as a navy mound inside the mouth.
torso=bpy.data.objects['V20_Torso']
torso_open=[]
for v in torso.data.vertices:
    p=v.co.copy()
    if p.z>3.0:p.z=3.0+.20*(p.z-3.0)
    torso_open.append(tuple(p))
morph(torso,torso_open)
morph(neck,nv_open)
neck_mid=neck.shape_key_add(name='MouthClearanceMid',from_mix=False)
for i,(vertex,base) in enumerate(zip(neck_mid.data,nv)):
    t=max(0,min(1,(base[2]-3.25)/.18));t=t*t*(3-2*t)
    front=(1-math.sin(2*math.pi*(i%32)/32))/2 if i<len(nrings)*32 else .5
    vertex.co=Vector(base)+Vector((0,.060*t*front,0))
fc=neck_mid.driver_add('value');driver=fc.driver;driver.type='SCRIPTED'
var=driver.variables.new();var.name='opening';var.type='SINGLE_PROP'
var.targets[0].id=rig;var.targets[0].data_path='["MouthOpen"]'
driver.expression='max(0,4*opening*(1-opening))'
torso['mouth_clearance']='Upper chest compresses only above z=3 when MouthOpen rises; lower body and closed endpoint unchanged'
neck['mouth_clearance']='Tapered bridge joins closed head to torso; on opening it curves into the narrow posterior cavity wall'
print('V20_FEATURES_READY')


# Short, visible crimped textile loops. Instances remain procedural and
# separate from the deforming control mesh; no random displacement tears lips.
tuft_variants=[]
for variant in range(3):
    tuft_v=[];tuft_f=[];T=14;S=5
    for strand in range(3):
        phase=.7*strand+.8*variant
        def seed_path(t):
            if variant==1:
                a=-1.25+3.05*t
                x=.0058*math.cos(a)+.0018*(strand-1)
                y=.0080*math.sin(a)+.0012*math.sin(phase+5*t)
            else:
                x=.0032*math.sin(phase+(1.25 if variant==2 else .85)*2*math.pi*t)+.0020*(strand-1)
                y=.018*(t-.5)+.0018*math.sin(phase+7.3*t)
            z=.0018+.0065*math.sin(math.pi*t)**.8+.00065*strand
            return Vector((x,y,z))
        start=len(tuft_v)
        for i in range(T):
            t=i/(T-1);center=seed_path(t)
            tangent=(seed_path(min(1,t+.001))-seed_path(max(0,t-.001))).normalized()
            normal=tangent.cross(Vector((0,0,1)))
            if normal.length<.01:normal=tangent.cross(Vector((1,0,0)))
            normal.normalize();binormal=tangent.cross(normal).normalized()
            radius=(.00225+.00015*math.sin(phase))*(.34+.66*math.sin(math.pi*t)**.40)
            for j in range(S):
                a=2*math.pi*j/S
                tuft_v.append(tuple(center+radius*(normal*math.cos(a)+binormal*math.sin(a))))
                if i:tuft_f.append((start+(i-1)*S+j,start+(i-1)*S+(j+1)%S,start+i*S+(j+1)%S,start+i*S+j))
        tuft_f.extend([tuple(start+j for j in reversed(range(S))),tuple(start+(T-1)*S+j for j in range(S))])
    td=bpy.data.meshes.new('V20_BoucleTuftSeed_mesh.'+str(variant))
    td.from_pydata(tuft_v,[],tuft_f);td.materials.append(FUR)
    for p in td.polygons:p.use_smooth=True
    tuft=bpy.data.objects.new('V20_BoucleTuftSeed.'+str(variant),td);FLEECE.objects.link(tuft)
    tuft.hide_render=True;tuft.hide_set(True);tuft['qa_skip']=True
    tuft_variants.append(tuft)

gn=bpy.data.node_groups.new('V20_BoucleSurfaceInstances','GeometryNodeTree')
source_socket=gn.interface.new_socket(name='Source',in_out='INPUT',socket_type='NodeSocketObject')
density_socket=gn.interface.new_socket(name='Density',in_out='INPUT',socket_type='NodeSocketFloat')
gn.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
n=gn.nodes;l=gn.links
inp=n.new('NodeGroupInput');out=n.new('NodeGroupOutput')
surface=n.new('GeometryNodeObjectInfo');surface.name='SourceSurface';surface.transform_space='RELATIVE'
l.new(inp.outputs['Source'],surface.inputs['Object'])
scatter=n.new('GeometryNodeDistributePointsOnFaces');scatter.distribute_method='RANDOM'
scatter.inputs['Seed'].default_value=219
l.new(surface.outputs['Geometry'],scatter.inputs['Mesh'])
named=n.new('GeometryNodeInputNamedAttribute');named.data_type='FLOAT';named.inputs['Name'].default_value='FleeceCoverage'
mult=n.new('ShaderNodeMath');mult.name='DensityFactor';mult.operation='MULTIPLY'
l.new(named.outputs['Attribute'],mult.inputs[0]);l.new(inp.outputs['Density'],mult.inputs[1])
l.new(mult.outputs[0],scatter.inputs['Density'])
seeds=n.new('GeometryNodeGeometryToInstance')
for tuft in tuft_variants:
    seed=n.new('GeometryNodeObjectInfo');seed.inputs['Object'].default_value=tuft;seed.transform_space='ORIGINAL'
    l.new(seed.outputs['Geometry'],seeds.inputs['Geometry'])
instance=n.new('GeometryNodeInstanceOnPoints')
instance.inputs['Pick Instance'].default_value=True
seed_index=n.new('FunctionNodeRandomValue');seed_index.data_type='INT'
seed_index.inputs['Min'].default_value=0;seed_index.inputs['Max'].default_value=2
l.new(seed_index.outputs['Value'],instance.inputs['Instance Index'])
l.new(scatter.outputs['Points'],instance.inputs['Points'])
l.new(scatter.outputs['Rotation'],instance.inputs['Rotation'])
l.new(seeds.outputs['Instances'],instance.inputs['Instance'])
scale=n.new('FunctionNodeRandomValue');scale.data_type='FLOAT_VECTOR'
scale.inputs['Min'].default_value=(.72,.70,.74);scale.inputs['Max'].default_value=(1.35,1.32,1.42)
length=n.new('GeometryNodeInputNamedAttribute');length.data_type='FLOAT';length.inputs['Name'].default_value='FleeceLength'
pile_scale=n.new('ShaderNodeVectorMath');pile_scale.operation='SCALE'
l.new(scale.outputs['Value'],pile_scale.inputs[0]);l.new(length.outputs['Attribute'],pile_scale.inputs['Scale'])
l.new(pile_scale.outputs['Vector'],instance.inputs['Scale'])
rotate=n.new('GeometryNodeRotateInstances')
l.new(instance.outputs['Instances'],rotate.inputs['Instances'])
rotation=n.new('FunctionNodeRandomValue');rotation.data_type='FLOAT_VECTOR'
rotation.inputs['Min'].default_value=(0,0,0);rotation.inputs['Max'].default_value=(0,0,2*math.pi)
l.new(rotation.outputs['Value'],rotate.inputs['Rotation'])
if 'Local Space' in rotate.inputs:rotate.inputs['Local Space'].default_value=True
l.new(rotate.outputs['Instances'],out.inputs['Geometry'])

fleece_sources=[head,neck,*ear_objs.values()]
for name in ('V20_Torso','V20_Arm.L','V20_Arm.R','V20_Hand.L','V20_Hand.R',
             'V20_Leg.L','V20_Leg.R','V20_Foot.L','V20_Foot.R','V20_StitchedTail'):
    if name in bpy.data.objects:fleece_sources.append(bpy.data.objects[name])
for source in fleece_sources:
    if 'FleeceCoverage' not in source.data.attributes:
        if source.name=='V20_Torso':
            values=[0 if v.co.y<0 and (v.co.x/.49)**2+((v.co.z-2.49)/.64)**2<1.1 else 1 for v in source.data.vertices]
            coverage(source,values)
        else:coverage(source)
    if 'FleeceLength' not in source.data.attributes:
        attr=source.data.attributes.new('FleeceLength','FLOAT','POINT')
        for value in attr.data:value.value=1.0
    dat=bpy.data.meshes.new(source.name+'_curl_host')
    ob=bpy.data.objects.new(source.name.replace('V20_','V20_Fleece_'),dat)
    FLEECE.objects.link(ob);ob.parent=rig
    local=gn.copy();local.name='V20_Boucle_'+source.name
    srcnode=local.nodes['SourceSurface'];densitynode=local.nodes['DensityFactor']
    for link in list(srcnode.inputs['Object'].links):local.links.remove(link)
    srcnode.inputs['Object'].default_value=source
    for link in list(densitynode.inputs[1].links):local.links.remove(link)
    full_density=5200.0 if source==head or source in ear_objs.values() else 2300.0
    viewport=local.nodes.new('GeometryNodeIsViewport')
    preview_density=local.nodes.new('GeometryNodeSwitch');preview_density.input_type='FLOAT'
    preview_density.label='20% interactive density; full detail in renders'
    preview_density.inputs['False'].default_value=full_density
    preview_density.inputs['True'].default_value=full_density*.20
    local.links.new(viewport.outputs[0],preview_density.inputs['Switch'])
    local.links.new(preview_density.outputs[0],densitynode.inputs[1])
    if source==head:
        # Short plush pile remains on the OPEN lip roll, while the successful
        # resting contact edge stays trimmed. Blend fields with the same rig control.
        original=densitynode.inputs[0].links[0].from_socket
        local.links.remove(densitynode.inputs[0].links[0])
        open_mask=local.nodes.new('GeometryNodeInputNamedAttribute');open_mask.data_type='FLOAT'
        open_mask.inputs['Name'].default_value='FleeceOpenCoverage'
        difference=local.nodes.new('ShaderNodeMath');difference.operation='SUBTRACT'
        local.links.new(open_mask.outputs['Attribute'],difference.inputs[0]);local.links.new(original,difference.inputs[1])
        factor=local.nodes.new('ShaderNodeValue');factor.label='Rig MouthOpen: lip pile'
        fc=factor.outputs[0].driver_add('default_value');driver=fc.driver;driver.type='SCRIPTED'
        var=driver.variables.new();var.name='opening';var.type='SINGLE_PROP'
        var.targets[0].id=rig;var.targets[0].data_path='["MouthOpen"]'
        driver.expression='min(1,max(0,opening))'
        weighted=local.nodes.new('ShaderNodeMath');weighted.operation='MULTIPLY'
        local.links.new(difference.outputs[0],weighted.inputs[0]);local.links.new(factor.outputs[0],weighted.inputs[1])
        blend=local.nodes.new('ShaderNodeMath');blend.operation='ADD'
        local.links.new(original,blend.inputs[0]);local.links.new(weighted.outputs[0],blend.inputs[1])
        local.links.new(blend.outputs[0],densitynode.inputs[0])
        sockets=local.nodes.new('GeometryNodeJoinGeometry')
        sockets.label='Live eye sockets: follows morph and armature'
        for side in ('L','R'):
            socket_info=local.nodes.new('GeometryNodeObjectInfo')
            socket_info.transform_space='RELATIVE'
            socket_info.inputs['Object'].default_value=bpy.data.objects['V20_EyeSocket.'+side]
            local.links.new(socket_info.outputs['Geometry'],sockets.inputs['Geometry'])
        proximity=local.nodes.new('GeometryNodeProximity')
        proximity.target_element='FACES'
        local.links.new(sockets.outputs['Geometry'],proximity.inputs['Geometry'])
        clearance=local.nodes.new('ShaderNodeMapRange')
        clearance.clamp=True
        clearance.inputs['From Min'].default_value=.015
        clearance.inputs['From Max'].default_value=.025
        clearance.inputs['To Min'].default_value=0
        clearance.inputs['To Max'].default_value=1
        local.links.new(proximity.outputs['Distance'],clearance.inputs['Value'])
        mask=local.nodes.new('ShaderNodeMath');mask.operation='MULTIPLY'
        prior=densitynode.inputs[0].links[0].from_socket
        local.links.remove(densitynode.inputs[0].links[0])
        local.links.new(prior,mask.inputs[0])
        local.links.new(clearance.outputs['Result'],mask.inputs[1])
        local.links.new(mask.outputs[0],densitynode.inputs[0])
    mod=ob.modifiers.new('V20_RenderOnly_CurledFleece','NODES');mod.node_group=local
    ob['export_note']='Procedural hero fiber instances. Exclude or bake for Roblox runtime.'

# Rebuild a soft neutral studio. v18 inherited a dark -1.35 EV preview; v20
# explicitly resets exposure so textile form can be judged in actual light.
groundmat,_=material('MAT_Studio_LightWarmGrey_v20',(185,175,184),.92)
bpy.ops.mesh.primitive_plane_add(size=2000,location=(0,0,-.028))
ground=bpy.context.object;ground.name='Studio_Ground_NotAsset'
for c in list(ground.users_collection):c.objects.unlink(ground)
STUDIO.objects.link(ground);ground.data.materials.append(groundmat)
ground.visible_camera=False
world=bpy.data.worlds.new('V20_NeutralReviewWorld');world.use_nodes=True;scene.world=world
wn=world.node_tree.nodes;wl=world.node_tree.links
lightbg=wn['Background'];lightbg.inputs['Color'].default_value=(.45,.44,.50,1)
lightbg.inputs['Strength'].default_value=.23
camerabg=wn.new('ShaderNodeBackground');camerabg.inputs['Color'].default_value=(.60,.51,.57,1)
camerabg.inputs['Strength'].default_value=.8
path=wn.new('ShaderNodeLightPath');mix=wn.new('ShaderNodeMixShader')
wl.new(path.outputs['Is Camera Ray'],mix.inputs[0]);wl.new(lightbg.outputs[0],mix.inputs[1])
wl.new(camerabg.outputs[0],mix.inputs[2]);wl.new(mix.outputs[0],wn['World Output'].inputs['Surface'])
def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
for name,pos,energy,size,color in (
    ('Key',(-3.4,-4.5,7.4),1050,4.5,(1,.91,.84)),
    ('Fill',(4,-3.0,5.2),630,4.0,(.82,.86,1)),
    ('Rim',(-1.2,3.0,6.6),1250,3.0,(.69,.76,1))):
    d=bpy.data.lights.new('Studio_'+name,'AREA');d.energy=energy;d.shape='DISK';d.size=size;d.color=color
    o=bpy.data.objects.new('Studio_'+name,d);STUDIO.objects.link(o);o.location=pos;aim(o,(0,0,3.8))

cameras={}
for name,pos,target,scale in (
    ('front',(0,-10,4.13),(0,0,4.13),3.32),
    ('hero',(-2.1,-8,4.48),(0,0,4.13),3.32),
    ('profile',(-8,-.90,4.22),(0,0,4.13),3.32),
    ('reference_side',(-8,-3.4,4.32),(0,0,4.13),3.32),
    ('mouth',(-.9,-9,3.95),(0,-.1,3.92),1.95),
    ('full',(0,-13,3.4),(0,0,2.87),6.30)):
    d=bpy.data.cameras.new('CAM_V20_'+name);d.type='ORTHO';d.ortho_scale=scale
    o=bpy.data.objects.new('CAM_V20_'+name,d);STUDIO.objects.link(o);o.location=pos;aim(o,target);cameras[name]=o

quick='--quick' in sys.argv
scene.render.engine='CYCLES';scene.cycles.samples=28 if quick else 64
scene.cycles.use_denoising=True
scene.render.resolution_x=860 if quick else 1100
scene.render.resolution_y=860 if quick else 1100
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
scene.render.film_transparent=False
scene.view_settings.view_transform='AgX';scene.view_settings.exposure=0.0
scene.view_settings.gamma=1.0
scene.render.use_file_extension=True

# A restrained photographic bloom around the luminous cloth-eye inserts.
comp=bpy.data.node_groups.new('V20_RestrainedEyeGlow','CompositorNodeTree')
comp.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
layers=comp.nodes.new('CompositorNodeRLayers')
glow=comp.nodes.new('CompositorNodeGlare')
glow.inputs['Type'].default_value='Fog Glow'
glow.inputs['Quality'].default_value='High'
glow.inputs['Threshold'].default_value=1.5
glow.inputs['Strength'].default_value=.45
glow.inputs['Size'].default_value=.035
comp_out=comp.nodes.new('NodeGroupOutput')
comp.links.new(layers.outputs['Image'],glow.inputs['Image'])
comp.links.new(glow.outputs['Image'],comp_out.inputs['Image'])
scene.use_nodes=True
scene.compositing_node_group=comp

rig['MouthOpen']=1.0
rig.id_properties_ui('MouthOpen').update(min=0,max=1,description='0: clean smile seam; 1: dropped jaw and deep rounded-U gape')
rig.update_tag();bpy.context.view_layer.update()
scene['AssetRevision']='v20 – stuffed face, padded textile lips, folded cavity, grooved cloth tongue and individual enamel crowns'
scene['SoftwareBuiltWith']='Blender 5.3.0 official Linux release'
scene['AnimationStatus']='Mouth morph has independent sampled-state QA; legacy locomotion not retargeted'
scene['Reference']='User-provided open/closed/profile mouth sheet and four prior movement videos'
scene['ExportWarning']='High-detail procedural master. Fleece instances must be excluded/baked for Roblox LOD.'
scene['RigControl']='ARM_Plush_v20 custom property MouthOpen (0..1)'
for t in list(bpy.data.texts):
    if t.name.startswith('READ_ME'):bpy.data.texts.remove(t)
txt=bpy.data.texts.new('READ_ME_V20.txt')
txt.write('PLUSH V20 / Blender 5.3.0\nSelect ARM_Plush_v20, Custom Properties -> MouthOpen.\n')
txt.write('0 = closed upturned seam; 1 = deep gape with lower chin drop.\n')
txt.write('The core facial shell is closed and continuous; curled fleece is a separate procedural render layer.\n')
txt.write('Legacy locomotion clips are not retargeted. This is a model-review master, not a Roblox export.\n')
scene.camera=cameras['hero']
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
scene.render.filepath=str(OUT/'v20_hero_open.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Plush-v20-Face-Study.blend'),compress=True)
print('V20_SAVED',str(OUT/'Plush-v20-Face-Study.blend'))

if '--no-render' not in sys.argv:
    shots=[('front',1,'front_open'),('hero',1,'hero_open'),('profile',1,'profile_open'),
           ('front',0,'front_closed'),('front',.5,'front_half'),('full',1,'full_open')]
    if quick:shots=[('front',1,'front_open'),('profile',1,'profile_open'),('front',0,'front_closed')]
    for camera,value,label in shots:
        rig['MouthOpen']=value;rig.update_tag();bpy.context.view_layer.update()
        scene.camera=cameras[camera];scene.render.filepath=str(OUT/f'v20_{label}.png')
        bpy.ops.render.render(write_still=True)
print('V20_BUILD_DONE')
