"""Optional AI/ML: predictive delivery risk, recurring bottleneck detection, smart search.

Everything in this package is opt-in and inert unless
``AppSettings.ai.enabled`` is set (off by default - see
:class:`app.config.settings.AiSettings`). The deterministic system built in
Phases 1-8 does not depend on anything here; disabling AI removes a sidebar
page and nothing else stops working (spec rule 29).

A prediction from this package is always labeled "Predicted Risk" and is
never written into - or allowed to silently influence - the actual
manufacturing fields (`CustomerOrderLine.status`, due dates, quantities) that
the rest of the app treats as ground truth (spec rule 28). Nothing here
requires a network call or a cloud service; the risk model is a small
pure-Python logistic regression trained on this database's own history, and
smart search is a deterministic keyword parser - no external LLM dependency.
"""
