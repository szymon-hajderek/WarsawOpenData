# Walking route duration

- Fix #72: walking route totals and arrival times now include the walking leg instead of a zero-second override.
- Add regression cases for seven- and twenty-one-minute walks, including arrival after midnight.
- The user explicitly authorized this route-engine fix. No dependencies, environment setup, or API fields changed.
- Validation: both regression cases failed before the fix; all 82 backend tests pass after it.
