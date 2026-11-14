# Architecture, Assumptions and Engineering Decisions

## Architecture

The project follows a relational data-processing workflow:

1. Master data creation.
2. Dependent event generation.
3. Inventory and storage requirement association.
4. Risk-rule evaluation.
5. Alarm creation.
6. Inspection and remediation workflows.
7. Inventory-impact traceability.
8. Validation and reporting.

## Core Decisions

| Decision | Reason |
|---|---|
| Relational database | Supports explicit relationships and referential integrity. |
| Synthetic data | Enables controlled scenarios without relying on confidential operational data. |
| Fixed seed | Supports reproducible generation. |
| Deterministic identifiers | Makes joins and audit trails easier to verify. |
| Separate ground truth | Avoids leaking expected anomaly labels into operational input features. |
| Explicit event records | Preserves operational history and traceability. |
| Validation scripts | Makes data quality and acceptance evidence repeatable. |

## Assumptions

- Warehouse and zone identifiers are stable.
- Sensor readings are timestamped.
- Storage requirements are evaluated against inventory and storage context.
- Affected inventory is determined from relevant time and zone overlap.
- Missing readings and incomplete associations must be visible exceptions.
- Risk thresholds must be documented and consistently applied.

## Trade-offs

- SQLite simplifies local execution but is not a substitute for a distributed production database.
- Synthetic data improves repeatability but cannot represent every real warehouse operating condition.
- Rule-based detection is explainable but may require tuning for real industrial environments.
- Full-scale generation and validation can require significant local execution time.

## Limitations

This challenge implementation does not claim certified industrial control, safety-critical operation, or live OT integration.

Actual implementation details should be verified against source code and database schema.
