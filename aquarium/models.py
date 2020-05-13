from dataclasses import dataclass
from datetime import datetime

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class TempMeasurement:
    time: str
    temp: float

    @property
    def time_iso(self):
        return datetime.fromisoformat(self.time)


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


@dataclass_json
@dataclass
class Config:
    device_id: int
    temp: float
    temp_tolerance: float
    light_start: str
    light_end: str
    pump_start: str
    pump_end: str
