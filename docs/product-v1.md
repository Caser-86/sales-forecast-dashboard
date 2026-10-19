# Sales Forecast Dashboard V1 Product Contract

Status: Frozen for implementation on 2026-09-15

## 1. Product Positioning

V1 is a single-tenant, single-deployment retail demand forecasting and replenishment assistant.

It helps an operator answer three questions:

1. What demand is expected for a product at a store during the supported forecast horizon?
2. Which products or store-product combinations need attention first, and why?
3. What replenishment quantity is suggested under the configured inventory policy?

The final purchasing decision remains with a human operator. V1 does not place orders automatically.

The product may run with generated data in demo mode, but every screen and API response must identify demo data as demo data. Generated-data metrics cannot be presented as evidence of real business performance.

## 2. In Scope

### 2.1 Data sources

- A validated sales dataset imported from CSV.
- A validated inventory snapshot imported from CSV.
- A versioned product and store catalog derived from the active dataset.
- A versioned calendar/promotion input when those features are used by the model.
- Generated data only as a reproducible development/demo source.

### 2.2 User capabilities

- Select all or a valid product/store scope.
- View historical demand and forecast demand with explicit units and date ranges.
- View model, baseline, data version, model version, and freshness metadata.
- View product/category summaries and ABC priority under one documented population definition.
- View replenishment inputs, formula breakdown, and suggested quantity.
- Save a replenishment draft, reopen it after restart, and export it for human review.
- See loading, empty, stale, partial-failure, unavailable, and retry states.

### 2.3 Supported operating model

- One active dataset version at a time.
- One active model package at a time, with the previous package retained for rollback.
- Manual import, training, validation, and activation commands.
- One service instance for V1. Horizontal scaling and distributed coordination are out of scope.
- SQLite is acceptable for replenishment drafts; sales and model artifacts remain versioned files until a later product decision.

## 3. Domain Definitions

### 3.1 Units and money

- `sales` and `forecast_sales` are quantities in units, not money.
- A monetary metric is only shown when it is explicitly calculated as `quantity * unit_price` and labeled with its currency.
- A quantity metric must use words such as `销量`, `需求量`, or `件数`; it must not be labeled `销售额`.

### 3.2 Time windows

- The reference date is the latest valid date in the active dataset unless a request explicitly supplies another supported as-of date.
- `historical_30d` means the inclusive 30 calendar days ending at the reference date.
- `forecast_30d` means the next 30 calendar days after the reference date.
- Every aggregate response must expose the window start, window end, and source dataset version.
- A comparison is valid only when actuals, predictions, and baselines use the same origin set, horizon, scope, and eligible sample keys.

### 3.3 Forecasting

- The supported production horizon is 30 days for V1.
- A product/store pair with insufficient history is unavailable, not zero demand.
- The published model may be an ensemble, LightGBM, LSTM, or seasonal baseline. Selection is based on the same-origin backtest, not on model complexity.
- Future features use only information known at the forecast origin plus explicitly documented assumptions. Future actual sales must never be used during recursive prediction.
- An interval is called a statistical prediction interval only when its calibration target, empirical coverage, sample size, and calibration window are reported. Otherwise it is called an `情景范围` or omitted.
- Statistical interval calibration is explicitly out of scope for V1; V1 uses the documented `情景范围` path until a reviewed calibration dataset and release requirement exist.

### 3.4 ABC priority

- ABC is a demand-priority classification, not a stockout-risk classification.
- V1 uses one documented population for a result: product-level across the selected business population, or product-store-level when explicitly requested.
- The class population is fixed before applying a UI filter so an item's class does not silently change because the screen was filtered.
- Default thresholds are A through 70% cumulative demand and B through 90% cumulative demand. The highest-demand item is always A so a one-item population remains actionable; subsequent items use cumulative demand after the current item, with threshold boundaries covered by tests.
- An all-zero or empty population is `C` for every present item, but the UI must not interpret this as low stock risk.

### 3.5 Replenishment

V1 uses a transparent policy formula, not a fixed forecast multiplier:

```text
net_available = on_hand + confirmed_inbound - reserved
target_stock = demand_during_lead_time_and_review_window + safety_stock
raw_replenishment = max(0, target_stock - net_available)
suggested_quantity = round_up_to_pack_size(raw_replenishment, pack_size, minimum_order_quantity)
```

Rules:

- `lead_time_days`, `review_period_days`, `safety_stock`, `pack_size`, and `minimum_order_quantity` are explicit inputs or policy values.
- If a required input is missing or stale, the suggestion is unavailable and explains which input is missing.
- If the lead-time and review window exceeds the supported forecast horizon, the system refuses to calculate instead of silently truncating the window.
- ABC can sort attention but cannot replace on-hand, inbound, reserved, or lead-time data.
- V1 saves a draft only. It does not call an ERP, WMS, supplier, or ordering endpoint.

## 4. Data Contract

### 4.1 Required sales fields

`date`, `product_id`, `store_id`, `product_name`, `store_name`, `category`, `sales`, and `price`.

Optional model inputs must be declared in the dataset manifest. Dates are calendar dates; IDs are positive integers; numeric values must be finite. The `(date, product_id, store_id)` key must be unique in a validated dataset.

Negative sales require an explicit returns policy. They must not be silently converted to zero.

### 4.2 Required inventory fields

`as_of_date`, `product_id`, `store_id`, `on_hand`, `confirmed_inbound`, `reserved`, `lead_time_days`, `review_period_days`, `safety_stock`, `pack_size`, and `minimum_order_quantity`.

Inventory timestamps and policy version are part of the saved replenishment snapshot.

### 4.3 Dataset lifecycle

1. Validate the candidate file without changing the active dataset.
2. Write it to a new immutable `dataset_id`.
3. Generate a manifest containing schema, date range, row count, source label, checksum, and validation result.
4. Activate only after validation and compatibility checks pass.
5. Keep the previous active version for rollback.

## 5. API Contract Principles

- `200` means the requested representation is usable and complete for the stated scope.
- `206` is not required; partial responses use `200` with explicit `status: "partial"`, `requested`, `succeeded`, and `failed` fields.
- All requested combinations failing returns `503` with a stable error code.
- Invalid syntax or values return `422`; unknown product/store returns `404`.
- Missing or invalid model/data readiness returns `503`, while process liveness may remain `200`.
- Errors include a request ID and stable machine-readable code; internal filesystem paths and raw exception details are not returned in production.
- Responses expose `data_version`, `model_version`, `as_of_date`, and relevant window metadata when the result depends on them.

## 6. Explicitly Out Of Scope

- Automatic purchase-order creation or external order submission.
- ERP/WMS real-time synchronization.
- Multi-tenant isolation, SSO, organization roles, and approval workflows.
- Chatbot, LLM, Agent, RAG, vector database, or tool-calling layer.
- Microservices, event bus, distributed cache, Kubernetes, or a model registry product.
- Automatic retraining, automatic model activation, or unreviewed production rollback.
- Mobile-native application.

## 7. Product Success Criteria

V1 is ready for release only when:

- An operator can import valid data, see the data/model versions, inspect a forecast, understand its units and dates, calculate a transparent replenishment suggestion, save a draft, restart the service, reopen the draft, and export it.
- Invalid or incomplete inputs are rejected without replacing the active version.
- Forecast and baseline metrics are from the same-origin 30-day evaluation protocol, or the UI clearly labels a metric as a different diagnostic.
- A failed dependency, partial prediction, stale dataset, or stale inventory snapshot is visible and actionable.
- No P0/P1 issue remains open and the acceptance matrix is backed by repeatable command or test evidence.
