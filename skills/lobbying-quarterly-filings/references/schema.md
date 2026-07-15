# Schema notes

## `get_local_senate_filings()` output columns

Same tidy shape `lobbyR::get_filings()` returns from the live API (verified by diffing
`get_filings.R`'s `tidyr::hoist()`/`unnest()`/`pivot_wider()` block against a real record
from `data/senate/2026/filings/filings_2026.json` -- identical field names, because the
local JSON is the same `results` array shape the API returns).

| Column | Notes |
|---|---|
| `registrant.name`, `client.name` | Who's lobbying, who's paying. |
| `registrant.id`, `client.id` | Senate-internal numeric IDs. |
| `registrant.house_registrant_id` | A Senate cross-reference field pointing at a House registrant number. ~29% NA in the 2026 sample -- not reliable enough to lean on. |
| `filing_type` | Raw code (`RR`, `Q1`, `1T`, `1A`, ...) -- see `data/senate/constants/filing_types.json` or the table in `data_quality_notes.md`. |
| `filing_period` | `first_quarter` / `second_quarter` / `third_quarter` / `fourth_quarter` (older filings may use `mid_year` / `year_end`). |
| `income`, `expenses` | Registrants report `income` (paid by client) or `expenses` (self-filers), rarely both. |
| `<issue code display name>` columns (e.g. `Budget/Appropriations`) | Wide-pivoted from `lobbying_activities[].description`, one column per ALI issue area present in the loaded data, values are list-columns (a filing can touch an issue more than once). |
| `covered_positions` | *Carry-through, not classified.* Semicolon-joined `covered_position` text from every lobbyist on the filing. Revolving-door analysis starts here, in a later pass. |
| `foreign_entities_flag`, `foreign_entity_names` | *Carry-through, not classified.* Whether/who the filing lists as a foreign entity. |
