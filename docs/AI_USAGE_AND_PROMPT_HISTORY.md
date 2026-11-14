# AI Usage Disclosure and Prompt History

## 1. Purpose

This document discloses the use of large language models (LLMs) during development of the Warehouse Risk Monitor challenge submission.

AI tools were used as development assistants. They were not treated as substitutes for executing the application, reviewing the repository, or validating results.

## 2. Areas Where AI Assisted

The AI-assisted workflow covered these categories:

1. Understanding and decomposing the warehouse-monitoring challenge.
2. Planning implementation phases and dependencies.
3. Designing synthetic data generation and relational data workflows.
4. Developing and reviewing database validation logic.
5. Designing anomaly, alarm and inventory traceability checks.
6. Preparing automated validation and test commands.
7. Diagnosing test failures and interpreting command output.
8. Improving documentation and submission readiness.

## 3. Representative Prompt History

The following are representative prompt topics from the development workflow. They are categorized summaries, not a claim that they reproduce every original prompt verbatim.

| Area | Representative prompt / request | AI contribution |
|---|---|---|
| Project planning | Break the warehouse risk monitoring challenge into implementation phases. | Helped structure the work into manageable phases. |
| Database | Implement and validate the warehouse relational database and its entity relationships. | Assisted with schema and integrity review. |
| Synthetic data | Generate the required warehouse, zone, sensor, reading and inventory volumes with a fixed seed. | Assisted with generation logic and validation planning. |
| Edge cases | Add labelled incompatible-zone, sensor-assignment, reading-gap and alarm-link exceptions. | Assisted with exception design and checks. |
| Traceability | Build links between alarms, affected inventory lots, inspections and remediation. | Assisted with relationship and reconciliation logic. |
| Testing | Run the test suite and investigate validation failures. | Helped interpret output and propose fixes. |
| Reproducibility | Verify repeated generation with the same seed. | Assisted with reproducibility checks. |
| Submission | Review README and submission compliance against the challenge guidelines. | Assisted with documentation and acceptance-check planning. |

## 4. Where AI Accelerated Development

AI assistance helped accelerate:
- Breaking a broad challenge into smaller implementation phases.
- Drafting and reviewing Python validation scripts.
- Identifying missing relationships and edge cases.
- Interpreting test and audit output.
- Preparing documentation structures.
- Creating repeatable command sequences.

## 5. Where AI Assistance Was Significant

LLM assistance was significant in planning, code drafting, debugging suggestions, validation design and documentation preparation.

The final implementation must be judged using the actual repository, executable commands, database state, test results and generated evidence.

## 6. Developer Review and Responsibility

The developer is responsible for:
- Running commands in the local project environment.
- Reviewing changes before accepting them.
- Inspecting generated files and database records.
- Running automated tests and validation scripts.
- Checking data relationships and exception outputs.
- Confirming that documentation matches actual implementation.
- Reviewing the public repository before submission.

AI-generated suggestions are not considered verified merely because they were generated.

## 7. Verification Evidence

The following evidence should be retained with the submission:

- Test execution output.
- Database integrity and foreign-key validation.
- Dataset row counts.
- Reproducibility checksums.
- Ground-truth and anomaly reports.
- Submission-readiness and final acceptance reports.
- Relevant Git commit history.

## 8. Transparency Note

This document is a categorized reconstruction of the AI-assisted workflow, not an exhaustive verbatim export of every conversation or prompt.

If a complete verbatim prompt transcript is required, the original conversation history should be exported and attached separately. No fabricated prompts or unverified claims of manual authorship are presented here.
