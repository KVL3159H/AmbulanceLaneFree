"""Identity-checked shared junction catalog; one controller owns one junction."""
import json
import math
from pathlib import Path
from .config import JunctionConfig


class JunctionRegistry:
    def __init__(self, configurations):
        self.junctions={}
        controllers=set()
        for config in configurations:
            junction=config.junction
            identity=junction['id']; controller=junction['controller_id']
            if not identity or not controller or identity in self.junctions or controller in controllers:
                raise ValueError("junction/controller IDs must be nonempty and unique")
            if not all(math.isfinite(junction[key]) for key in ('latitude','longitude')):
                raise ValueError("invalid registry coordinates")
            if not -90<=junction['latitude']<=90 or not -180<=junction['longitude']<=180:
                raise ValueError("invalid registry coordinates")
            self.junctions[identity]=config; controllers.add(controller)

    @classmethod
    def load(cls,path):
        path=Path(path)
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('schemaVersion')!=2: raise ValueError("unsupported junction catalog")
        return cls([JunctionConfig(item,path) for item in data['junctions']])

    def resolve(self,junction_id,controller_id):
        config=self.junctions.get(junction_id)
        if config is None: raise ValueError("unknown junction")
        if config.junction['controller_id']!=controller_id: raise ValueError("incorrect controller")
        return config
