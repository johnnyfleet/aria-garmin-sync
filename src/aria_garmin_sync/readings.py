"""Turn Google Health weight and body-fat data points into paired weigh-ins."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class Reading:
    id: str  # Google data point ID; weight and body-fat for one weigh-in share it
    time: datetime  # aware, in the offset the scale recorded
    weight_kg: float
    fat_pct: float | None = None


def _sample_time(sample: dict) -> datetime:
    st = sample["sampleTime"]
    utc = datetime.fromisoformat(st["physicalTime"].replace("Z", "+00:00"))
    offset = int(st.get("utcOffset", "0s").rstrip("s"))
    return utc.astimezone(timezone(timedelta(seconds=offset)))


def _point_id(point: dict) -> str:
    return point["name"].rsplit("/", 1)[-1]


def pair(weights: list[dict], body_fats: list[dict]) -> list[Reading]:
    """Join weight and body-fat points by ID (falling back to identical timestamp), oldest first."""
    fat_by_id = {}
    fat_by_time = {}
    for p in body_fats:
        pct = p["bodyFat"]["percentage"]
        fat_by_id[_point_id(p)] = pct
        fat_by_time[_sample_time(p["bodyFat"])] = pct

    readings = []
    for p in weights:
        pid, t = _point_id(p), _sample_time(p["weight"])
        fat = fat_by_id.get(pid, fat_by_time.get(t))
        readings.append(Reading(pid, t, p["weight"]["weightGrams"] / 1000, fat))
    return sorted(readings, key=lambda r: r.time)
