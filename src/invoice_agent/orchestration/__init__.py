"""Agent orchestration (Task 7).

A LangGraph state machine wiring the pipeline into one agentic flow:

    ingest → extract → match → (post | escalate) → audit

The node *logic* lives in :mod:`.nodes` as plain, injectable functions so it is
unit-testable without LangGraph; :mod:`.graph` assembles them into the compiled
LangGraph app (imported lazily — heavy dependency, Python ≤3.12).
"""
