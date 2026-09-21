"""Original juvenile vampiric dragon. Uses only our mathematical mesh helpers."""
import math
from mathutils import Vector
from geometry import MeshBuilder


TAIL_POINTS=[(0,.36,.82),(.10,.80,.60),(.48,1.25,.42),(1.05,1.57,.43),
             (1.57,1.67,.72),(1.91,1.50,1.17),(1.98,1.18,1.56)]


def plate(m, center, width, height, depth, material, weights):
    x,y,z=center
    points=[(x-width,y,z+height*.30),(x,y-depth,z+height*.50),
            (x+width,y,z+height*.30),(x+width*.77,y,z-height*.20),
            (x,y-depth*.35,z-height*.55),(x-width*.77,y,z-height*.20),
            (x,y-depth,z)]
    ids=[m.vertex(p,weights) for p in points]
    for i in range(6):m.face((ids[i],ids[(i+1)%6],ids[6]),material)


def muzzle(m, weights, lower=False):
    """Long, shaped snout with a squared front and tapered cheek transition."""
    sections=[(-.24,.39,2.44,.17),(-.67,.37,2.41,.16),(-1.03,.29,2.39,.13)]
    if lower:sections=[(-.27,.29,2.20,.075),(-.66,.32,2.20,.07),(-1.005,.26,2.20,.06)]
    rings=[]
    for y,half,z,height in sections:
        ring=[]
        for i in range(8):
            a=math.tau*i/8
            ring.append(m.vertex((half*math.cos(a),y,z+height*math.sin(a)),weights))
        rings.append(ring)
    m.face(tuple(reversed(rings[0])),0)
    m.face(rings[-1],10 if lower else 0)
    for a,b in zip(rings,rings[1:]):
        for i in range(8):
            j=(i+1)%8
            m.face((a[i],b[i],b[j],a[j]),10 if lower else (1 if i in (1,2) else 0))


def wing(m, side):
    suffix="L" if side>0 else "R"
    def p(x,y,z):return (side*x,y,z)
    def w(point):
        blend=max(0,min(1,(abs(point[0])-1.05)/1.0))
        return {"wing."+suffix:1-blend,"wingtip."+suffix:blend}
    shoulder=p(.43,.22,1.94);elbow=p(.96,.22,2.40);wrist=p(1.61,.27,2.72)
    tips=[p(2.80,.37,2.42),p(2.42,.46,1.54),p(1.67,.53,1.02),p(.91,.38,1.10)]
    boundary=[wrist,tips[0],p(2.44,.42,2.14),tips[1],p(2.06,.49,1.49),
              tips[2],p(1.28,.46,1.32),tips[3],p(.63,.27,1.37),shoulder,elbow]
    center=Vector(p(1.46,.34,1.89))
    for i in range(len(boundary)):
        a=Vector(boundary[i]);b=Vector(boundary[(i+1)%len(boundary)])
        crown=(a+b+center)/3;crown.y-=.05
        ids=[m.vertex(v,w(v)) for v in (center,a,b,crown)]
        for tri in ((0,1,3),(1,2,3),(2,0,3)):
            m.face(tuple(ids[j] for j in tri),2 if i%3==0 else 3)
        back=[m.vertex(v+Vector((0,.035,0)),w(v)) for v in (center,b,a)]
        m.face(back,2)
    m.tube([shoulder,elbow,wrist],[.10,.083,.055],0,w,8)
    for tip in tips:
        midpoint=(Vector(wrist)+Vector(tip))/2;midpoint.y-=.05
        m.tube([wrist,midpoint,tip],[.039,.024,.006],1,w,6)
    for a,b in zip(boundary,boundary[1:]+boundary[:1]):
        m.tube([a,b],[.017,.014],0,w,5)
    m.tube([wrist,p(1.64,.22,2.89),p(1.75,.24,2.95),p(1.80,.27,2.86)],
           [.050,.037,.021,.003],5,w,6)


