"""v19: reference-driven head, lips, jaw silhouette, teeth, ears and fleece.

Blender 5.3.0. Reads the saved v18 master, never overwrites it.
The facial shell is a hand-designed quad loft, not a boolean-cut sphere.
Run: blender -b --python refine_plush_v19.py [-- --quick | --no-render]
"""

import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'plush_v19'
OUT.mkdir(exist_ok=True)
BASE=ROOT/'plush_v18'/'Plush-v18-Reference-Match.blend'
if not BASE.exists(): BASE=ROOT/'Plush-v18-Reference-Match.blend'
bpy.ops.wm.open_mainfile(filepath=str(BASE))
scene=bpy.context.scene
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
rig.name='ARM_Plush_v19'
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
    if o.name.startswith('V18_'):o.name=o.name.replace('V18_','V19_',1)
for c in bpy.data.collections:
    if c.name.startswith('V18_'):c.name=c.name.replace('V18_','V19_',1)

# Bury the old sleeve end caps inside the chest rather than leaving the
# pointed shoulders visible as separate conical masses beside the neck.
for side,sign in (('L',-1),('R',1)):
    sleeve=bpy.data.objects.get('V19_Arm.'+side)
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

HEAD=collection('V19_05 • redesigned facial topology')
DETAIL=collection('V19_06 • inset eyes, felt and stitching')
FLEECE=collection('V19_07 • procedural boucle / render master only')
STUDIO=collection('V19_08 • review studio / exclude from export')

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
FUR.name='MAT_Fabric_NavyVioletBoucle_v19'
FUR,p=material(FUR.name,(24,23,45),.91,.14)
p.inputs['Specular IOR Level'].default_value=.11
p.inputs['Sheen Tint'].default_value=rgb((44,39,73))
n=FUR.node_tree.nodes;l=FUR.node_tree.links
tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=95
tex.inputs['Detail'].default_value=3.2
coord=n.new('ShaderNodeTexCoord');l.new(coord.outputs['Object'],tex.inputs['Vector'])
ramp=n.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].position=.19;ramp.color_ramp.elements[0].color=rgb((22,20,41))
ramp.color_ramp.elements[1].position=.83;ramp.color_ramp.elements[1].color=rgb((34,31,61))
l.new(tex.outputs['Fac'],ramp.inputs['Fac']);l.new(ramp.outputs['Color'],p.inputs['Base Color'])
bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.18
bump.inputs['Distance'].default_value=.004
l.new(tex.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],p.inputs['Normal'])

INNER,ip=material('MAT_Mouth_VelvetDepth_v19',(14,8,20),.88,.04)
ip.inputs['Specular IOR Level'].default_value=.12
inn=INNER.node_tree.nodes;inl=INNER.node_tree.links
inoise=inn.new('ShaderNodeTexNoise');inoise.inputs['Scale'].default_value=13
inoise.inputs['Detail'].default_value=2
ibump=inn.new('ShaderNodeBump');ibump.inputs['Strength'].default_value=.24;ibump.inputs['Distance'].default_value=.012
inl.new(inoise.outputs['Fac'],ibump.inputs['Height']);inl.new(ibump.outputs['Normal'],ip.inputs['Normal'])
FELT,fp=material('MAT_Ear_InnerWornFelt_v19',(28,21,25),.96,.05)
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
EYE,_=material('MAT_Eyes_WarmInset_v19',(255,212,139),.35,0,5.0)
SOCKET,_=material('MAT_Eyes_RecessedShadow_v19',(13,12,24),.9)
TEETH,tp=material('MAT_Teeth_OrganicIvory_v19',(220,209,177),.52)
tn=TEETH.node_tree.nodes;tl=TEETH.node_tree.links
attr=tn.new('ShaderNodeAttribute');attr.attribute_name='ToothTipFade'
tr=tn.new('ShaderNodeValToRGB')
tr.color_ramp.elements[0].color=rgb((101,79,53));tr.color_ramp.elements[0].position=.0
tr.color_ramp.elements[1].color=rgb((221,207,174));tr.color_ramp.elements[1].position=.65
tl.new(attr.outputs['Fac'],tr.inputs['Fac']);tl.new(tr.outputs['Color'],tp.inputs['Base Color'])

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
HX=.80;HC=4.06;TOP=.72;HY=.65;MW=.655;N=96
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
    return Vector((HX*c*(1-.065*max(0,-s)),0,
                   HC+(TOP*s if s>=0 else (.72+.38*o)*s)))

