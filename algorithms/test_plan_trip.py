from datetime import datetime, timedelta, timezone

from plan_trip import as_warsaw, warsaw_offset


def test_warsaw_offset_is_summer_time_between_the_last_sundays_of_march_and_october():
    assert warsaw_offset(datetime(2026, 7, 1, 12, tzinfo=timezone.utc)) == timedelta(hours=2)
    assert warsaw_offset(datetime(2026, 12, 1, 12, tzinfo=timezone.utc)) == timedelta(hours=1)
    # 2026-10-25 01:00 UTC ends summer time
    assert warsaw_offset(datetime(2026, 10, 25, 0, 59, tzinfo=timezone.utc)) == timedelta(hours=2)
    assert warsaw_offset(datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)) == timedelta(hours=1)


def test_as_warsaw_keeps_naive_and_converts_aware_times():
    assert as_warsaw(datetime(2026, 10, 18, 8, 0)) == datetime(2026, 10, 18, 8, 0)
    assert as_warsaw(datetime(2026, 10, 17, 23, 30, tzinfo=timezone.utc)) == datetime(2026, 10, 18, 1, 30)
