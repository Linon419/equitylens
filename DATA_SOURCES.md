# Data-source and authorization boundary

This document defines the intended use, persistence, and release gate for each
data class processed by EquityLens.

| Data class | Source and intended use | Stored form | Release boundary |
|---|---|---|---|
| Company identity, filings, and financial facts | SEC EDGAR automated-access endpoints, requested with an identifying `SEC_USER_AGENT` | Filing artifacts, bounded filing sections, normalized Company Facts, citations | Follow the SEC automated-access policy and preserve SEC source URLs |
| Evaluation market data | Values generated locally by `SyntheticMarketDataProvider`; public identifiers and names plus hand-authored coarse categories form the catalog | Snapshots labeled `synthetic-evaluation-v1` | Approved for demos, tests, and hackathon judging; every numeric market value and profile description is fabricated |
| Yahoo market data | Yahoo pages accessed through the optional `yfinance` adapter for local research | Compact cached quote/profile snapshots | Requires a separate Yahoo data-license review before any public or commercial deployment |
| Official company and regulator pages | Pages selected during an Agent run and fetched through the configured web-search provider | Content-addressed private artifact, bounded excerpt, source URL, timestamps, source tier | Preserve attribution and provider terms; distribute citations and bounded excerpts |
| User research conversations | Questions, selected page context, generated answers, and citation bindings | Database records and private evidence artifacts | Guest records have a seven-day retention path; authenticated records follow account lifecycle controls |
| Test fixtures | Public SEC samples, fabricated Yahoo-shaped mapper payloads, and fabricated research outputs | Checked-in JSON, HTML, and Python fixtures | Test-only; fixture conclusions and market values carry no investment meaning |

## Evaluation profile

Set `MARKET_DATA_PROVIDER=synthetic` in the API environment. This selection:

1. routes company search, profiles, and market snapshots to local deterministic
   generation;
2. labels returned market snapshots `synthetic-evaluation-v1` in the API and UI;
3. disables direct Yahoo / `yfinance` collection in the research-chat evidence
   pipeline;
4. keeps SEC EDGAR and configured model/web providers available under their own
   access policies and credentials.

Set `MARKET_DATA_PROVIDER=yahoo` only for the documented local research profile.
Review the [Yahoo Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html)
and [Yahoo Developer Network Guidelines](https://legal.yahoo.com/us/en/yahoo/guidelines/ydn/index.html)
before expanding that profile's deployment scope.
