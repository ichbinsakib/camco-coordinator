# Assumptions Made Where the Spec Was Ambiguous

Per the master prompt's instruction not to block on every open question: each
of these is a reasonable default, and every one is reversible through
`app/config/settings.py` (`AppSettings`) without a code change unless noted.

1. **"CO" (Customer Order) vs. "SO" (Sales Order)** - modeled as two related
   but independent headers (`CustomerOrder`, `SalesOrder`), linked optionally
   at both the header and the line level, because the spec references both
   as distinct searchable identifiers (sections 13, 18) without stating
   CAMCO's exact relationship between them. If in practice every CO has
   exactly one SO (or vice versa), this is a query simplification, not a
   schema change.
2. **Customer "importance" for the priority engine** - modeled as a 1
   (strategic) to 5 (low) integer on `Customer`, since the spec asks the
   priority algorithm to consider "customer importance" (section 10) without
   defining a scale. Configurable weight in `PrioritySettings.weight_customer_importance`.
3. **Priority score thresholds and weights** - initial values in
   `PrioritySettings` are a reasonable starting point, not a validated
   model. They are the first thing to tune against real CAMCO data once the
   dashboard is in daily use; every weight and cutoff is a Settings-page
   field precisely so this doesn't require a code change.
4. **RMA "aging in months" bucketing** - implemented as 30-day months
   (`Rma.age_months()`), configurable bucket edges in
   `RmaSettings.aging_buckets_months` (default 0-1/1-3/3-6/6-12/12+, matching
   spec section 17 exactly).
5. **On-time shipment historical ranges** (spec section 16) - the spec lists
   specific ranges (current/prior month, 3/6/12/24/36/48/60 months) as
   examples of "configurable time ranges," not a fixed requirement to
   pre-build every one of them; Phase 3's shipping analytics will expose a
   date-range picker rather than a fixed dropdown of those exact bands, which
   is a superset of what's asked.
6. **Work week default** - Monday-Friday (`CalendarSettings.work_days`),
   since CAMCO's shift pattern wasn't specified; changeable in Settings
   (spec explicitly calls out Sun-Thu as a possible alternative, section 53).
7. **Timezone default** - `America/New_York` per spec section 54's explicit
   instruction, configurable.
8. **Default admin bootstrap** - since spec section 27 requires roles but
   doesn't specify a first-run provisioning flow, the app seeds one `admin`
   account with a random temporary password on first launch (logged, not
   displayed/emailed), rather than shipping a fixed default password.
9. **"Vendor performance" scoring** (`Vendor.on_time_score`) - stored as a
   nullable float refreshed by analytics (Phase 5), not computed inline on
   every read, since it aggregates historical PO data across potentially
   thousands of rows (performance, spec rule 30).
10. **Sales order as fully optional** - many shops don't run a separate SO
    number distinct from the CO; `CustomerOrderLine.sales_order_id` and
    `SalesOrder` itself are nullable/optional everywhere so the app is fully
    usable without ever creating a SalesOrder record.
11. **"Weekly Production Report" folded into existing screens** - spec
    section 23 lists this alongside the Daily Coordinator Report and others.
    Rather than build a seventh static, timestamped report that would just
    restate the live Production page, the workload-by-department chart on
    the Analytics page and the Production page itself cover the same need
    with always-current data. If a literal weekly snapshot document turns
    out to matter for an external audience (e.g. emailing production status
    to someone without app access), it's a small addition to
    `app/reports/builders.py` following the existing pattern.