def outward(phi,o):
    d=rim(phi+.0005,o)-rim(phi-.0005,o)
    return Vector((d.z,0,-d.x)).normalized()

def sphere_front(x,z,o):
    height=TOP if z>=HC else .72+.38*o
    return -HY*math.sqrt(max(0,1-(x/HX)**2-((z-HC)/height)**2))

FR=13;BR=15;IR=10
closed=[];opened=[];faces=[];mats=[];fleecemask=[]
def front_point(phi,k,o):
    p=rim(phi,o);n=outward(phi,o)
    width=.038+.035*o
    if k==0:return p
    if k==1:return p+n*(width*.39)+Vector((0,-.045,0))
    if k==2:return p+n*width+Vector((0,-.030,0))
    u=(k-2)/(FR-2)
    r=p+n*width;q=outer(phi,o)
    x=r.x*(1-u)+q.x*u;z=r.z*(1-u)+q.z*u
    natural=sphere_front(x,z,o)
    startnatural=sphere_front(r.x,r.z,o)
    y=natural+(p.y-.030-startnatural)*(1-u)**2
    return Vector((x,y,z))

for k in range(FR+1):
    for j in range(N):
        phi=2*math.pi*j/N
        closed.append(tuple(front_point(phi,k,0)));opened.append(tuple(front_point(phi,k,1)))
        # Eye clearance is evaluated against the live deformed sockets in GN.
        # A fixed vertex mask would leave a long bald patch when the face closes.
        fleecemask.append(0 if k<=1 else (.65 if k==2 else 1))
        if k:
            faces.append(((k-1)*N+j,k*N+j,k*N+(j+1)%N,(k-1)*N+(j+1)%N));mats.append(0)
outer_start=FR*N
for k in range(1,BR+1):
    start=len(closed);a=math.pi*.5*k/(BR+1)
    for j in range(N):
        phi=2*math.pi*j/N
        for o,arr in ((0,closed),(1,opened)):
            p=outer(phi,o);center=HC-.05*o
            arr.append((p.x*math.cos(a),HY*math.sin(a),center+(p.z-center)*math.cos(a)))
        fleecemask.append(1)
    for j in range(N):
        prev=outer_start if k==1 else start-N
        faces.append((prev+j,start+j,start+(j+1)%N,prev+(j+1)%N));mats.append(0)
pole=len(closed);closed.append((0,HY,HC));opened.append((0,HY,HC-.05));fleecemask.append(1)
for j in range(N):faces.append((pole-N+j,pole,pole-N+(j+1)%N));mats.append(0)

# Interior is a genuine manifold continuation of the aperture, with a throat
# cap behind every section. No nonplanar fan turns back through the lips.
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
            arr.append((p.x*shrink_x,p.y*(1-depth)+.27*depth,cz+(p.z-cz)*shrink_z+chamber))
        fleecemask.append(0)
    for j in range(N):
        prev=0 if k==1 else start-N
        faces.append((prev+j,prev+(j+1)%N,start+(j+1)%N,start+j));mats.append(1)
pole=len(closed);closed.append((0,.30,3.84));opened.append((0,.30,3.68));fleecemask.append(0)
for j in range(N):faces.append((pole-N+(j+1)%N,pole,pole-N+j));mats.append(1)

