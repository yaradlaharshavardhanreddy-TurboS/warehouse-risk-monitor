# Phase 7 automated tests

## Included tests

- `test_database.py`: creates an isolated database from the project's actual schema and checks core schema integrity.
- `test_analytics.py`: exercises all six Phase 6 analytics functions against an empty isolated database, including zero-record completion-rate handling.
- `test_service_imports.py`: verifies that the existing Phase 5 service modules can be imported.
- `conftest.py`: provides a temporary SQLite database fixture. It does not use `data/warehouse_monitor.db`.

## Run

Activate the project's virtual environment, then run:

```bash
python -m pytest tests -v
```

## Scope and limitation

These are a safe baseline test suite, not a claim that every Phase 5 workflow is fully tested.
Alarm lifecycle, inspection, remediation, environmental detector behavior, operational detector behavior, and generator behavior need tests tailored to their actual function interfaces and required table columns. Those tests should be added after reviewing the complete source files. The production/generated database is never used by this fixture.
