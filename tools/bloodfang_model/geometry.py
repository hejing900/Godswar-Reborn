"""Original Bloodfang geometry. No imported mesh, texture or animation assets."""
import math
import bpy
from mathutils import Vector


PALETTE = [
    ("Charcoal fur", (0.025, 0.035, 0.055, 1)),
    ("Slate fur edges", (0.095, 0.12, 0.16, 1)),
    ("Wine membrane", (0.22, 0.007, 0.024, 1)),
    ("Crimson membrane", (0.43, 0.012, 0.035, 1)),
    ("Inner ear velvet", (0.24, 0.022, 0.050, 1)),
    ("Ivory fangs", (0.94, 0.83, 0.65, 1)),
    ("Eye socket", (0.014, 0.009, 0.021, 1)),
    ("Ruby eyes", (0.95, 0.035, 0.025, 1)),
    ("Pupil", (0.018, 0.006, 0.012, 1)),
    ("Eye glint", (1, 0.76, 0.50, 1)),
    ("Muzzle", (0.12, 0.13, 0.16, 1)),
    ("Nose", (0.29, 0.018, 0.035, 1)),
]


class MeshBuilder:
    def __init__(self):
        self.vertices, self.faces, self.materials, self.weights = [], [], [], []

    def vertex(self, position, weights):
        index = len(self.vertices)
        self.vertices.append(tuple(position))
        self.weights.append(dict(weights))
        return index

    def face(self, indexes, material):
        self.faces.append(tuple(indexes))
        self.materials.append(material)

    def sphere(self, center, radius, material, weights, segments=14, rings=8,
               angle=0):
        """Own latitude mesh with individually shaped proportions."""
        cx, cy, cz = center
        rx, ry, rz = radius
        def point(theta, phi):
            x = rx * math.sin(phi) * math.cos(theta)
            y = ry * math.sin(phi) * math.sin(theta)
            z = rz * math.cos(phi)
            return (cx+x*math.cos(angle)+z*math.sin(angle), cy+y,
                    cz+z*math.cos(angle)-x*math.sin(angle))
        top = self.vertex(point(0, 0), weights)
        row = []
        for j in range(1, rings):
            row.append([self.vertex(point(i*math.tau/segments, j*math.pi/rings),
                                    weights) for i in range(segments)])
        bottom = self.vertex(point(0, math.pi), weights)
        for i in range(segments):
            k = (i+1) % segments
            self.face((top, row[0][i], row[0][k]), material)
            self.face((bottom, row[-1][k], row[-1][i]), material)
            for j in range(len(row)-1):
                self.face((row[j][i], row[j+1][i], row[j+1][k], row[j][k]),
                          material)

    def tube(self, points, radii, material, weights, sides=7):
        """A tapered curved extrusion, also used for wing bones and fangs."""
        rows = []
        for i, raw in enumerate(points):
            p = Vector(raw)
            tangent = Vector(points[min(i+1,len(points)-1)]) - Vector(points[max(0,i-1)])
            tangent.normalize()
            axis = tangent.cross(Vector((0,1,0)))
            if axis.length < 0.01:
                axis = tangent.cross(Vector((1,0,0)))
            axis.normalize()
            other = tangent.cross(axis).normalized()
            w = weights(p) if callable(weights) else weights
            rows.append([self.vertex(p+radii[i]*(math.cos(a)*axis+math.sin(a)*other), w)
                         for a in [j*math.tau/sides for j in range(sides)]])
        self.face(tuple(reversed(rows[0])), material)
        self.face(rows[-1], material)
        for a,b in zip(rows,rows[1:]):
            for j in range(sides):
                k = (j+1)%sides
                self.face((a[j],a[k],b[k],b[j]),material)

    def build(self):
        mesh = bpy.data.meshes.new("Bloodfang_OriginalMesh")
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.update()
        if mesh.validate(verbose=True):
            raise RuntimeError("Original mesh required repair; inspect authoring geometry")
        obj = bpy.data.objects.new("Bloodfang", mesh)
        bpy.context.collection.objects.link(obj)
        for name,color in PALETTE:
            mat=bpy.data.materials.new(name)
            mat.diffuse_color=color
            mat.use_nodes=True
            shader=mat.node_tree.nodes.get("Principled BSDF")
            shader.inputs["Base Color"].default_value=color
            shader.inputs["Roughness"].default_value=0.76
            if name in ("Ruby eyes","Eye glint"):
                shader.inputs["Emission Color"].default_value=color
                shader.inputs["Emission Strength"].default_value=0.25
            mesh.materials.append(mat)
        uv = mesh.uv_layers.new(name="PaletteUV")
        for poly,material in zip(mesh.polygons,self.materials):
            poly.material_index=material
            # Exact texel-center swatches; no generated or copied texture needed.
            for loop in poly.loop_indices:
                uv.data[loop].uv=((material+0.5)/len(PALETTE),0.5)
            poly.use_smooth=False
        for bone in sorted({b for weights in self.weights for b in weights}):
            group=obj.vertex_groups.new(name=bone)
            for i,weights in enumerate(self.weights):
                if bone in weights:
                    group.add([i],weights[bone],"REPLACE")
        return obj