def curved_tail(m):
    radii=[.24,.20,.16,.125,.09,.060,.032]
    assignments=[{"tail.01":1},{"tail.01":.75,"tail.02":.25},
                 {"tail.01":.2,"tail.02":.8},{"tail.02":.6,"tail.03":.4},
                 {"tail.03":1},{"tail.03":.25,"tail.04":.75},{"tail.04":1}]
    def w(point):
        nearest=min(range(len(TAIL_POINTS)),key=lambda i:(Vector(TAIL_POINTS[i])-point).length)
        return assignments[nearest]
    m.tube(TAIL_POINTS,radii,0,w,10)
    # Dorsal blade scales follow the curved tail; all are individually authored.
    for i in range(1,6):
        x,y,z=TAIL_POINTS[i];size=.15-i*.014
        front=m.vertex((x-.07,y-.11,z+radii[i]*.72),assignments[i])
        back=m.vertex((x+.07,y+.11,z+radii[i]*.72),assignments[i])
        tip=m.vertex((x+.04,y+.04,z+radii[i]+size),assignments[i])
        left=m.vertex((x-.035,y+.07,z+radii[i]*.90),assignments[i])
        right=m.vertex((x+.035,y-.07,z+radii[i]*.90),assignments[i])
        m.face((front,tip,left),2);m.face((back,left,tip),3)
        m.face((front,right,tip),3);m.face((back,tip,right),2)
    # Crimson spade: a thick diamond fin visibly distinct from either wing.
    x,y,z=TAIL_POINTS[-1];weights={"tail.04":1}
    outline=[(x-.05,y+.08,z-.10),(x-.28,y-.05,z+.16),(x,y-.25,z+.51),
             (x+.27,y-.05,z+.17),(x+.05,y+.08,z-.10)]
    front=[m.vertex(p,weights) for p in outline]
    ridge=m.vertex((x,y-.12,z+.20),weights)
    back=[m.vertex((a,b+.052,c),weights) for a,b,c in outline]
    rear=m.vertex((x,y+.04,z+.20),weights)
    for i in range(len(outline)):
        j=(i+1)%len(outline)
        m.face((front[i],front[j],ridge),3)
        m.face((back[j],back[i],rear),2)
        m.face((front[j],front[i],back[i],back[j]),0)


