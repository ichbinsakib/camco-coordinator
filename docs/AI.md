# AI / Machine Learning (Phase 9)

Off by default (`AppSettings.ai.enabled = False`). With it off, nothing
changes anywhere else in the app - no sidebar entry, no extra page, no
background work. Turn it on from Settings > AI. Nothing here calls out to
the network or a cloud service; everything trains and runs locally against
this database's own history.

## The rule that shapes everything in `app/ai/`

> AI predictions must NEVER silently replace actual manufacturing data.
> Always distinguish Actual Status from Predicted Risk.

Concretely: the AI Insights page always shows a line's real `status` column
next to its `Predicted Risk` column, never one *instead of* the other; no
code path in `app/ai/` writes to `CustomerOrderLine.status`, a due date, a
quantity, or any other field the rest of the app treats as ground truth.
`DeliveryRiskResult` is a value object that gets displayed and discarded -
it isn't persisted onto the order line itself.

## Delivery Risk (`app/ai/risk_model.py`)

Predicts, for each open customer order line, how likely it is to ship late.
Two blended components:

1. **A learned base rate.** A small logistic regression
   (`app/ai/logistic_model.py`, hand-rolled in ~140 lines of pure Python -
   no numpy/scikit-learn, see that module's docstring for why) trained on
   this database's own historical **shipped** order lines. Label: did the
   line's shipment go out after its due date. Features: customer
   importance, log-scaled quantity, and whether the due date was ever
   pushed out from its original value.
2. **A real-time rule-based adjustment**, added on top, using exactly the
   kind of signal the alert/priority engines already compute: currently
   blocked on material, a production operation stuck 10+ days, a linked PO
   already late, or the line itself already past due.

**Why the split, and a known limitation worth stating plainly:** the
database doesn't store point-in-time snapshots (what a line's status was
three weeks before it shipped) - only final state. That makes "was this
line ever blocked on material" fundamentally unlearnable from historical
data (every shipped line's final status is SHIPPED, never WAITING
MATERIAL). So the learned model only uses features that are genuinely
knowable from a closed line's static attributes, and the real-time,
rule-based half covers exactly the live-status information the model
structurally can't learn. This is a deliberate, documented design choice,
not an oversight - see assumption #12 in `docs/ASSUMPTIONS.md`.

Below 20 labeled historical examples, the learned component is skipped
entirely and the result is honestly labeled "scored using live status
only" - never a confident-looking number backed by too little data.

Train (or retrain, as more shipments accumulate) from the AI Insights page's
Delivery Risk tab. The trained model is a small JSON file under
`%LOCALAPPDATA%\CAMCO Coordinator\ai\delivery_risk_model.json`.

## Recurring Bottleneck Detection (`app/ai/bottleneck_model.py`)

Deterministic historical statistics, not a learned model - the question
("which operation is recurringly slow") is fully answered by averaging
actual `start_date` -> `actual_completion_date` durations per operation
name across every completed operation in the database, so there's no case
for reaching past that (rule 63: "do we really need this?" - here, no).
Complements the existing live "what's stuck right now" view
(`app/repositories/analytics.py`'s `bottleneck_operations`) with "what's
*historically* been slow, even when nothing is stuck on it today."

## Smart Search (`app/ai/smart_search.py`)

A deterministic keyword parser, not an LLM. The spec's own examples
("Which parts are waiting for material?", "Which POs are overdue?") are
exactly the fixed-vocabulary kind of query a rule set handles well, and a
rule set adds no dependency weight, no latency, and no hallucination risk.
Every query result comes back with a plain-English "interpreted this as..."
line, so the mapping from words to filters is never a black box. Supports:
late/overdue, waiting-on-material, this-month/this-week/today date ranges,
and routes to customer orders, purchase orders, RMAs, or follow-ups based
on keywords - plus one AI-flavored query ("likely to be late"), which pulls
in the Delivery Risk model's HIGH/CRITICAL results.

`AiSettings.provider`/`endpoint`/`model` exist in settings as the seam for
a future local-LLM-backed parser (Ollama, per spec section 29) that could
replace or augment the keyword rules for more flexible phrasing - not built
in this phase, since the deterministic parser already covers the spec's
stated examples without that dependency.

## Testing

24 tests: 5 for the logistic regression (learns a separable relationship,
deterministic given the same input, handles zero-variance features without
dividing by zero), 3 for the smart-search date/keyword helpers, 7 for the
risk model (training-label correctness, the minimum-sample-count fallback,
rule-based-only scoring, sort order), 4 for bottleneck detection, and 5 for
smart search routing end-to-end against a real database. Verified further
with a full-app smoke test: AI correctly absent from the sidebar when
disabled, correctly present and fully functional (train -> score -> search)
when enabled, against realistically seeded historical and open data.
