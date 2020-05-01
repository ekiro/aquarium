from dataclasses import dataclass
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