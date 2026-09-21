"""Original sculpted Bloodfang revision: continuous forms and paintable UVs."""
import math
import bpy
from mathutils import Vector
from mathutils.geometry import intersect_ray_tri
from geometry import MeshBuilder

PALETTE=[
    ('Obsidian scales',(0.022,.035,.044,1)),
    ('Soft throat scales',(.105,.135,.14,1)),
    ('Wine membrane',(.245,.006,.018,1)),
    ('Crimson membrane',(.43,.012,.03,1)),
    ('Wing bone',(.035,.021,.029,1)),
    ('Aged ivory',(.69,.53,.33,1)),
    ('Ivory tips',(.86,.77,.56,1)),
    ('Ruby iris',(.49,.007,.014,1)),
    ('Deep sockets',(.006,.003,.009,1)),
    ('Eye highlight',(.94,.58,.35,1)),
    ('Scale ridges',(.05,.07,.075,1)),
]

TAIL=[(0,.30,.68),(.05,.64,.50),(.20,.98,.37),(.46,1.25,.31),
      (.80,1.45,.34),(1.15,1.56,.46),(1.43,1.54,.67),
      (1.62,1.43,.92),(1.69,1.22,1.15),(1.68,.99,1.29)]


class Sculpt(MeshBuilder):
    def finish(self):
        data=bpy.data.meshes.new('Bloodfang_RefinedOriginalMesh')
        data.from_pydata(self.vertices,[],self.faces);data.update()
        if data.validate(verbose=True):raise ValueError('Sculpt needs geometry repair')
        obj=bpy.data.objects.new('Bloodfang_RefinedDragon',data)
        bpy.context.collection.objects.link(obj)
        for index,(name,color) in enumerate(PALETTE):
            mat=bpy.data.materials.new(name);mat.diffuse_color=color;mat.use_nodes=True
            nodes=mat.node_tree.nodes;links=mat.node_tree.links
            bsdf=nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=color
            bsdf.inputs['Roughness'].default_value=.77
            if index in (0,1,2,3,4,5,10):
                noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=5.5
                noise.inputs['Detail'].default_value=2
                ramp=nodes.new('ShaderNodeValToRGB')
                ramp.color_ramp.elements[0].color=(.65,.65,.65,1)
                ramp.color_ramp.elements[1].color=(1.15,1.15,1.15,1)
                links.new(noise.outputs['Fac'],ramp.inputs['Fac'])
                multiply=nodes.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY'
                multiply.inputs[0].default_value=1;multiply.inputs[1].default_value=color
                links.new(ramp.outputs['Color'],multiply.inputs[2]);links.new(multiply.outputs[0],bsdf.inputs['Base Color'])
            if index in (7,9):
                bsdf.inputs['Emission Color'].default_value=color
                bsdf.inputs['Emission Strength'].default_value=.12 if index==7 else .18
            data.materials.append(mat)
        for face,material in zip(data.polygons,self.materials):
            face.material_index=material;face.use_smooth=True
        for bone in sorted({key for value in self.weights for key in value}):
            group=obj.vertex_groups.new(name=bone)
            for i,weights in enumerate(self.weights):
                if weights.get(bone,0)>0:group.add([i],weights[bone],'REPLACE')
        bpy.context.view_layer.objects.active=obj;obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.uv.smart_project(angle_limit=math.radians(62),island_margin=.008)
        bpy.ops.object.mode_set(mode='OBJECT')
        # Small facial marks get dedicated texel space so pupils survive mipmaps.
        uv=data.uv_layers.active.data
        for item in uv:item.uv.y*=.91
        for face in data.polygons:
            if face.material_index not in (7,8,9):continue
            left=.03+(face.material_index-7)*.31
            for index,loop in enumerate(face.loop_indices):
                corner=[(0,0),(1,0),(1,1),(0,1)][index%4]
                uv[loop].uv=(left+.23*corner[0],.945+.040*corner[1])
        return obj

    def loft_z(self,sections,weights,sides=20):
        rows=[]
        for z,y,rx,ry in sections:
            rows.append([self.vertex((rx*math.cos(a),y+ry*math.sin(a),z),weights(z))
                         for a in (i*math.tau/sides for i in range(sides))])
        self.face(tuple(reversed(rows[0])),0);self.face(rows[-1],0)
        for a,b in zip(rows,rows[1:]):
            for i in range(sides):
                j=(i+1)%sides
                self.face((a[i],a[j],b[j],b[i]),1 if sides*.625<=i<sides*.875 else 0)

    def loft_y(self,sections,weights,material=0):
        # A bevelled wedge cross-section; broad skull roof and narrow lower jaw.
        shape=[(0,1),(.62,.92),(.96,.52),(1,.02),(.80,-.52),(.4,-.70),
               (0,-.75),(-.4,-.70),(-.8,-.52),(-1,.02),(-.96,.52),(-.62,.92)]
        rows=[]
        for y,z,width,height in sections:
            rows.append([self.vertex((x*width,y,z+v*height),weights) for x,v in shape])
        self.face(tuple(reversed(rows[0])),material);self.face(rows[-1],material)
        for a,b in zip(rows,rows[1:]):
            for i in range(len(shape)):
                j=(i+1)%len(shape);self.face((a[i],b[i],b[j],a[j]),material)

    def on_face(self,x,z,offset=0):
        origin=Vector((x,-2,z));ray=Vector((0,1,0));hits=[]
        for a,b,c in self.head_triangles:
            hit=intersect_ray_tri(a,b,c,ray,origin,True)
            if hit is not None:hits.append(hit.y)
        if not hits:raise ValueError(f'Eye or brow leaves skull surface: {x}, {z}')
        return Vector((x,min(hits)-offset,z))