def create_ear(m, side):
    """Curved pinna shell, folded rim and recessed velvet interior."""
    bone="ear.L" if side>0 else "ear.R"
    w={bone:1}
    # Silhouette traces an asymmetrical pointed leaf, not a cone.
    outline=[(.34,2.81),(.29,3.23),(.40,3.72),(.86,4.22),
             (1.03,3.67),(1.03,3.24),(.80,2.84)]
    center=(side*.66,-.075,3.39)
    front=[]; back=[]; inner=[]
    for x,z in outline:
        y=-.13 + (z-2.8)*.075
        front.append(m.vertex((side*x,y,z),w))
        back.append(m.vertex((side*x,y+.19,z-.035),w))
        inner.append(m.vertex((side*(.66+(x-.66)*.74),y+.045,
                               3.36+(z-3.36)*.78),w))
    middle=m.vertex(center,w)
    rear=m.vertex((side*.66,.20,3.38),w)
    for i in range(len(outline)):
        j=(i+1)%len(outline)
        m.face((front[i],front[j],inner[j],inner[i]),1)
        m.face((inner[i],inner[j],middle),4)
        m.face((front[j],front[i],back[i],back[j]),0)
        m.face((back[j],back[i],rear),0)
    # Small inside fold gives the ear a readable curved structure in 3/4 view.
    m.tube([(side*.48,-.135,2.93),(side*.48,-.125,3.26),
            (side*.67,-.03,3.64)], [.045,.037,.008],1,w,5)


def create_wing(m, side):
    suffix="L" if side>0 else "R"
    def p(x,y,z): return (side*x,y,z)
    def w(point):
        blend=max(0,min(1,(abs(point[0])-1.15)/1.1))
        return {"wing."+suffix:1-blend,"wingtip."+suffix:blend}
    shoulder=p(.52,.07,1.80)
    elbow=p(1.05,.065,2.19)
    wrist=p(1.76,.03,2.50)
    # Bats' long fingers form the membrane ribs. Concave scallops hang between.
    endpoints=[p(3.00,.10,2.19),p(2.66,.15,1.24),
               p(1.89,.20,.68),p(.96,.21,.79),p(.52,.12,1.28)]
    boundary=[wrist, endpoints[0],p(2.65,.13,1.93),endpoints[1],
              p(2.28,.17,1.18),endpoints[2],p(1.48,.20,1.03),
              endpoints[3],p(.73,.17,1.14),endpoints[4],shoulder,elbow]
    # Give each fan sector a slightly domed center and doubled membrane surface.
    center=Vector(p(1.58,.09,1.69))
    for i in range(len(boundary)):
        a=Vector(boundary[i]); b=Vector(boundary[(i+1)%len(boundary)])
        centroid=(a+b+center)/3
        centroid.y-=.045
        front=[m.vertex(v,w(v)) for v in (center,a,b,centroid)]
        for tri in ((0,1,3),(1,2,3),(2,0,3)):
            m.face(tuple(front[j] for j in tri),3 if i%3 else 2)
        back=[m.vertex(v+Vector((0,.035,0)),w(v)) for v in (center,b,a)]
        m.face(back,2)
    m.tube([shoulder,elbow,wrist], [.115,.095,.075],0,w,8)
    for i,tip in enumerate(endpoints[:4]):
        mid=(Vector(wrist)+Vector(tip))/2
        mid.y-=.065
        m.tube([wrist,mid,tip],[.045,.026,.009],1,w,6)
    for a,b in zip(boundary,boundary[1:]+boundary[:1]):
        m.tube([a,b],[.020,.017],0,w,5)
    # Curved thumb hook on the leading edge.
    m.tube([wrist,p(1.77,-.005,2.70),p(1.89,-.012,2.80),p(1.98,0,2.70)],
           [.066,.052,.030,.005],5,w,7)