def create_dragon():
    m=MeshBuilder();body={"spine":1};neck={"neck":1};head={"head":1};jaw={"jaw":1}
    # A substantial reptilian chest, rising neck, broad skull and long snout.
    m.sphere((0,.06,1.20),(.53,.43,.76),0,body,16,10)
    m.sphere((0,.04,1.91),(.31,.30,.66),0,neck,14,9)
    m.sphere((0,-.085,2.64),(.54,.405,.46),0,head,16,9)
    muzzle(m,head);muzzle(m,jaw,lower=True)
    # Overlapping belly and throat scutes, separated by narrow dark seams.
    for z,width,y in [(0.76,.28,-.31),(1.00,.36,-.37),(1.24,.39,-.37),
                       (1.48,.35,-.34),(1.70,.26,-.26)]:
        plate(m,(0,y,z),width,.26,.055,1,body)
    for z,width,y in [(1.91,.235,-.24),(2.10,.235,-.265),(2.27,.22,-.30)]:
        plate(m,(0,y,z),width,.18,.035,10,neck)
    for s in (-1,1):
        # A strongly modeled sloping brow with forward-looking ruby slit eyes.
        m.sphere((s*.39,-.327,2.69),(.188,.092,.160),6,head,12,7,angle=s*.23)
        m.sphere((s*.39,-.40,2.687),(.13,.059,.104),7,head,12,7,angle=s*.23)
        m.sphere((s*.387,-.449,2.681),(.025,.017,.086),8,head,8,5)
        m.sphere((s*.365,-.465,2.73),(.025,.011,.025),9,head,7,5)
        m.tube([(s*.20,-.34,2.83),(s*.39,-.35,2.882),(s*.54,-.23,2.78)],
               [.059,.078,.032],1,head,7)
        # A pair of sweeping, ridged horns; no tall mammalian ears.
        m.tube([(s*.34,.035,2.94),(s*.45,.16,3.18),(s*.51,.36,3.37),
                (s*.46,.66,3.43)], [.145,.116,.070,.004],5,head,9)
        m.tube([(s*.34,.035,2.94),(s*.385,.085,3.035)], [.16,.135],1,head,9)
        # Tiny triangular cheek fins read as reptilian frills.
        points=[(s*.43,.09,2.56),(s*.71,.26,2.82),(s*.66,.23,2.56),
                (s*.73,.24,2.35),(s*.45,.01,2.42),(s*.53,.055,2.57)]
        ids=[m.vertex(p,head) for p in points]
        for f in ((0,1,5),(1,2,5),(2,3,5),(3,4,5),(4,0,5)):
            m.face(tuple(ids[i] for i in f),2 if f[0]%2 else 3)
        for a,b in zip(points[:5],points[1:5]+points[:1]):
            m.tube([a,b],[.018,.012],0,head,5)
        # Two visible long fangs plus smaller back teeth per side.
        for y,z,r in [(-.84,2.35,.067),(-.45,2.33,.048)]:
            x=s*(.27 if y<-.7 else .35)
            m.tube([(x,y,z),(x+s*.015,y-.025,z-.13),
                    (x-s*.025,y-.035,z-.27 if y<-.7 else z-.20)],
                   [r,r*.7,.003],5,head,7)
        m.sphere((s*.19,-.963,2.495),(.064,.039,.027),6,head,9,5)
        # Separate forearms: tucked elbows, forward hands and three grasping claws.
        arm={"arm.L" if s>0 else "arm.R":1}
        m.tube([(s*.37,-.025,1.73),(s*.68,-.20,1.34),(s*.60,-.56,1.12)],
               [.14,.12,.095],0,arm,9)
        m.sphere((s*.61,-.58,1.08),(.145,.17,.105),1,arm,10,6)
        for digit in (-1,0,1):
            x=s*.61+digit*.08
            m.tube([(x,-.67,1.06),(x,-.79,1.02),(x,-.82,.94)],
                   [.032,.023,.002],5,arm,6)
        # Robust dinosaur-like hind legs are visibly separate from the forearms.
        foot={"foot.L" if s>0 else "foot.R":1}
        m.sphere((s*.44,.08,.63),(.28,.31,.36),0,foot,12,7)
        m.tube([(s*.52,.05,.55),(s*.62,-.03,.27),(s*.60,-.28,.20)],
               [.18,.14,.12],0,foot,9)
        m.sphere((s*.60,-.29,.17),(.23,.30,.115),1,foot,12,6)
        for digit in (-1,0,1):
            x=s*.60+digit*.13
            m.tube([(x,-.47,.18),(x,-.64,.16),(x,-.70,.09)],
                   [.052,.029,.002],5,foot,7)
        wing(m,s)
    # Nose shield and central armored head crest.
    plate(m,(0,-1.07,2.40),.20,.17,.03,1,head)
    for y,z,width in [(-.19,2.995,.17),(.045,3.02,.14),(.24,2.91,.12)]:
        points=[(-width,y,z-.07),(width,y,z-.07),(0,y-.06,z+.13),(0,y+.15,z+.02)]
        ids=[m.vertex(p,head) for p in points]
        for f in ((0,1,2),(1,3,2),(3,0,2),(0,3,1)):
            m.face(tuple(ids[i] for i in f),1)
    # Back crest shows clearly in the rear view between the wings.
    for z,y,size in [(2.38,.29,.16),(2.13,.30,.17),(1.86,.32,.18),(1.59,.43,.18)]:
        weight=neck if z>1.8 else body
        points=[(-.045,y,z-.13),(.045,y,z-.13),(0,y+size,z+.075),(0,y,z+.12)]
        ids=[m.vertex(p,weight) for p in points]
        for f in ((0,1,2),(1,3,2),(3,0,2),(0,3,1)):
            m.face(tuple(ids[i] for i in f),2 if f[0]%2 else 3)
    curved_tail(m)
    mesh=m.build();mesh.name="Bloodfang_VampiricDragon"
    mesh.data.name="Bloodfang_OriginalDragonMesh"
    return mesh
