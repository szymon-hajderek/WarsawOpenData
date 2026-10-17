# GTFS geometry cache version

- Rebuild unversioned or incompatible GTFS caches instead of inferring distance units from a maximum across feeds.
- Stamp the final atomic NPZ with a cache version and keep that metadata out of stop-time arrays.
- This replaces truncated metro kilometre values with metre distances rebuilt from raw GTFS, allowing existing shape geometry to be used.
- Add regression coverage for mixed-feed legacy data, cache reuse, incompatible versions, missing fields, precision and concurrent builds.
- Document the automatic rebuild at the next backend restart. No new dependencies, downloads or API fields.
- Validation: 89 backend tests and 4 shape-unit tests pass. All 16 real M1/M2 trip templates use GTFS shapes after migration (147 / 138 points).
