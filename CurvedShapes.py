import sys
import os
import FreeCAD
from FreeCAD import Vector
import Part
from importlib import reload

global epsilon
epsilon = 1e-7

def get_module_path():
    """ Returns the current module path.
    Determines where this file is running from, so works regardless of whether
    the module is installed in the app's module directory or the user's app data folder.
    (The second overrides the first.)
    """
    return os.path.dirname(__file__)

    
def scale(obj, delta=Vector(1,1,1), center=Vector(0,0,0)):
    sh = obj.Shape.copy()
    if delta == Vector(1,1,1):
        return sh
    
    #if len(obj.Shape.Solids) > 0:
    #    sh.Placement.Base = Vector(0,0,0)
    #    sh.Placement.Rotation.Angle = -obj.Placement.Rotation.Angle
    #    delta = sh.Placement.Rotation.multVec(delta)
    #    sh.Placement.Rotation.Angle = 0
    
    m = FreeCAD.Matrix()
    m.scale(delta)
    sh = sh.transformGeometry(m)
    corr = Vector(center.x,center.y,center.z)
    corr.scale(delta.x,delta.y,delta.z)
    corr = (corr.sub(center)).negative()
    sh.translate(corr)
    sh.Placement = obj.Placement
    return sh


def PointVec(point):
    """Converts a Part::Point to a FreeCAD::Vector"""
    return Vector(point.X, point.Y, point.Z)

   
def boundbox_from_intersect(curves, pos, normal, doScaleXYZ):        
    if len(curves) == 0:
        return None
    
    plane = Part.Plane(pos, normal)
    xmin = float("inf")
    xmax = float("-inf")
    ymin = float("inf")
    ymax = float("-inf")
    zmin = float("inf")
    zmax = float("-inf")
    found = False
    for n in range(0, len(curves)):
        curve = curves[n]
        ipoints = []
        for edge in curve.Shape.Edges:
            i = plane.intersect(edge.Curve)          
            if i: 
                for p in i[0]:
                    parm = edge.Curve.parameter(PointVec(p))
                    if parm >= edge.FirstParameter and parm <= edge.LastParameter:    
                        ipoints.append(p)
                        found = True
        
        if found == False:
            return None
        
        use_x = True
        use_y = True
        use_z = True
        if len(ipoints) > 1:
            use_x = doScaleXYZ[n][0]
            use_y = doScaleXYZ[n][1]
            use_z = doScaleXYZ[n][2] 
        
        for p in ipoints:
            if use_x and p.X > xmax: xmax = p.X
            if use_x and p.X < xmin: xmin = p.X
            if use_y and p.Y > ymax: ymax = p.Y
            if use_y and p.Y < ymin: ymin = p.Y
            if use_z and p.Z > zmax: zmax = p.Z
            if use_z and p.Z < zmin: zmin = p.Z
      
    if xmin == float("inf") or xmax == float("-inf"):
        xmin = 0
        xmax = 0
    if ymin == float("inf") or ymax == float("-inf"):
        ymin = 0
        ymax = 0
    if zmin == float("inf") or zmax == float("-inf"):
        zmin = 0
        zmax = 0
   
    return FreeCAD.BoundBox(xmin, ymin, zmin, xmax, ymax, zmax)
    
            
def makeSurfaceSolid(ribs, solid):
    surfaces = []
    for e in range(0, len(ribs[0].Edges)):
        edge = ribs[0].Edges[e]      
        bs = edge.Curve.toBSpline()
        umults = bs.getMultiplicities()
        uknots = bs.getKnots()
        uperiodic = bs.isPeriodic()
        udegree = bs.Degree
        uweights = bs.getWeights()
        
        weights = []
        poles = []
        for r in ribs:
            weights += uweights
            spline = r.Edges[e].Curve.toBSpline()
            poles.append(spline.getPoles())
        
        if len(ribs) > 3:
            vmults = [4]
            vknots = [0]
            for i in range(1, len(ribs) - 3):
                vknots.append(i * 1.0 / (len(ribs) - 1))
                vmults.append(1)
            vmults.append(4)
            vknots.append(1.0)
        else:
            vmults = [len(ribs), len(ribs)]
            vknots = [0.0, 1.0]
        
        #print("poles:" + str(len(poles)) + "x" + str(len(poles[0])))
        #print("umults:" + str(umults))
        #print("vmults:" + str(vmults))
        #print("uknots:" + str(uknots))
        #print("vknots:" + str(vknots))
    
        try:
            bs = Part.BSplineSurface()
            bs.buildFromPolesMultsKnots(poles, vmults, umults, vknots, uknots, False, uperiodic, udegree, udegree) 
            surfaces.append(bs.toShape())
        except:      
            FreeCAD.Console.PrintError("BSplineSurface failed. Creating Lofts instead\n")      
            wiribs = []
            for r in ribs:
                wiribs.append(Part.Wire(r.Edges))
                                
            surfaces.append(Part.makeLoft(wiribs))
                 
    if solid:  
        face1 = makeFace(ribs[0])
        if face1:
            surfaces.append(face1)
        face2 = makeFace(ribs[len(ribs)-1])
        if face2:
            surfaces.append(face2)

        try:
            shell = Part.makeShell(surfaces)
            return Part.makeSolid(shell)
        except:
            FreeCAD.Console.PrintError("Creating solid failed !\n")
               
    if len(surfaces) == 1:
        return surfaces[0]
    elif len(surfaces) > 1:
        return Part.makeCompound(surfaces) 

        
        
def makeFace(rib):
    wire = Part.Wire(rib.Edges)
    if wire.isClosed():
        return Part.makeFace(wire, "Part::FaceMakerSimple")
    else:
        FreeCAD.Console.PrintError("Base shape is not closed. Cannot draw solid")   
   
        
def makeCurvedArray(Base = None, 
                    Hullcurves=[], 
                    Axis=Vector(0,0,0), 
                    Items=2, 
                    OffsetStart=0, 
                    OffsetEnd=0, 
                    Twist=0, 
                    Surface=False, 
                    Solid=False, 
                    extract=False):
    import CurvedArray
    reload(CurvedArray)
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython","CurvedArray")
    cs = CurvedArray.CurvedArrayWorker(obj, Base, Hullcurves, Axis, Items, OffsetStart, OffsetEnd, Twist, Surface, Solid, extract)
    CurvedArray.CurvedArrayViewProvider(obj.ViewObject)
    FreeCAD.ActiveDocument.recompute()
    return obj


def makeCurvedSegment(Shape1 = None, 
                      Shape2 = None, 
                    Hullcurves=[], 
                    NormalShape1=Vector(0,0,1), 
                    NormalShape2=Vector(0,0,1), 
                    Items=2, 
                    Surface=False, 
                    Solid=False):
    import CurvedSegment
    reload(CurvedSegment)
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython","CurvedSegment")
    cs = CurvedSegment.CurvedSegmentWorker(obj, Shape1, Shape2, Hullcurves, NormalShape1, NormalShape2, Items, Surface, Solid)
    CurvedSegment.CurvedSegmentViewProvider(obj.ViewObject)
    FreeCAD.ActiveDocument.recompute()
    return obj
        