def create_bloodfang():
    m=MeshBuilder()
    body={"spine":1}; head={"head":1}
    # Pear-shaped breast with a narrower waist and a deliberately broad brow.
    m.sphere((0,.055,1.33),(.58,.39,.75),0,body,16,10)
    m.sphere((0,-.245,1.42),(.39,.17,.47),1,body,12,7)
    m.sphere((0,-.035,2.43),(.78,.48,.66),0,head,18,10)
    # Slate cheeks and angular fur fans outline the face.
    for s in (-1,1):
        m.sphere((s*.36,-.375,2.24),(.31,.18,.27),10,head,12,7)
        for z,x in ((2.50,.68),(2.32,.69),(2.15,.60)):
            root=m.vertex((s*(x-.14),-.10,z+.10),head)
            edge=m.vertex((s*x,-.25,z+.10),head)
            tip=m.vertex((s*(x+.18),-.07,z-.12),head)
            low=m.vertex((s*(x-.07),-.20,z-.10),head)
            back=m.vertex((s*x,.14,z),head)
            m.face((root,edge,tip,low),1)
            m.face((root,back,tip,edge),0)
            m.face((low,tip,back,root),0)
        # Almond eyes follow the slanted brow plane, with tall vertical pupils.
        m.sphere((s*.32,-.442,2.57),(.262,.075,.187),6,head,12,7,angle=s*.20)
        m.sphere((s*.32,-.503,2.57),(.190,.055,.124),7,head,12,7,angle=s*.20)
        m.sphere((s*.31,-.55,2.57),(.031,.017,.102),8,head,8,5)
        m.sphere((s*.275,-.568,2.624),(.035,.013,.037),9,head,7,5)
        m.tube([(s*.095,-.466,2.735),(s*.32,-.475,2.799),
                (s*.58,-.387,2.75)],[.064,.092,.035],0,head,7)
        # Curved fangs descend forward from the muzzle; no straight cones.
        m.tube([(s*.225,-.493,2.17),(s*.24,-.545,2.02),
                (s*.205,-.58,1.83)], [.091,.068,.005],5,head,8)
        # Short hind legs and little three-clawed feet.
        leg={"foot.L" if s>0 else "foot.R":1}
        m.tube([(s*.27,.04,.82),(s*.33,-.01,.41),(s*.36,-.15,.29)],
               [.16,.115,.13],0,leg,8)
        m.sphere((s*.35,-.15,.29),(.19,.23,.11),1,leg,10,5)
        for toe in (-1,0,1):
            x=s*.35+toe*.10
            m.tube([(x,-.26,.28),(x,-.39,.24),(x,-.42,.16)],
                   [.036,.023,.002],5,leg,6)
        create_ear(m,s)
        create_wing(m,s)
    # Mouth opening and raised little nose: a proper face at in-game scale.
    m.sphere((0,-.435,2.115),(.245,.075,.102),6,head,12,5)
    m.sphere((0,-.459,2.27),(.19,.13,.11),10,head,12,5)
    nose=[(-.135,-.57,2.35),(.135,-.57,2.35),(0,-.606,2.20),
          (0,-.64,2.30),(0,-.52,2.30)]
    ids=[m.vertex(p,head) for p in nose]
    for f in ((0,1,3),(1,2,3),(2,0,3),(0,4,1),(1,4,2),(2,4,0)):
        m.face([ids[i] for i in f],11)
    # Distinctive swept forehead crest ties the pinnae together.
    crest=[(-.25,-.20,2.99),(.25,-.20,2.99),(0,-.50,2.75),
           (0,-.01,3.16),(0,-.39,3.04)]
    ids=[m.vertex(p,head) for p in crest]
    for f in ((0,2,4),(2,1,4),(1,3,4),(3,0,4),(0,3,1,2)):
        m.face([ids[i] for i in f],1 if f[0] in (0,1) else 0)
    tail={"tail":1}
    m.tube([(0,.24,.83),(0,.38,.50),(0,.43,.20)], [.11,.06,.008],0,tail,7)
    tips=[(-.27,.30,.56),(0,.43,.20),(.27,.30,.56),(0,.22,.82)]
    ids=[m.vertex(p,tail) for p in tips]
    m.face(ids,2)
    reverse=[m.vertex((x,y+.018,z),tail) for x,y,z in reversed(tips)]
    m.face(reverse,2)
    return m.build()
