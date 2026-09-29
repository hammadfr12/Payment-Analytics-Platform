# CLAUDE CODE MASTER BUILD PROMPT
## Payment Growth Analytics Platform

You are a senior staff-level data engineer, analytics engineer, product engineer and BI engineer.

Build the complete **Payment Growth Analytics Platform** described in the attached/adjacent PRD. Treat the PRD as the source of truth.

The objective is NOT to create a fake static dashboard or a collection of screenshots. Build a real, reproducible, locally runnable analytics product using Python, SQL, Tableau-compatible outputs, an API, tests, synthetic data and documentation.

---

# 1. NON-NEGOTIABLE RULES

1. Do not fabricate completed work.
2. Do not hard-code KPI outputs.
3. Every dashboard number must originate from generated data and an actual transformation/query.
4. Use synthetic data only.
5. Clearly label all synthetic/demo data.
6. Use deterministic random seeds so results are reproducible.
7. Write clean, typed, modular Python.
8. Use SQL as a first-class analytical layer.
9. Prefer Trino-compatible SQL syntax for analytical models.
10. Use DuckDB locally where it makes the project easy to run; document any Trino/DuckDB syntax differences.
11. Use Tableau Hyper API to generate a Tableau-ready `.hyper` extract.
12. Generate Tableau workbook/data-source artifacts where technically feasible.
13. Never claim Tableau visual validation if Tableau Desktop is not installed/available.
14. If Tableau Desktop is unavailable, generate the Hyper extract plus Tableau setup instructions and workbook/template artifacts that can be validated structurally.
15. Build a Streamlit reference application so the full product can be demonstrated locally without Tableau.
16. Build a FastAPI service exposing reusable metrics.
17. Add automated tests.
18. Add data-quality tests.
19. Add documentation.
20. Do not use real payment/customer/merchant data.
21. Do not put credentials in code.
22. Use `.env.example`.
23. Keep dependencies minimal and justified.
24. Run tests and fix failures before declaring completion.
25. If a requested feature cannot be implemented in the environment, implement the closest reproducible artifact and document exactly what remains manual.

---

# 2. FIRST ACTION — INSPECT THE ENVIRONMENT

Before writing code:

- Inspect the repository.
- Inspect available Python version.
- Check whether `uv`, `poetry`, `pip`, `conda`, Docker and Make are available.
- Check whether Tableau Desktop/Server tools are installed.
- Check whether Tableau Hyper API is installable.
- Check whether Java is available if any Tableau tooling needs it.
- Check whether DuckDB is available.
- Check whether Node is available. Only use Node if genuinely useful.
- Do not assume external network access.
- Do not assume a live Trino cluster exists.

Create an `ENVIRONMENT.md` documenting what is available.

---

# 3. BUILD ORDER

Build in this order:

1. Repository structure.
2. Python environment/dependencies.
3. Configuration.
4. Synthetic data generator.
5. Data validation.
6. Local analytical database.
7. SQL staging models.
8. SQL marts.
9. KPI layer.
10. Benchmarking.
11. RCA engine.
12. Opportunity engine.
13. Hyper extract.
14. FastAPI.
15. Streamlit.
16. Tableau artifacts/documentation.
17. Tests.
18. README.
19. Demo runner.
20. Final validation.

Do not build UI before the data layer is working.

---

# 4. PROJECT STRUCTURE

Create:

```text
payment-growth-analytics/
│
├── README.md
├── PRD.md
├── ENVIRONMENT.md
├── CLAUDE_CODE_BUILD_PROMPT.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── Makefile
├── docker-compose.yml
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── generated/
│
├── sql/
│   ├── staging/
│   ├── marts/
│   ├── analytics/
│   └── tests/
│
├── src/
│   ├── config/
│   ├── data_generation/
│   ├── etl/
│   ├── analytics/
│   ├── rca/
│   ├── opportunities/
│   ├── api/
│   ├── tableau/
│   └── common/
│
├── app/
│   └── streamlit/
│
├── tableau/
│   ├── extracts/
│   ├── workbooks/
│   ├── datasource/
│   └── documentation/
│
├── tests/
│   ├── unit/
│   ├── data/
│   └── integration/
│
├── docs/
│   ├── architecture.md
│   ├── data_dictionary.md
│   ├── metric_definitions.md
│   ├── rca_methodology.md
│   ├── tableau_setup.md
│   └── demo_walkthrough.md
│
└── scripts/
    ├── generate_data.py
    ├── run_pipeline.py
    ├── build_hyper.py
    └── validate_project.py
```

---

# 5. PYTHON STACK

Use Python 3.11+ if available.

Preferred libraries:

