# Tableau Story workbook

- `Who_Should_We_Persuade_public.twbx`: sanitized final Story, 4 scenes and 1200 × 900 px.
- Four packaged Hyper extracts contain **aggregated** customer-group and strategy metrics; no client ID column is visible in workbook/extract schemas. This is not a substitute for a full Tableau Desktop inspection.
- The `.twb` XML was changed only to remove absolute CSV directory paths (`directory='.'`). Hyper extract paths are kept unchanged.
- Tableau Desktop/Public open-test, refresh behavior, and final publishing have **not** been verified in this environment.
- Aggregated source CSVs are in `../data/`. Refresh/reconnection may require manually pointing each source to the matching CSV. Use caution when publishing to Tableau Public, as packaged data become accessible.
