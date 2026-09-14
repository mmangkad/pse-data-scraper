# Test fixtures

Snapshots of real PSE EDGE responses, captured on **2026-09-15** during a live
audit of the endpoints documented in `docs/API.md`. They pin the parser to the
actual wire format so that a future EDGE markup or payload change fails loudly
in CI instead of silently producing empty output.

| Fixture | Endpoint | Contents |
|---|---|---|
| `company_directory_page1.html` | `GET /companyDirectory/search.ax?pageNo=1` | Page 1 of 6 (282 total rows): count span, paging div with `goPage(6)`, and 50 table rows incl. Sector / Subsector / Listing Date columns |
| `disclosure_chart_mer.json` | `POST /common/DisclosureCht.ax` (MER, Aug 2026 range) | `chartData` with 19 daily OHLC records (plus the ignored `tableData` disclosure notices) |

To re-capture after an API change, save the raw response bodies with the same
names and update the assertions that pin counts and dates.
