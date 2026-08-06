"""Delivery domain — ``delivery_run`` and ``project_stage`` persistence.

Provides the one-current-run and per-stage ORM models defined in database
design 1.1, sections 8.2 and 9.1.  State transitions, worker claiming,
and stage scheduling belong to the Delivery Control Module in Phase 3.
"""