head=mesh('V19_HeadShell',closed,faces,FUR,role='head')
head.data.materials.append(INNER)
for p,m in zip(head.data.polygons,mats):p.material_index=m
normalize_normals(head)
morph(head,opened)
smooth(head,1)
coverage(head,fleecemask)
aperture=head.vertex_groups.new(name='QA_MouthAperture');aperture.add(list(range(N)),1,'REPLACE')
head['design']='Stable upper skull; dropped outer chin; rolled fabric lip; recessed mouth tunnel'
head['qa_budget_role']='High-detail master; fleece instances are not export LOD'

print('V19_HEAD_READY',len(closed),len(faces))


def make_teeth(upper=True):
    xs=([-.57,-.43,-.30,-.15,0,.15,.30,.43,.57] if upper
        else [-.57,-.45,-.32,-.19,-.065,.065,.19,.32,.45,.57])
    lengths=([.17,.40,.23,.20,.17,.20,.23,.40,.17] if upper
             else [.15,.28,.25,.22,.17,.17,.22,.25,.28,.15])
    radii=([.046,.078,.055,.048,.043,.048,.055,.078,.046] if upper
           else [.043,.065,.059,.052,.042,.042,.052,.059,.065,.043])
    vv=[];oo=[];ff=[];fade=[];tips=[];S=14
    samples=[(0,.80),(.10,1),(.24,.86),(.43,.66),(.62,.44),(.80,.22),(.93,.075)]
    for x,length,r in zip(xs,lengths,radii):
        phi=math.acos(x/MW)
        if not upper:phi=-phi
        edge=rim(phi,1)
        sign=-1 if upper else 1
        start=len(vv)
        for k,(t,rad) in enumerate(samples):
            for j in range(S):
                a=2*math.pi*j/S
                bend=.070*(abs(x)/MW)**.4 if abs(x)>.01 else 0
                curve=-math.copysign(bend,x)*t*t if abs(x)>.01 else 0
                xx=x+curve+r*rad*math.cos(a)
                # Opposing dental arches occupy different depths at rest.
                yy_open=edge.y+.062+(.050 if upper else -.040)*t*t+.052*rad*math.sin(a)
                zz_open=edge.z+(-.012 if upper else .012)+sign*length*t
                zz_closed=(4.02+.025*(1-(x/MW)**2) if upper else 3.62+.12*(x/MW)**2)+sign*length*t
                yy_closed=edge.y+(.36 if upper else .47)+.050*rad*math.sin(a)+.025*t
                vv.append((xx,yy_closed,zz_closed));oo.append((xx,yy_open,zz_open));fade.append(t)
                if t>=.8:tips.append(len(vv)-1)
                if k:
                    prev=start+(k-1)*S;cur=start+k*S
                    ff.append((prev+j,prev+(j+1)%S,cur+(j+1)%S,cur+j))
        root=len(vv)
        vv.append((x,edge.y+(.36 if upper else .47),4.02+.025*(1-(x/MW)**2) if upper else 3.62+.12*(x/MW)**2))
        oo.append((x,edge.y+.062,edge.z+(-.012 if upper else .012)));fade.append(0)
        for j in range(S):ff.append((root,start+(j+1)%S,start+j))
        tip=len(vv)
        bend=.070*(abs(x)/MW)**.4 if abs(x)>.01 else 0
        cx=x-(math.copysign(bend,x) if abs(x)>.01 else 0)
        vv.append((cx,edge.y+(.36 if upper else .47)+.025,
                   (4.02+.025*(1-(x/MW)**2) if upper else 3.62+.12*(x/MW)**2)+sign*length))
        oo.append((cx,edge.y+.062+(.050 if upper else -.040),
                   edge.z+(-.012 if upper else .012)+sign*length))
        fade.append(1);tips.append(tip)
        last=start+(len(samples)-1)*S
        for j in range(S):ff.append((last+j,last+(j+1)%S,tip))
    obj=mesh('V19_UpperTeeth' if upper else 'V19_LowerTeeth',vv,ff,TEETH,
             role='upper_teeth' if upper else 'lower_teeth')
    normalize_normals(obj);morph(obj,oo);smooth(obj,1)
    a=obj.data.attributes.new('ToothTipFade','FLOAT','POINT')
    for item,v in zip(a.data,fade):item.value=v
    vg=obj.vertex_groups.new(name='QA_FreeToothTips');vg.add(tips,1,'REPLACE')
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
seal=mesh('V19_InnerLipSeal',seal_closed,seal_faces,INNER,role='interior')
normalize_normals(seal);morph(seal,seal_open);smooth(seal,1)
seal['design']='Soft inner lip closure folds behind upper lip when opening; no exposed enamel at rest'

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
        q=Vector((rx*math.sin(phi)*math.cos(theta),
                  -depth*math.cos(phi),rz*math.sin(phi)*math.sin(theta)))
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
    eye_mesh('V19_EyeSocket.'+side,sgn*.285,4.375,.121,.128,.012,SOCKET,-.005)
    eye_mesh('V19_InsetGlowEye.'+side,sgn*.285,4.375,.101,.108,.014,EYE,.001)

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
    for i in range(4):
        x=sgn*(.604+i*.039)
        for endpoint,arr in ((0,paths),(1,opaths)):
            center_z=(3.98+i*.003) if endpoint==0 else (4.073-i*.022)
            path=[]
            for t in (0,.25,.5,.75,1):
                xx=x+sgn*(t-.5)*.035;zz=center_z+(t-.5)*.065
                p,n=projected(head_bvh[endpoint],xx,zz,.012)
                path.append(tuple(p))
            arr.append(path)
    strand_mesh('V19_CheekBlanketStitch.'+side,paths,THREAD,.010,opened_paths=opaths)


