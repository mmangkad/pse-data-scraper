# PSE EDGE API Notes

This project uses the same endpoints that the PSE EDGE website calls from the browser.
These endpoints are undocumented and may change without notice.

## Company Directory

Endpoint:

- `GET https://edge.pse.com.ph/companyDirectory/search.ax?pageNo={page}`

Notes:

- The response is HTML.
- Company rows are in `table.list tbody tr`.
- The company and security IDs are embedded in the `onclick` handler:
  - `cmDetail('COMPANY_ID','SECURITY_ID')`

## Historical Stock Data

Endpoint:

- `POST https://edge.pse.com.ph/common/DisclosureCht.ax`

Headers:

- `Referer: https://edge.pse.com.ph/companyPage/stockData.do`
- `X-Requested-With: XMLHttpRequest`

JSON payload:

```json
{
  "cmpy_id": "123",
  "security_id": "456",
  "startDate": "01-01-1900",
  "endDate": "08-30-2024"
}
```

Response (JSON):

- `chartData`: list of daily records

Record fields used:

- `CHART_DATE` (example: `Aug 30, 2024 00:00:00`)
- `VALUE`
- `OPEN`
- `CLOSE`
- `HIGH`
- `LOW`

## Rate Limiting

The scraper enforces a configurable delay between requests (`--rate-limit`) and retries
transient failures (HTTP 429/5xx) with exponential backoff.
