# AI Usage Disclosure and Prompt-History Guidance

## Disclosure

LLM-based assistance was used during development for challenge decomposition, architecture and data-model discussion, code drafting/review, debugging suggestions, test and validator design, and documentation. The developer remains responsible for reviewing the source, executing the project, understanding its behavior, and validating the submission.

## Representative categories of assistance

| Work area | Representative request category | How assistance was used |
|---|---|---|
| Planning | Decompose the warehouse monitoring challenge into deliverables and implementation phases. | Organizing dependencies and acceptance criteria. |
| Database | Review schema relationships, constraints and data integrity. | Discussing relational design and audit queries. |
| Generation | Create repeatable synthetic warehouse, sensor, event and inventory data. | Drafting generator logic and seed strategy. |
| Detection | Implement environmental and operational anomaly detection. | Reviewing rule logic and edge cases. |
| Traceability | Link alarms to exposed lots and subsequent inspections/remediation. | Designing association checks and reporting. |
| Validation | Diagnose failures and design comprehensive checks. | Interpreting command output and proposing tests. |
| Submission | Improve project documentation and final readiness evidence. | Drafting documentation and checklists. |

These are categorized summaries, not verbatim quotations of every prompt.

## Prompt-history integrity

This document is a transparent summary of the AI-assisted workflow, not an exhaustive transcript. It must not be presented as a complete or verbatim prompt history. Where a submission evaluator requires exact prompts, export the relevant original ChatGPT conversation(s) from the account's data export and attach the unedited export or the requested conversation excerpts. Do not reconstruct missing messages from memory, invent prompt text, or imply that a categorized summary is a raw transcript.

## Human review and accountability

The developer must independently:

- Run the application and commands in the target environment.
- Review and understand all accepted code changes.
- Verify generated database records, outputs and anomaly evidence.
- Run tests, database integrity checks and both scale profiles.
- Review the final Git diff and submission package.
- Disclose remaining failures or limitations rather than claiming unverified success.

AI-generated code or suggestions are not evidence of correctness until executed and checked.

## Evidence to retain

Retain the exact commands, test output, database integrity and business-rule reports, starter/full execution report, per-table reproducibility hashes, ground-truth artifacts, and relevant commit history. A report certifies only the tests and profiles it actually ran.