# Parallel-transport-like ear frame: Y is thickness and the XZ normal follows
# the entire bend, eliminating the pinched angular hook of the old ear.
def catmull(points,t):
    u=t*(len(points)-1);i=min(len(points)-2,int(u));f=u-i
    a=Vector(points[max(0,i-1)]);b=Vector(points[i]);c=Vector(points[i+1]);d=Vector(points[min(len(points)-1,i+2)])
    return .5*(2*b+(-a+c)*f+(2*a-5*b+4*c-d)*f*f+(-a+3*b-3*c+d)*f*f*f)

ear_paths={
 'L':[(-.43,.025,4.64),(-.52,.025,4.94),(-.59,.04,5.28),(-.63,.07,5.61),(-.64,.08,5.78)],
 'R':[(.40,.04,4.64),(.50,.02,4.85),(.73,.01,4.98),(1.00,.01,4.87),(1.17,.03,4.61),(1.18,.05,4.38)]
}
ear_objs={}
for side,path in ear_paths.items():
    rings=[];weights=[];M=34;S=40
    for i in range(M):
        t=i/(M-1);p=catmull(path,t)
        tangent=(catmull(path,min(1,t+.001))-catmull(path,max(0,t-.001))).normalized()
        normal=Vector((tangent.z,0,-tangent.x)).normalized()
        width=(.115*(1-t)+.29*math.sin(math.pi*t)**.56)
        depth=(.08*(1-t)+.145*math.sin(math.pi*t)**.50)
        if t>.93:width=max(.014,width);depth=max(.012,depth)
        rings.append([tuple(p+normal*width*math.cos(2*math.pi*j/S)+Vector((0,depth*math.sin(2*math.pi*j/S),0))) for j in range(S)])
        a=max(0,min(1,(t-.37)/.22))
        weights.extend([{f'EarBase.{side}':1-a,f'EarTip.{side}':a} for _ in range(S)])
    vv,ff=quad_rings(rings);weights.extend([{f'EarBase.{side}':1},{f'EarTip.{side}':1}])
    ear=mesh('V19_PillowEar.'+side,vv,ff,FUR,weights,HEAD)
    normalize_normals(ear);smooth(ear,1);coverage(ear);ear_objs[side]=ear
    if side=='R':
        ear.data.materials.append(FELT)
        for poly in ear.data.polygons:
            if len(poly.vertices)!=4:continue
            k=poly.index//S;j=poly.index%S
            angle=2*math.pi*(j+.5)/S
            if 5<=k<=23 and math.cos(angle)>.32 and math.sin(angle)<.3:
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
    t=max(0,min(1,(p.z-5.03)/.30));return {'EarBase.L':1-t,'EarTip.L':t}