```text
pandas
numpy
pyarrow
duckdb
scipy
scikit-learn
statsmodels
pydantic
pydantic-settings
fastapi
uvicorn
sqlalchemy
trino
tableauhyperapi
plotly
streamlit
pytest
pytest-cov
faker
python-dotenv
```

Do not blindly install everything. Remove unused dependencies after implementation.

Use:

- pandas for data manipulation.
- NumPy for numerical operations.
- PyArrow for columnar data.
- DuckDB for local analytical execution.
- SciPy/statsmodels only where statistically useful.
- FastAPI for API.
- Pydantic for schemas/configuration.
- Tableau Hyper API for extract creation.
- Plotly/Streamlit for reference UI.
- pytest for testing.

---

# 6. SYNTHETIC DATA ENGINE

Build a deterministic generator.

Default scale:

- 150 merchants.
- 12 industries.
- 25 MCCs.
- 10 issuer banks.
- 5 payment methods.
- 4 device categories.
- 3 platforms.
- 10–20 error codes.
- 8–12 weeks of transaction data.
- At least 1–3 million transactions if the environment can handle it efficiently; otherwise default to 250k–500k and document the scale.

Create realistic distributions.

Industries should include examples such as:

- E-commerce
- Food Delivery
- Travel
- Fintech
- Grocery
- Fashion
- Electronics
- Quick Commerce
- Entertainment
- Healthcare
- Education
- Marketplaces

Payment methods:

- UPI
- Credit Card
- Debit Card
- Netbanking
- Wallet

Devices:

- Mobile
- Desktop
- Tablet

Platforms:

- Android
- iOS
- Web

Generate merchant-level baseline SRs and industry baselines.

Generate controlled scenarios:

### Scenario 1
A merchant experiences a 3–5 pp SR decline.

### Scenario 2
Android debit-card transactions deteriorate.

### Scenario 3
One issuer has an error spike.

### Scenario 4
A merchant consistently underperforms its industry.

### Scenario 5
A merchant has an unusually strong improvement.

These scenarios must be discoverable by the RCA/opportunity system.

---

# 7. DATABASE

Use DuckDB as the default local database.

Database file:

```text
data/processed/payment_growth.duckdb
```

Tables:

```text
raw_payment_transactions
raw_merchants
raw_checkout_events
dim_calendar
dim_error_codes
dim_payment_methods
```

Analytical tables:

```text
fct_payment_performance
fct_checkout_conversion
merchant_daily_metrics
merchant_weekly_metrics
industry_benchmarks
payment_method_metrics
rca_metrics
opportunity_candidates
```

Create indexes/partitions only where they materially help DuckDB performance.

---

# 8. SQL

Write actual `.sql` files.

Required:

```text
sql/staging/stg_transactions.sql
sql/staging/stg_merchants.sql
sql/staging/stg_checkout_events.sql

sql/marts/fct_payment_performance.sql
sql/marts/fct_checkout_conversion.sql

sql/analytics/merchant_daily_metrics.sql
sql/analytics/merchant_weekly_metrics.sql
sql/analytics/industry_benchmarks.sql
sql/analytics/payment_method_metrics.sql
sql/analytics/rca_metrics.sql
sql/analytics/opportunity_candidates.sql
```

Every SQL model must be documented.

Use explicit column lists rather than `SELECT *` in production-style transformations.

Avoid SQL that works only because of accidental implicit casts.

---

# 9. METRIC LAYER

Implement a centralized metric definition module and matching SQL.

Required:

### Success Rate

```text
authorized transactions / eligible transactions
```

### TPV

```text
SUM(amount)
```

### Transaction Count

```text
COUNT(DISTINCT transaction_id)
```

### AOV

```text
TPV / successful transaction count
```

### Failure Rate

```text
failed eligible transactions / eligible transactions
```

### Payment Method Share

```text
method TPV / total TPV
```

### Percentage-point delta

```text
current_rate - previous_rate
```

### Percentage delta

```text
(current - previous) / previous
```

Protect all denominators.

Write unit tests for every formula.

---

# 10. CHECKOUT CONVERSION

Do NOT derive checkout conversion from payment transactions.

Use the checkout event table.

Implement:

```text
checkout_started
payment_attempted
payment_success
payment_failed
```

Define:

```text
checkout conversion =
successful checkout sessions / checkout sessions started
```

Document the denominator.

---

# 11. BENCHMARK ENGINE

Benchmark a merchant against:

```text
industry + country + payment method + date range
```

Requirements:

- Minimum transaction threshold.
- Minimum merchant count.
- Exclude current merchant from peer group.
- Weighted aggregate benchmark.
- Return benchmark sample size.
- Return peer count.
- Return benchmark methodology.

Never show a benchmark as authoritative if the sample is insufficient.

Add:

```text
benchmark_status =
VALID
INSUFFICIENT_SAMPLE
NO_PEERS
```

---