def eye(m,side):
    w={'head':1}
    # Sockets, irises and slit pupils sit against the sculpt, not on eyeballs.
    outline=[(-1,0),(-.62,.56),(0,.86),(.64,.50),(1,0),(.61,-.45),(0,-.60),(-.66,-.38)]
    rim=[]
    for size,offset in [(1,.019),(.80,.032)]:
        rim.append([m.vertex(m.on_face(side*(.265+u*.112*size),
                    2.475+v*.085*size+u*.016,offset),w) for u,v in outline])
    # Only a border: no coplanar dark backing disk can fight the ruby surface.
    for i in range(8):
        j=(i+1)%8;m.face((rim[0][i],rim[0][j],rim[1][j],rim[1][i]),8)
    for size,offset,material in [(.80,.032,7)]:
        rows=[]
        for radius in (.25,.6,1):
            rows.append([m.vertex(m.on_face(side*(.265+u*.112*size*radius),
                         2.475+(v*.085*size+u*.016)*radius,offset),w) for u,v in outline])
        mid=m.vertex(m.on_face(side*.265,2.475,offset),w)
        for i in range(8):
            j=(i+1)%8;m.face((rows[0][i],rows[0][j],mid),material)
            for a,b in zip(rows,rows[1:]):m.face((a[i],a[j],b[j],b[i]),material)
    pupil=[(-.012,0),(0,.052),(.015,0),(0,-.040)]
    center=m.vertex(m.on_face(side*.265,2.475,.069),w)
    ids=[m.vertex(m.on_face(side*(.265+u),2.475+v,.069),w) for u,v in pupil]
    for i in range(4):m.face((ids[i],ids[(i+1)%4],center),8)
    glint=m.on_face(side*.235,2.497,.076)
    m.sphere(glint,(.014,.008,.014),9,w,7,4)
    m.tube([m.on_face(side*x,z,.025) for x,z in [(.145,2.505),(.22,2.548),(.325,2.555),(.382,2.52)]],
           [.017,.034,.031,.005],0,w,8)


