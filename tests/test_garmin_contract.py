"""Offline checks that the unofficial Garmin library still has the API this project uses.

These can't prove Garmin's servers still accept uploads, but they catch renamed or
changed methods in a dependency update before it is deployed.
"""

import inspect

from garminconnect import Garmin, GarminConnectAuthenticationError  # noqa: F401
from garminconnect.fit import FitEncoderWeight


def test_methods_used_still_exist_with_expected_parameters():
    params = inspect.signature(Garmin.add_body_composition).parameters
    assert {"timestamp", "weight", "percent_fat"} <= params.keys()
    assert "cdate" in inspect.signature(Garmin.get_daily_weigh_ins).parameters
    assert {"startdate", "enddate"} <= inspect.signature(Garmin.get_weigh_ins).parameters.keys()
    assert "tokenstore" in inspect.signature(Garmin.login).parameters
    for name in ("get_full_name",):
        assert callable(getattr(Garmin, name))


def test_fit_weight_file_encodes():
    from datetime import UTC, datetime

    dt = datetime(2026, 11, 7, 20, 27, 16, tzinfo=UTC)
    enc = FitEncoderWeight()
    enc.write_file_info()
    enc.write_file_creator()
    enc.write_device_info(dt)
    enc.write_weight_scale(dt, weight=90.17, percent_fat=22.666)
    enc.finish()
    data = enc.getvalue()
    assert data[8:12] == b".FIT" and len(data) > 50
