"""Continuous lane paths for straight, left and right movements in metre coordinates."""
import math
from functools import lru_cache
from ..core.models import Approach

OPPOSITE={Approach.NORTH:Approach.SOUTH,Approach.SOUTH:Approach.NORTH,
          Approach.EAST:Approach.WEST,Approach.WEST:Approach.EAST}
INBOUND={Approach.NORTH:(-4,20),Approach.EAST:(20,4),Approach.SOUTH:(4,-20),Approach.WEST:(-20,-4)}
OUTBOUND={Approach.NORTH:(4,20),Approach.EAST:(20,-4),Approach.SOUTH:(-4,-20),Approach.WEST:(-20,4)}
OUTWARD={Approach.NORTH:(0,1),Approach.EAST:(1,0),Approach.SOUTH:(0,-1),Approach.WEST:(-1,0)}

@lru_cache(maxsize=12)
def movement_path(approach,destination):
    if approach==destination: raise ValueError("ordinary vehicles require a distinct exit")
    a=INBOUND[approach]; b=OUTBOUND[destination]
    inbound=OUTWARD[approach]; outbound=OUTWARD[destination]
    start=(a[0]+180*inbound[0],a[1]+180*inbound[1])
    end=(b[0]+180*outbound[0],b[1]+180*outbound[1])
    if destination==OPPOSITE[approach]: curve=[a,b]
    else:
        c=(a[0]-16*inbound[0],a[1]-16*inbound[1])
        d=(b[0]-16*outbound[0],b[1]-16*outbound[1])
        curve=[tuple((1-t)**3*a[k]+3*(1-t)**2*t*c[k]+3*(1-t)*t*t*d[k]+t**3*b[k] for k in (0,1))
               for t in (i/40 for i in range(41))]
    points=[start]+curve+[end]
    lengths=[math.dist(x,y) for x,y in zip(points,points[1:])]
    exit_progress=sum(lengths[:-1])
    return points,lengths,exit_progress,sum(lengths)

def position_on_path(approach,destination,progress):
    points,lengths,_,_=movement_path(approach,destination)
    remaining=max(0,progress)
    for a,b,length in zip(points,points[1:],lengths):
        if remaining<=length:
            ratio=remaining/length if length else 0
            return a[0]+(b[0]-a[0])*ratio,a[1]+(b[1]-a[1])*ratio,math.degrees(math.atan2(b[0]-a[0],b[1]-a[1]))%360
        remaining-=length
    return points[-1][0],points[-1][1],math.degrees(math.atan2(points[-1][0]-points[-2][0],points[-1][1]-points[-2][1]))%360