def membrane(m,side):
    suffix='L' if side>0 else 'R'
    def p(x,y,z):return Vector((side*x,y,z))
    def weights(v):
        t=max(0,min(1,(abs(v[0])-1.05)/1.2))
        return {'wing.'+suffix:1-t,'wingtip.'+suffix:t}
    shoulder=p(.16,.05,1.57);elbow=p(.93,.23,2.22);wrist=p(1.58,.27,2.43)
    tips=[p(2.78,.43,2.24),p(2.43,.62,1.46),p(1.79,.69,.99),p(.96,.48,1.06),shoulder]
    controls=[p(2.21,.31,2.57),p(2.18,.48,2.02),p(1.91,.62,1.49),
              p(1.33,.56,1.38),p(.69,.27,1.40)]
    boundary=[wrist]
    start=wrist
    for end,control in zip(tips,controls):
        for step in range(1,7):
            t=step/6;boundary.append((1-t)**2*start+2*(1-t)*t*control+t*t*end)
        start=end
    boundary.extend([elbow])
    # Shared radial rings make a gently bowed, smoothly shaded thin membrane.
    center=p(1.36,.31,1.94)
    front_start=len(m.faces)
    front_triangles=[]
    for reverse in (False,True):
        offset=Vector((0,.022 if reverse else 0,0));rows=[]
        middle=m.vertex(center+offset,weights(center))
        for radius in (.30,.65,1):
            row=[]
            for edge in boundary:
                point=center.lerp(edge,radius)+offset
                point.y-=.065*math.sin(math.pi*radius)
                row.append(m.vertex(point,weights(point)))
            rows.append(row)
        count=len(boundary)
        for i in range(count):
            j=(i+1)%count
            f=(middle,rows[0][i],rows[0][j]);m.face(tuple(reversed(f)) if reverse else f,2 if reverse else 3)
            for a,b in zip(rows,rows[1:]):
                f=(a[i],b[i],b[j],a[j]);m.face(tuple(reversed(f)) if reverse else f,2 if reverse else 3)
        if not reverse:
            front_triangles=[tuple(Vector(m.vertices[k]) for k in (face[0],face[i],face[i+1]))
                             for face in m.faces[front_start:] for i in range(1,len(face)-1)]
    m.tube([shoulder,shoulder.lerp(elbow,.5),elbow,elbow.lerp(wrist,.55),wrist],
           [.075,.07,.065,.05,.040],0,weights,9)
    for end in tips[:4]:
        points=[]
        for t in (0,.125,.25,.375,.5,.625,.75,.875,1):
            point=wrist.lerp(end,t);hits=[]
            for a,b,c in front_triangles:
                hit=intersect_ray_tri(a,b,c,Vector((0,1,0)),Vector((point.x,-3,point.z)),True)
                if hit is not None:hits.append(hit.y)
            point.y=(min(hits) if hits else point.y)-.022
            points.append(point)
        m.tube(points,[.028,.026,.024,.0215,.019,.0155,.012,.0075,.003],4,weights,7)
    m.tube(boundary+[boundary[0]],[.010]*len(boundary)+[.010],4,weights,5)
    m.tube([wrist,p(1.61,.23,2.58),p(1.70,.26,2.62),p(1.74,.29,2.56)],
           [.037,.026,.012,.002],6,weights,7)


def tail(m):
    assignments=[{'tail.01':1},{'tail.01':1},{'tail.01':.5,'tail.02':.5},{'tail.02':1},
                 {'tail.02':.6,'tail.03':.4},{'tail.03':1},{'tail.03':.6,'tail.04':.4},
                 {'tail.04':1},{'tail.04':1},{'tail.04':1}]
    def weight(p):return assignments[min(range(len(TAIL)),key=lambda i:(Vector(TAIL[i])-p).length)]
    m.tube(TAIL,[.185,.163,.135,.109,.085,.063,.045,.032,.022,.012],0,weight,12)
    for i in (1,3,5,7):
        x,y,z=TAIL[i];height=.115-i*.008
        m.tube([(x,y,z+.08),(x,y+.022,z+.08+height)], [.055,.001],2,assignments[i],6)
    x,y,z=TAIL[-1];w={'tail.04':1}
    outline=[(x-.025,y+.07,z-.065),(x-.17,y-.04,z+.12),(x,y-.22,z+.34),
             (x+.18,y-.045,z+.13),(x+.028,y+.07,z-.065)]
    ids=[m.vertex(p,w) for p in outline];c=m.vertex((x,y-.05,z+.12),w)
    back=[m.vertex((a,b+.035,c),w) for a,b,c in outline]
    for i in range(5):
        j=(i+1)%5;m.face((ids[i],ids[j],c),3);m.face((back[j],back[i],c),2)
        m.face((ids[j],ids[i],back[i],back[j]),4)


