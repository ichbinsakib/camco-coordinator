# Database Schema (Phase 1)

All tables live under `app/models/`. Every business table inherits
`AuditedBase` (`created_at`, `updated_at`, `created_by_id`, `updated_by_id`);
cross-cutting tables (`notes`, `activity_log`, `alerts`, `import_batches`)
use lighter mixins since they are themselves the audit trail.

## Entity relationship overview

```
Customer ──< CustomerOrder ──< CustomerOrderLine >── Part
                                     │      │
                                     │      └──< PurchaseOrderLine (optional link)
                                     │      └──< ProductionOrder ──< ProductionOperation
                                     │      └──< ShipmentLine >── Shipment
                                     │      └──< Rma
                              SalesOrder (optional)

Vendor ──< PurchaseOrder ──< PurchaseOrderLine
Customer ──< Rma
FollowUp  -> optionally references Part / CustomerOrder / SalesOrder /
             PurchaseOrder / Vendor / Customer / User (all nullable FKs)
Note, ActivityLogEntry, Alert -> polymorphic (entity_type, entity_id)
```

## Tables

| Table | Purpose | Key fields |
|---|---|---|
| `users` | Local accounts / roles | `username`, `role`, `password_hash` |
| `customers` | Customer master | `code`, `importance` (1=strategic..5=low) |
| `vendors` | Vendor master | `code`, `on_time_score` |
| `parts` | Centralized part record | `part_number` + `revision` (natural key) |
| `customer_orders` | CO header | `co_number`, `customer_id` |
| `sales_orders` | SO header (optional) | `so_number` |
| `customer_order_lines` | Demand line - the core coordination row | `quantity_ordered/completed`, `due_date`, `status` |
| `production_orders` | Shop work order for one CO line | `production_number` |
| `production_operations` | Routing step (OP10, OP20...) | `sequence`, `status`, `status_since` |
| `purchase_orders` | PO header | `po_number`, `vendor_id` |
| `purchase_order_lines` | Material commitment | `required_date`, `promised_date`, `status` |
| `shipments` / `shipment_lines` | Outbound fulfilment | `ship_date`, `tracking_number` |
| `rmas` | Return/quality case | `date_received`, `status`, aging computed in months |
| `follow_ups` | Manual coordination tasks | `due_date`, `next_followup_date`, `status` |
| `notes` | Free-text notes on any entity | `entity_type`, `entity_id` |
| `activity_log` | Append-only change history | never updated or deleted by app code |
| `alerts` | System-generated attention items | `rule_code`, `severity`, `status` |
| `import_batches` / `import_row_errors` | Excel/CSV import audit trail | Phase 6 |

## Derived values (never stored as plain columns)

- **Days late / days until due** - `CustomerOrderLine.days_late()` /
  `.days_until_due()`. Closed statuses (COMPLETE, SHIPPED, CANCELLED) always
  return 0 days late, regardless of due date - a completed order does not
  keep "aging."
- **Quantity remaining** - `quantity_ordered - quantity_completed`, clamped
  at zero so an over-completion (rework replacing scrap) can't show negative
  remaining.
- **RMA age** - reported in months (`Rma.age_months()`), per the spec's
  explicit instruction (rule 17) not to report RMA aging only in days.
- **Priority** - never stored on the order line except as an optional
  `manual_priority` override; the effective priority is always computed by
  `app.business.priority.compute_line_priority` at read time from current
  data, so it can never drift out of sync with the order's actual state.

## Migrations

Alembic is a listed dependency and `alembic/` will be initialized in Phase 2
once the schema stabilizes past first use. Until then, `init_database()`
uses `Base.metadata.create_all`, which is additive-only and safe to run
against an existing database - it will not touch or drop a table it already
finds.
