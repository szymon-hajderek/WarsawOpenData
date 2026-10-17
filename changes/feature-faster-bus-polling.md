# feature/faster-bus-polling

- Bus detection poller runs every 3 s (was 10 s), so a new position is caught soon after the feed publishes it (about every 10 s).
- `/api/live/vehicles` has its own cache of 3 s (was 30 s, shared with stop lines and times). Without this the poller would read the same cached answer for 30 s. Lines and times keep the 30 s cache.
- Unchanged: `max_age_s` = 300 (a freshness filter), history = 3 positions per vehicle (repeats are skipped).
- Assumption: the City Hall API accepts 1 request per 3 s per vehicle type (limit not documented).
