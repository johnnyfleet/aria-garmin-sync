from datetime import timedelta

from aria_garmin_sync.readings import pair


def _point(kind, pid, physical, offset="46800s", **value):
    key = {"weight": "weight", "body-fat": "bodyFat"}[kind]
    return {
        "name": f"users/1/dataTypes/{kind}/dataPoints/{pid}",
        key: {"sampleTime": {"physicalTime": physical, "utcOffset": offset}, **value},
    }


def test_pairs_weight_and_body_fat_by_id():
    weights = [_point("weight", "111", "2026-11-07T20:27:16Z", weightGrams=90170)]
    fats = [_point("body-fat", "111", "2026-11-07T20:27:16Z", percentage=22.666)]
    [r] = pair(weights, fats)
    assert r.id == "111"
    assert r.weight_kg == 90.17
    assert r.fat_pct == 22.666
    assert r.time.utcoffset() == timedelta(hours=13)
    assert r.time.hour == 9 and r.time.minute == 27


def test_falls_back_to_timestamp_and_sorts_oldest_first():
    weights = [
        _point("weight", "2", "2026-11-08T20:00:00Z", weightGrams=90000),
        _point("weight", "1", "2026-11-01T19:49:00Z", weightGrams=89350),
    ]
    fats = [_point("body-fat", "other-id", "2026-11-08T20:00:00Z", percentage=22.5)]
    readings = pair(weights, fats)
    assert [r.id for r in readings] == ["1", "2"]
    assert readings[0].fat_pct is None
    assert readings[1].fat_pct == 22.5