# 12. RCA ENGINE

Implement current-vs-previous-period RCA.

Dimensions:

```text
payment_method
payment_type
card_type
issuer_bank
device
platform
error_category
industry
mcc
country
```

For every segment calculate:

```text
current_metric
previous_metric
delta
volume_current
volume_previous
contribution
```

The contribution methodology must be documented.

Prefer a contribution decomposition that accounts for both:

- segment volume
- segment rate movement

Do not claim causal inference.

Use language such as:

- contributor
- associated movement
- concentrated decline
- observed pattern

Avoid:

- caused by
- root cause

unless the evidence actually supports causality.

---

# 13. OPPORTUNITY ENGINE

Create a transparent rules engine.

Rules:

### RULE_SR_DECLINE

Trigger if:

```text
SR delta <= -1.5 pp
AND transaction_count >= minimum_threshold
```

### RULE_BENCHMARK_GAP

Trigger if:

```text
merchant_sr <= benchmark_sr - 2 pp
AND benchmark_status = VALID
```

### RULE_ERROR_SPIKE

Trigger if an error category increases beyond configured threshold.

### RULE_CONCENTRATED_SEGMENT

Trigger if a segment explains a meaningful share of observed decline.

Every generated opportunity needs:

```text
opportunity_id
merchant_id
opportunity_type
severity
metric
current_value
previous_value
benchmark_value
delta
gap
affected_volume
primary_dimension
supporting_evidence
recommended_next_step
confidence
created_at
```

The confidence field should represent evidence quality, not causal certainty.

---

# 14. FASTAPI

Build:

```text
GET /health

GET /metrics/overview
GET /metrics/merchant/{merchant_id}
GET /metrics/trend
GET /metrics/payment-method
GET /metrics/rca

GET /benchmarks/merchant/{merchant_id}

GET /opportunities
GET /opportunities/{opportunity_id}
```

Add query validation.

Example:

```text
/metrics/merchant/M001?start_date=2026-08-01&end_date=2026-08-31
```

Use Pydantic response models.

Add proper HTTP errors.

Add OpenAPI documentation.

---

# 15. STREAMLIT

Build a polished internal analytics application.

Pages/tabs:

```text
Overview
Merchant Performance
Benchmarking
RCA Explorer
Opportunity Center
Data Quality
```

Overview:

- KPI cards.
- Trend chart.
- Benchmark chart.
- Top opportunities.

Merchant page:

- Search/select merchant.
- KPI cards.
- Trend.
- Payment-method table.
- Device/platform breakdown.

Benchmarking:

- Merchant SR.
- Industry benchmark.
- Gap.
- Peer count.
- Sample size.

RCA:

- Current vs previous.
- Contribution chart.
- Drilldown filters.

Opportunity Center:

- Filter by severity/type/industry.
- Opportunity cards.
- Evidence.
- Next step.

Data Quality:

- Record counts.
- Invalid records.
- Missing values.
- Pipeline status.

Use Plotly.

Do not hard-code demo values.

---

# 16. TABLEAU

This is a major requirement.

Create a Tableau Hyper extract using:

```python
tableauhyperapi
```

Create:

```text
tableau/extracts/payment_growth.hyper
```

Create a documented Tableau datasource.

Required logical datasets:

```text
Merchant Performance
Industry Benchmark
RCA
Opportunities
Checkout Conversion
```

If Tableau workbook generation is feasible, create a `.twb`.

If Tableau Desktop is available, validate the workbook.

If not available:

- Build the Hyper.
- Build workbook/source artifacts where possible.
- Create `tableau/documentation/tableau_setup.md`.
- Include exact steps to connect Hyper to Tableau.
- Document all calculated fields, filters, dashboard actions and sheets that should be created.
- Never state "Tableau dashboard validated" without actually opening/validating it.

Tableau dashboards:

### 1. Executive Overview

Filters:
- Date
- Merchant
- Industry
- MCC
- Payment method
- Country
- Device
- Platform

KPI cards:
- SR
- TPV
- Transactions
- AOV
- Checkout conversion

Charts:
- SR trend
- TPV trend
- payment-method mix
- merchant vs benchmark
- opportunities

### 2. Merchant Performance

### 3. Industry Benchmarking

### 4. RCA Explorer

### 5. Opportunity Center

Include tooltips explaining KPI definitions.

---

# 17. TABLEAU CALCULATED FIELDS

Where appropriate create documented calculated fields such as:

```text
SR %
AOV
Failure Rate %
Payment Method Share %
SR Delta pp
SR WoW %
Benchmark Gap pp
```

Do not duplicate business logic unnecessarily between SQL and Tableau.

Prefer SQL/precomputed metrics for complex logic.

Use Tableau primarily for:

- presentation
- filtering
- interaction
- visualization
- lightweight calculations