strand_mesh('V19_UprightEar_SewnSpine',[ear_spine],THREAD,.009,ear_weight)
strand_mesh('V19_UprightEar_CrossTacks',ear_tacks,THREAD,.012,ear_weight)

# Rounded short neck is buried in the head and shoulders; no rigid collar.
nrings=[]
for z,rx,ry in ((3.00,.25,.20),(3.12,.27,.21),(3.24,.27,.21),(3.35,.25,.20)):
    nrings.append([(rx*math.cos(2*math.pi*j/32),.28+ry*math.sin(2*math.pi*j/32),z) for j in range(32)])
nv,nf=quad_rings(nrings)
neck=mesh('V19_SoftNeckBridge',nv,nf,FUR,[{'Neck':1} for _ in nv])
normalize_normals(neck);smooth(neck,2);coverage(neck)
# Opening the enormous plush jaw also compresses the hidden upper chest and
# moves the soft neck slightly backwards. This preserves the closed join and
# prevents the old torso cap from appearing as a navy mound inside the mouth.
torso=bpy.data.objects['V19_Torso']
torso_open=[]
for v in torso.data.vertices:
    p=v.co.copy()
    if p.z>3.0:p.z=3.0+.20*(p.z-3.0)
    torso_open.append(tuple(p))
morph(torso,torso_open)
morph(neck,[(p[0],p[1]+.08,p[2]) for p in nv])
torso['mouth_clearance']='Upper chest compresses only above z=3 when MouthOpen rises; lower body and closed endpoint unchanged'
neck['mouth_clearance']='Soft neck moves rearward by 0.08 at full opening'
print('V19_FEATURES_READY')


# Short, visible crimped textile loops. Instances remain procedural and
# separate from the deforming control mesh; no random displacement tears lips.
tuft_v=[];tuft_f=[];T=11;S=5
for i in range(T):
    t=i/(T-1);a=-.45*math.pi+2.20*math.pi*t
    center=Vector((.008*math.cos(a),.0055*math.sin(a),.003+.006*math.sin(math.pi*t)))
    tangent=Vector((-.008*math.sin(a),.0055*math.cos(a),.003*math.cos(math.pi*t))).normalized()
    normal=tangent.cross(Vector((0,0,1))).normalized();binormal=tangent.cross(normal).normalized()
    radius=.0040*(.84+.16*math.sin(math.pi*t))
    for j in range(S):
        ph=2*math.pi*j/S
        tuft_v.append(tuple(center+radius*(normal*math.cos(ph)+binormal*math.sin(ph))))
        if i:tuft_f.append(((i-1)*S+j,(i-1)*S+(j+1)%S,i*S+(j+1)%S,i*S+j))
tuft_f.extend([tuple(reversed(range(S))),tuple((T-1)*S+j for j in range(S))])
td=bpy.data.meshes.new('V19_BoucleTuftSeed_mesh');td.from_pydata(tuft_v,[],tuft_f);td.materials.append(FUR)
for p in td.polygons:p.use_smooth=True
tuft=bpy.data.objects.new('V19_BoucleTuftSeed',td);FLEECE.objects.link(tuft)
tuft.hide_render=True;tuft.hide_set(True)

