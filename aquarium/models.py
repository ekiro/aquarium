from dataclasses import dataclass
from datetime import datetime

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class Measurement:
    time: str
    temp: float
    heater: bool
    light: bool
    pump: bool
    uptime: float

    @property
    def time_iso(self):
        return datetime.fromisoformat(self.time)