---

# 18. TESTING

Build extensive tests.

Unit tests:

```text
test_success_rate
test_aov
test_tpv
test_share
test_pp_delta
test_percentage_delta
test_benchmark
test_rca
test_opportunity_rules
```

Data tests:

```text
transaction_id uniqueness
merchant referential integrity
valid payment methods
valid amounts
valid dates
valid status values
no impossible timestamps
```

Integration test:

```text
generate data
→ load DuckDB
→ run SQL
→ calculate analytics
→ build Hyper
→ call API
```

Regression test:

The known degraded synthetic merchant must be detected.

Example expected behavior:

```text
Merchant: NOVA_FASHION

SR decline:
>= 3 pp

Primary contributing segment:
Android + Debit Card

Benchmark:
Merchant below industry benchmark
```

Do not assert exact floating-point values unless necessary; use reasonable tolerances.

---

# 19. CLI / MAKE COMMANDS

Implement:

```bash
make setup
make generate-data
make load-data
make run-sql
make run-pipeline
make build-hyper
make test
make lint
make run-api
make run-app
make validate
make demo
```

`make demo` should run the essential pipeline and print:

```text
DATA GENERATED
PIPELINE COMPLETE
TABLES CREATED
HYPER CREATED
TESTS PASSED
API READY
STREAMLIT READY
```

Do not print success unless the command actually succeeded.

---

# 20. DOCUMENTATION

README must contain:

1. Product overview.
2. Architecture.
3. Setup.
4. Data generation.
5. SQL pipeline.
6. KPI definitions.
7. Benchmark methodology.
8. RCA methodology.
9. Opportunity engine.
10. Tableau setup.
11. API usage.
12. Streamlit usage.
13. Testing.
14. Known limitations.
15. Synthetic-data disclaimer.

Create architecture diagrams using Mermaid where helpful.

---

# 21. DATA DICTIONARY

Create a complete data dictionary.

For every important field include:

```text
field
table
type
description
nullable
example
```

For every KPI include:

```text
metric
definition
numerator
denominator
grain
filters
edge cases
```

---

# 22. PERFORMANCE

The project should comfortably run on a developer laptop.

Use:

- Parquet where useful.
- DuckDB.
- Vectorized pandas.
- Avoid Python loops over millions of transactions.
- Batch generation.
- Efficient SQL.
- Cache expensive Streamlit queries.

---

# 23. QUALITY BAR

The final repository should look like a serious analytics/product engineering project.

Avoid:

- giant scripts.
- duplicated logic.
- hard-coded outputs.
- fake charts.
- fake API responses.
- placeholder TODOs for core functionality.
- undocumented magic thresholds.
- excessive dependencies.
- credentials.
- production customer data.

Prefer:

- modular architecture.
- typed functions.
- clear naming.
- tests.
- reproducibility.
- explainable metrics.
- useful comments.
- meaningful commit-ready structure.

---

# 24. FINAL VALIDATION

Before finishing, execute:

```bash
make validate
make test
```

Then manually verify:

1. Data generated.
2. DuckDB database exists.
3. SQL tables populated.
4. KPI numbers are non-null and sensible.
5. Benchmark records have valid sample sizes.
6. RCA identifies the intentionally degraded scenario.
7. Opportunities are generated.
8. Hyper file exists.
9. FastAPI health endpoint works.
10. Streamlit starts.
11. Documentation exists.
12. No secrets are present.
13. No real customer data exists.
14. Tests pass.

Then produce a final `BUILD_REPORT.md` containing:

```text
Environment
Files created
Commands executed
Tests passed
Tables created
API endpoints
Tableau artifacts
Known limitations
Manual Tableau steps
```

Do not say "complete" until the validation commands have actually passed.

---

# 25. PRODUCT DEMO NARRATIVE

Create a demo scenario around one synthetic merchant.

The narrative should be:

```text
Merchant performance dropped
        ↓
SR declined 3.2 pp
        ↓
Merchant is 3.6 pp below benchmark
        ↓
RCA identifies concentrated movement
        ↓
Android + Debit Card is a major contributor
        ↓
Issuer/error pattern is elevated
        ↓
Opportunity is created
        ↓
Recommended next investigation is displayed
```

The demo should make it obvious that this is a **decision-support product**, not merely a dashboard.

---

# 26. IMPORTANT: USE THE PRD AS THE SOURCE OF TRUTH

Read `PRD.md` before implementation.

Where this prompt and PRD conflict, use the more specific requirement and document the decision.

Do not simplify the project into only a Streamlit dashboard.

The final implementation must demonstrate:

**Python + SQL + Data Engineering + Analytics + RCA + Benchmarking + Tableau + API + Testing + Product Thinking.**

Start by inspecting the environment and repository, then build the project incrementally.
