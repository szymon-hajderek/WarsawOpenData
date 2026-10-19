# fix/route-list-duplicates

- Route list: the same rides arriving at the same time are one option (only the one leaving latest stays); before,
  a second copy that just left earlier and waited longer showed up right under the first.
- Option ids are unique in one answer: another run of a metro frequency trip gets `@HHMM` (#118);
  `route_delays.trip_ids_from_option` ignores the suffix. `data/API.md` updated.
