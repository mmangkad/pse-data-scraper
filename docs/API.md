# PSE EDGE API Reference

Behavioral reference for the endpoints this scraper uses. Everything below was
**verified live on 2026-09-15** (an audit session of ~28 rate-limited requests,
plus follow-up live checks during development; see also `tests/fixtures/README.md`).
These endpoints are undocumented and can change without notice — the fixture
tests pin the wire format so a change fails loudly in CI instead of silently
producing empty output.

Contents:

1. [Infrastructure](#1-infrastructure)
2. [Company directory](#2-company-directory)
3. [Historical chart data](#3-historical-chart-data)
4. [Adjacent endpoints (mapped, not used)](#4-adjacent-endpoints-mapped-not-used)
5. [Politeness](#5-politeness)

## 1. Infrastructure

- The site is fronted by **Cloudflare** (these endpoints return
  `cf-cache-status: DYNAMIC`) and F5 BIG-IP (a `BIGipServerPOOL_EDGE` cookie
  is set on the first response; it is not required on subsequent requests).
- Responses may be gzip-compressed (`requests` handles this transparently).
- A full browser `User-Agent` is required in practice; the scraper sends one.
- No authentication is needed for anything documented here.

## 2. Company directory

`GET https://edge.pse.com.ph/companyDirectory/search.ax`

### Query parameters

| Param | Value | Verified behavior |
|---|---|---|
| `pageNo` | 1-based integer | 50 rows per page. `pageNo=0` → 200 + empty table. Past the last page → 200 + empty `<tbody>`. |
| `keyword` | free text | Case-insensitive **substring** match on company name (`aYAlA` → 3 rows). |
| `sector` | exact string | One of the fixed set: `Financials`, `Industrial`, `Holding Firms`, `Services`, `Mining and Oil`, `Small, Medium & Emerging Board`, `ETF`. |
| `subsector` | exact string | Works in combination with `sector` (e.g. `sector=Mining and Oil` + `subsector=Mining` → 20 rows). |

The form (`GET /companyDirectory/form.do`) also exposes sorting via
`cmpySortType` / `symbolSortType` / `dateSortType` / `sortType` (the
`goSort(...)` handlers) — not used by the scraper.

Counts drift as listings change. On 2026-09-15 the unfiltered directory was
**6 pages / 282 rows**; `sector=Mining and Oil` alone returned 24 rows.

### Response (HTML)

- Rows live in `table.list tbody tr`, with columns:
  - `td[0]` company name — anchor with `onclick="cmDetail('COMPANY_ID','SECURITY_ID')"`
  - `td[1]` stock symbol — anchor (same `cmDetail` payload)
  - `td[2]` sector, `td[3]` subsector
  - `td[4]` listing date, formatted `Mar 22, 1973`
- **Pagination markers**, both reliable truncation detectors:
  - a count span: `<span class="count"> [1 / 6] [Total 282] </span>` —
    current page / total pages / total rows (whitespace inside varies)
  - the paging div's end icon: `goPage(6)` — the absolute last page number
- The scraper passes `keyword` / `sector` / `subsector` through as request
  params (server-side filtering = fewer pages fetched), and verifies
  completeness against the markers above.

### Coverage limits

- **One primary security per company.** 282 rows = 282 unique
  `company_id ↔ security_id` pairs (1:1).
- Preferred shares (e.g. MERB/MERC, BDOU), warrants, and delisted names are
  absent — from this endpoint and from `autoComplete` alike. Requesting such a
  symbol therefore warns in the scraper, and exits 1 if it was the only symbol
  requested.

## 3. Historical chart data

`POST https://edge.pse.com.ph/common/DisclosureCht.ax`

- **POST with a JSON body only** — GET returns **415**.
- The scraper sends `Referer: https://edge.pse.com.ph/companyPage/stockData.do`
  and `X-Requested-With: XMLHttpRequest` for browser parity.

### Payload

```json
{
  "cmpy_id": "123",
  "security_id": "456",
  "startDate": "08-01-2026",
  "endDate": "08-31-2026"
}
```

- Dates are **strictly `MM-DD-YYYY`** — ISO dates return **400**.
- A future `endDate` is silently capped at the latest available day.

### Response (JSON)

Two members:

- `chartData` — the price series (used by the scraper). One record per
  **trading day**, ascending by date:
  - `CHART_DATE` — e.g. `Aug 03, 2026 00:00:00` (always midnight)
  - `VALUE` — **PHP turnover, not share volume.** Verified by magnitude:
    MER 413.59M ÷ 487 close ≈ 849K shares (realistic); as a share count it
    would imply ₱201B daily turnover for one stock. **There is no volume field
    in this API.**
  - `OPEN`, `CLOSE`, `HIGH`, `LOW`
- `tableData` — disclosure notices in range (`SM_DM` timestamp +
  `SUBJECT_TITLE`, e.g. `Aug 28, 2026 03:51 PM`). Currently ignored by the
  scraper.

### Verified quirks

- **Repeated dates.** A full-history response can return the *same record*
  multiple times for a single date — observed live on BDO (4,184 records →
  4,015 unique dates; up to ~22 identical repeats on one date, 130 dates
  affected). The scraper keeps one row per date (last record wins).
- **No pagination** — the full range arrives in one response (17 years /
  4,184 records for MER).
- **History floor ≈ Aug 2009** (per MER; per-security listing dates apply).
- **~1 trading day lag** — queried Tue 2026-09-15 ~03:32 Manila, the last row
  was Fri 2026-09-11. A "sync to today" will never include today.
- **Silent failures.** A bogus `security_id`, a bogus `cmpy_id`, a mismatched
  pair, swapped start/end, or missing dates all return **200 with an empty
  `chartData`** — indistinguishable from "no data in range" without
  cross-checks. This is why the scraper keeps fixture contract tests and
  completeness verification.

## 4. Adjacent endpoints (mapped, not used)

- `GET /autoComplete/searchCompanyNameSymbol.ax?term=X` — ≤20 results; fields
  `cmpyId`, `cmpyNm`, `symbol`, `etfYn`. jQuery-style `term` parameter (not
  `keyword`). Also lists no preferred shares.
- `GET /psei/search.ax` — **disclosure search for PSEi constituents**, not
  index prices. Also has a `[Total N]` count span.
- `GET /companyDirectory/form.do` — the directory form (source of the
  filter/parameter inventory in §2).
- Company page tabs seen: `companyInformation`,
  `directors_and_management_list`, `financial_reports_view`,
  `companyDisclosures`, `announcements`, `financialReports`,
  `disclosureNotices`, `listingNotices`, `otherReports`, `marketCalendar`.

## 5. Politeness

The scraper is deliberately single-threaded and enforces a configurable delay
between requests (`--rate-limit`, default 0.6 s), retrying transient failures
(HTTP 429/5xx) with exponential backoff. A full first sync is ~5 minutes at
the default rate. Please keep it that way when changing this code — hammering
a small exchange's site is both rude and ban-prone.

---

*Verification date: 2026-09-15. When an endpoint changes, re-capture the
fixtures (see `tests/fixtures/README.md`) and update this reference.*