def create_refined():
    m=Sculpt();head={'head':1};jaw={'jaw':1}
    def neck_weight(z):
        t=max(0,min(1,(z-1.50)/.40));return {'spine':1-t,'neck':t}
    m.loft_z([(.44,.12,.19,.18),(.62,.12,.29,.24),(.85,.09,.38,.30),(1.08,.07,.44,.33),
              (1.31,.05,.43,.32),(1.50,.01,.35,.285),(1.69,-.05,.27,.24),
              (1.89,-.12,.245,.22),(2.10,-.21,.27,.23),(2.30,-.31,.295,.24)],neck_weight)
    head_start=len(m.faces)
    m.loft_y([(.06,2.38,.23,.20),(-.16,2.40,.36,.285),(-.37,2.40,.40,.28),
              (-.59,2.36,.355,.22),(-.74,2.29,.27,.135),(-.97,2.28,.24,.105),
              (-1.07,2.28,.19,.085)],head)
    m.head_triangles=[tuple(Vector(m.vertices[k]) for k in (face[0],face[i],face[i+1]))
                      for face in m.faces[head_start:] for i in range(1,len(face)-1)]
    m.loft_y([(-.43,2.17,.25,.043),(-.65,2.155,.255,.035),(-.89,2.155,.23,.032),
              (-1.025,2.17,.17,.022)],jaw,1)
    m.loft_y([(-.51,2.203,.255,.035),(-.80,2.195,.25,.025),(-1.015,2.20,.18,.018)],head,8)
    for s in (-1,1):
        eye(m,s)
        m.tube([(s*.275,-.015,2.61),(s*.38,.055,2.73),(s*.445,.24,2.81),
                (s*.425,.46,2.835),(s*.34,.66,2.81),(s*.24,.82,2.755)],
               [.100,.086,.065,.042,.020,.001],5,head,11)
        m.tube([(s*.275,-.015,2.61),(s*.29,.025,2.68)],[.108,.096],10,head,10)
        for y,x,height in [(-.88,.207,.24),(-.61,.265,.13)]:
            m.tube([(s*x,y,2.245),(s*(x+.01),y-.018,2.245-height*.45),
                    (s*(x-.027),y-.043,2.245-height)], [.039,.029,.001],6,head,9)
        # Fine recessed nostril marks, aligned with the upper snout plane.
        m.sphere((s*.126,-.99,2.373),(.056,.036,.010),8,head,10,4)
        points=[(s*.19,.00,2.40),(s*.405,.22,2.48),(s*.36,.16,2.36),(s*.395,.22,2.25),
                (s*.18,.00,2.27)]
        ids=[m.vertex(p,head) for p in points];m.face(ids,2)
        back=[m.vertex((a,b+.018,c),head) for a,b,c in points];m.face(tuple(reversed(back)),2)
        arm={'arm.L' if s>0 else 'arm.R':1};foot={'foot.L' if s>0 else 'foot.R':1}
        # Muscle-shaped extrusions, with broad shoulder roots blending into chest.
        m.tube([(s*.31,-.02,1.47),(s*.45,-.04,1.36),(s*.56,-.14,1.17),
                (s*.53,-.36,1.04),(s*.52,-.54,.97)], [.14,.135,.102,.079,.071],0,arm,12)
        m.tube([(s*.52,-.50,.98),(s*.53,-.62,.94)],[.088,.077],10,arm,10)
        for toe in (-1,0,1):
            x=s*.53+toe*.058
            m.tube([(x,-.65,.955),(x,-.745,.91),(x,-.77,.85)],[.026,.019,.001],6,arm,7)
        m.tube([(s*.28,.13,.82),(s*.45,.11,.64),(s*.52,.025,.45),
                (s*.47,-.04,.25),(s*.46,-.26,.18)], [.21,.22,.16,.105,.103],0,foot,14)
        m.tube([(s*.46,-.22,.18),(s*.46,-.39,.15)],[.115,.105],10,foot,12)
        for toe in (-1,0,1):
            x=s*.46+toe*.093
            m.tube([(x,-.40,.16),(x,-.55,.14),(x,-.62,.09)],[.038,.024,.001],6,foot,8)
        membrane(m,s)
    # Low crest follows the skull and back rather than separate armor plates.
    for y,z,w,h in [(-.24,2.64,.08,.11),(-.02,2.62,.07,.10),(.13,2.39,.07,.10),
                     (.17,2.15,.065,.11),(.21,1.93,.065,.11),(.30,1.68,.065,.12)]:
        m.tube([(0,y,z),(0,y+.065,z+h)],[w,.001],10 if z>2.5 else 2,head if z>2.4 else {'neck':1},7)
    tail(m)
    return m.finish()