gn=bpy.data.node_groups.new('V19_BoucleSurfaceInstances','GeometryNodeTree')
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
seed=n.new('GeometryNodeObjectInfo');seed.inputs['Object'].default_value=tuft;seed.transform_space='ORIGINAL'
instance=n.new('GeometryNodeInstanceOnPoints')
l.new(scatter.outputs['Points'],instance.inputs['Points'])
l.new(scatter.outputs['Rotation'],instance.inputs['Rotation'])
l.new(seed.outputs['Geometry'],instance.inputs['Instance'])
scale=n.new('FunctionNodeRandomValue');scale.data_type='FLOAT_VECTOR'
scale.inputs['Min'].default_value=(.67,.68,.65);scale.inputs['Max'].default_value=(1.34,1.30,1.5)
l.new(scale.outputs['Value'],instance.inputs['Scale'])
rotate=n.new('GeometryNodeRotateInstances')
l.new(instance.outputs['Instances'],rotate.inputs['Instances'])
rotation=n.new('FunctionNodeRandomValue');rotation.data_type='FLOAT_VECTOR'
rotation.inputs['Min'].default_value=(0,0,0);rotation.inputs['Max'].default_value=(0,0,2*math.pi)
l.new(rotation.outputs['Value'],rotate.inputs['Rotation'])
if 'Local Space' in rotate.inputs:rotate.inputs['Local Space'].default_value=True
l.new(rotate.outputs['Instances'],out.inputs['Geometry'])

fleece_sources=[head,neck,*ear_objs.values()]
for name in ('V19_Torso','V19_Arm.L','V19_Arm.R','V19_Hand.L','V19_Hand.R',
             'V19_Leg.L','V19_Leg.R','V19_Foot.L','V19_Foot.R','V19_StitchedTail'):
    if name in bpy.data.objects:fleece_sources.append(bpy.data.objects[name])
for source in fleece_sources:
    if 'FleeceCoverage' not in source.data.attributes:
        if source.name=='V19_Torso':
            values=[0 if v.co.y<0 and (v.co.x/.49)**2+((v.co.z-2.49)/.64)**2<1.1 else 1 for v in source.data.vertices]
            coverage(source,values)
        else:coverage(source)
    dat=bpy.data.meshes.new(source.name+'_curl_host')
    ob=bpy.data.objects.new(source.name.replace('V19_','V19_Fleece_'),dat)
    FLEECE.objects.link(ob);ob.parent=rig
    local=gn.copy();local.name='V19_Boucle_'+source.name
    srcnode=local.nodes['SourceSurface'];densitynode=local.nodes['DensityFactor']
    for link in list(srcnode.inputs['Object'].links):local.links.remove(link)
    srcnode.inputs['Object'].default_value=source
    for link in list(densitynode.inputs[1].links):local.links.remove(link)
    full_density=4500.0 if source==head or source in ear_objs.values() else 2300.0
    viewport=local.nodes.new('GeometryNodeIsViewport')
    preview_density=local.nodes.new('GeometryNodeSwitch');preview_density.input_type='FLOAT'
    preview_density.label='20% interactive density; full detail in renders'
    preview_density.inputs['False'].default_value=full_density
    preview_density.inputs['True'].default_value=full_density*.20
    local.links.new(viewport.outputs[0],preview_density.inputs['Switch'])
    local.links.new(preview_density.outputs[0],densitynode.inputs[1])
    if source==head:
        sockets=local.nodes.new('GeometryNodeJoinGeometry')
        sockets.label='Live eye sockets: follows morph and armature'
        for side in ('L','R'):
            socket_info=local.nodes.new('GeometryNodeObjectInfo')
            socket_info.transform_space='RELATIVE'
            socket_info.inputs['Object'].default_value=bpy.data.objects['V19_EyeSocket.'+side]
            local.links.new(socket_info.outputs['Geometry'],sockets.inputs['Geometry'])
        proximity=local.nodes.new('GeometryNodeProximity')
        proximity.target_element='FACES'
        local.links.new(sockets.outputs['Geometry'],proximity.inputs['Geometry'])
        clearance=local.nodes.new('ShaderNodeMapRange')
        clearance.clamp=True
        clearance.inputs['From Min'].default_value=.018
        clearance.inputs['From Max'].default_value=.029
        clearance.inputs['To Min'].default_value=0
        clearance.inputs['To Max'].default_value=1
        local.links.new(proximity.outputs['Distance'],clearance.inputs['Value'])
        mask=local.nodes.new('ShaderNodeMath');mask.operation='MULTIPLY'
        prior=densitynode.inputs[0].links[0].from_socket
        local.links.remove(densitynode.inputs[0].links[0])
        local.links.new(prior,mask.inputs[0])
        local.links.new(clearance.outputs['Result'],mask.inputs[1])
        local.links.new(mask.outputs[0],densitynode.inputs[0])
    mod=ob.modifiers.new('V19_RenderOnly_CurledFleece','NODES');mod.node_group=local
    ob['export_note']='Procedural hero fiber instances. Exclude or bake for Roblox runtime.'

# Rebuild a soft neutral studio. v18 inherited a dark -1.35 EV preview; v19
# explicitly resets exposure so textile form can be judged in actual light.
groundmat,_=material('MAT_Studio_LightWarmGrey_v19',(185,175,184),.92)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.028))
ground=bpy.context.object;ground.name='Studio_Ground_NotAsset'
for c in list(ground.users_collection):c.objects.unlink(ground)
STUDIO.objects.link(ground);ground.data.materials.append(groundmat)
world=bpy.data.worlds.new('V19_NeutralReviewWorld');world.use_nodes=True;scene.world=world
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
    ('front',(0,-10,4.18),(0,0,4.18),3.45),
    ('hero',(2.3,-8,4.60),(0,0,4.18),3.45),
    ('profile',(8,-.05,4.33),(0,0,4.18),3.45),
    ('full',(0,-13,3.4),(0,0,2.87),6.30)):
    d=bpy.data.cameras.new('CAM_V19_'+name);d.type='ORTHO';d.ortho_scale=scale
    o=bpy.data.objects.new('CAM_V19_'+name,d);STUDIO.objects.link(o);o.location=pos;aim(o,target);cameras[name]=o

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

rig['MouthOpen']=1.0
rig.id_properties_ui('MouthOpen').update(min=0,max=1,description='0: clean smile seam; 1: dropped jaw and deep rounded-U gape')
rig.update_tag();bpy.context.view_layer.update()
scene['AssetRevision']='v19 – mouth, jaw, pillow ears, inset eyes, curled fleece'
scene['SoftwareBuiltWith']='Blender 5.3.0 official Linux release'
scene['AnimationStatus']='Mouth morph has independent sampled-state QA; legacy locomotion not retargeted'
scene['Reference']='User-provided open/closed/profile mouth sheet and four prior movement videos'
scene['ExportWarning']='High-detail procedural master. Fleece instances must be excluded/baked for Roblox LOD.'
scene['RigControl']='ARM_Plush_v19 custom property MouthOpen (0..1)'
for t in list(bpy.data.texts):
    if t.name.startswith('READ_ME'):bpy.data.texts.remove(t)
txt=bpy.data.texts.new('READ_ME_V19.txt')
txt.write('PLUSH V19 / Blender 5.3.0\nSelect ARM_Plush_v19, Custom Properties -> MouthOpen.\n')
txt.write('0 = closed upturned seam; 1 = deep gape with lower chin drop.\n')
txt.write('The core facial shell is closed and continuous; curled fleece is a separate procedural render layer.\n')
txt.write('Legacy locomotion clips are not retargeted. This is a model-review master, not a Roblox export.\n')
scene.camera=cameras['hero']
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
scene.render.filepath=str(OUT/'v19_hero_open.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Plush-v19-Mouth-Refinement.blend'),compress=True)
print('V19_SAVED',str(OUT/'Plush-v19-Mouth-Refinement.blend'))

if '--no-render' not in sys.argv:
    shots=[('front',1,'front_open'),('hero',1,'hero_open'),('profile',1,'profile_open'),
           ('front',0,'front_closed'),('front',.5,'front_half'),('full',1,'full_open')]
    if quick:shots=[('front',1,'front_open'),('profile',1,'profile_open'),('front',0,'front_closed')]
    for camera,value,label in shots:
        rig['MouthOpen']=value;rig.update_tag();bpy.context.view_layer.update()
        scene.camera=cameras[camera];scene.render.filepath=str(OUT/f'v19_{label}.png')
        bpy.ops.render.render(write_still=True)
print('V19_BUILD_DONE')
