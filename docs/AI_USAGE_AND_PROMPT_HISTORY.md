# AI Usage and Prompt History

## 1. Summary

This project, **Warehouse Risk Monitor**, was developed with assistance from AI tools as part of the YottaFlex.ai Associate AI Forward Deployed Engineer Round 2 Code Challenge.

The AI tools used during development were:

- **ChatGPT:** Used primarily for code generation, implementation guidance, debugging, SQL and Python scripting, documentation, validation logic, and troubleshooting.
- **Claude:** Used as a second AI assistant for review, planning, and checking outputs. Its role was supplementary to the implementation and verification work.

### What AI assisted with

AI assistance was used to:

- Plan the project structure and implementation phases.
- Generate and revise Flask application components.
- Draft SQLite schema definitions and synthetic data generators.
- Develop risk detection, alarm lifecycle, inspection, and remediation scripts.
- Design anomaly injection and ground-truth recording logic.
- Develop CSV export and reproducibility checks.
- Create validation scripts and data dictionary documentation.
- Review errors, interpret test outputs, and suggest corrections.
- Improve the README and submission documentation.

### What I did

I remained responsible for the project and its submitted results. My work included:

- Running the generated scripts in my local development environment.
- Inspecting database contents, table structures, relationships, and generated records.
- Reviewing the output of AI-generated code before accepting changes.
- Creating and preserving database backups before potentially destructive operations.
- Rejecting or cancelling changes when their results did not match the intended data distribution.
- Comparing generated outputs against the actual project database.
- Running validation commands and reviewing their results.
- Deciding which changes to keep, restore, or reject.
- Maintaining the Git repository and committing and pushing the final changes.

AI-generated code and explanations were treated as assistance, not as proof of correctness.

---

## 2. Tool Log

The following table summarizes the main development activities. The prompt descriptions are reconstructed summaries, not verbatim copies of the original conversations.

| Step | Tool | Purpose of the prompt | What I verified myself |
|---|---|---|---|
| Initial Flask application, SQLite schema and generators | ChatGPT; Claude for supplementary review | Plan and implement the Flask application, SQLite database structure, and synthetic warehouse data generators. | Reviewed the project structure, database tables, generated records, and whether the application and database components were created correctly. |
| Risk detectors, alarm lifecycle, inspections and remediation scripts | ChatGPT; Claude for supplementary review | Develop risk detection logic and scripts for alarm handling, inspections, and remediation activities. | Examined generated records, database relationships, lifecycle results, and script execution output. |
| Anomaly injector: four cases, 15 each, and `ground_truth.csv` | ChatGPT | Implement four controlled anomaly categories with 15 cases per category and record affected rows in a separate ground-truth file. | Checked the four categories, 15 cases per category, affected database rows, and ground-truth records. |
| Alarm lifecycle with append-only history | ChatGPT | Restore a verified pre-lifecycle backup, then generate a seeded distribution of alarm states and record transitions in append-only history. | Checked the restored baseline, backup preservation, alarm-state distribution, history records, and database integrity. |
| Inspection and remediation generators with history and lot links | ChatGPT | Generate inspection and remediation records with associated history and links to actual inventory lots. | Checked generated records, linked lot IDs, history records, and preservation of existing dependencies. |
| `alarm_lots` rebuild cancelled after producing 93.8% affected lots | ChatGPT | Evaluate rebuilding alarm-to-lot associations and assess the resulting distribution. | Observed that the proposed rebuild produced 93.8% affected lots. I cancelled the operation and decided to retain the existing alarm-lot links instead of accepting the unsuitable distribution. |
| Removal of two zero-duration `alarm_lots` links | ChatGPT | Identify and remove two invalid zero-duration alarm-to-lot associations. | Checked the affected records and confirmed that the cleanup was limited to the two identified links. |
| CSV export script | ChatGPT | Develop a script to export database tables and ground-truth records to CSV files. | Compared exported table counts against the database. The export covered 19 tables and 1,699,396 total rows, with zero count mismatches. The exported `ground_truth.csv` contained 1,604 rows and was byte-identical to the source file. |
| Reproducibility checker | ChatGPT | Build a checker for nine base tables, execute two fresh generator runs, and compare their results with the actual database. | Ran the checker, compared both generated runs, and checked the results against the real database. The final reproducibility validation passed for all nine base tables. |
| Alignment of 2,620 base-table timestamps | ChatGPT | Investigate and correct timestamp differences between fresh generator output and the actual database. | Reviewed the 2,620 timestamp-cell differences and traced them to an earlier generator implementation that used the current clock. Checked the corrected seeded generator output against the database. |
| Validators and data dictionary | ChatGPT; Claude for supplementary review | Create and refine `validate_final.py`, `validate_phase10.py`, `validate_submission.py`, and the database data dictionary. | Ran the validators, inspected their results, and checked that the data dictionary represented the actual database schema. Final validation reported 11/11 checks passing. |
| README and submission documentation | ChatGPT; Claude for supplementary review | Prepare project documentation covering setup, database usage, scripts, outputs, limitations, and submission contents. | Reviewed the README against the actual repository, checked file paths, and corrected the database archive instructions and link. |

---

## 3. Key Prompts

The following are **paraphrases of the main prompts and requests**, reconstructed from the development work. They are not presented as exact quotations or verbatim chat history.

### 3.1 Initial Flask application, SQLite schema and generators

**Prompt paraphrase:** Plan and build a Python Flask warehouse monitoring application backed by SQLite. Include warehouse entities, storage zones, sensors, readings, inventory lots, and the required synthetic data generators.

### 3.2 Risk detectors, alarm lifecycle, inspections and remediation

**Prompt paraphrase:** Develop the risk detection and operational workflow scripts for identifying environmental and warehouse risks, managing alarms, creating inspections, and generating remediation activities.

### 3.3 Anomaly injector and ground truth

**Prompt paraphrase:** Implement a reproducible anomaly injector with four anomaly categories and 15 cases in each category. Record all modified, inserted, and deleted rows in a separate `ground_truth.csv` file so the injected changes can be audited.

The four categories were:

1. Wrong-type inventory lot zone assignments.
2. Overlapping sensor-zone assignments.
3. Missing sensor readings that create gaps of at least 30 minutes without a corresponding outage.
4. Removal of all `alarm_lots` links for selected alarms.

### 3.4 Alarm lifecycle and append-only history

**Prompt paraphrase:** Restore the verified pre-lifecycle database backup, establish a seeded distribution of alarm states, and record actual state transitions in an append-only `alarm_history` table.

### 3.5 Inspection and remediation generation

**Prompt paraphrase:** Generate inspection and remediation records with associated history and valid inventory-lot links. Preserve existing dependencies and avoid creating references to nonexistent lots.

### 3.6 Alarm-lot rebuild evaluation

**Prompt paraphrase:** Evaluate whether rebuilding the alarm-to-lot associations would produce a suitable distribution and preserve meaningful relationships.

The resulting rebuild was not accepted. I cancelled it after observing that it would produce 93.8% affected lots and chose to keep the existing links.

### 3.7 Zero-duration alarm-lot links

**Prompt paraphrase:** Identify the two zero-duration alarm-to-lot associations and remove only those invalid links.

### 3.8 CSV exports

**Prompt paraphrase:** Create a CSV export script that exports the database tables and ground-truth data, then compare the export counts against the source database.

### 3.9 Reproducibility checker

**Prompt paraphrase:** Build a reproducibility checker for nine base tables. Generate the data twice using fresh runs and compare the generated results with the actual project database.

### 3.10 Timestamp alignment

**Prompt paraphrase:** Investigate why the reproducibility check reports 2,620 timestamp-cell differences and align the base-table timestamps with the seeded generator rather than using the current clock.

### 3.11 Validation scripts and data dictionary

**Prompt paraphrase:** Create final, Phase 10, and submission validators. Generate a data dictionary from the actual SQLite schema and verify the documented tables and columns against the database.

### 3.12 README and submission documentation

**Prompt paraphrase:** Prepare a complete README explaining the project, setup, database, scripts, validation, outputs, limitations, and submission contents. Check that the documented database path points to the actual packaged database archive.

---

## 4. Mistakes and Corrections

The development process involved mistakes, failed checks, and corrections. The following examples are included to show that AI-generated output was reviewed rather than accepted without testing.

### 4.1 Empty ground-truth output

The initial ground-truth generation attempt produced no usable output because the detector scripts did not find matching anomalies in the clean data.

The database itself passed its integrity check, but the expected ground-truth files were missing.

**Correction:** The anomaly injection approach was developed to create controlled, known anomalies rather than expecting the clean baseline database to contain them naturally.

### 4.2 Anomaly label leaked into assignment data

The injector initially wrote `INJECTED_ANOMALY` into the `assignment_reason` field.

This was a problem because it exposed the injected anomaly directly in the underlying data and could make the anomaly too easy to identify.

**Correction:** I removed that marker from the assignment data. The original assignment reason was preserved for modified lot-zone assignments, and inserted overlapping sensor-zone assignments used a null reason. Ground truth remained separate.

### 4.3 Alarm-link injection initially deleted only one link

The first implementation of the alarm-link anomaly case deleted only one `alarm_lots` link per selected alarm.

That did not meet the intended condition, which required the selected alarms to have no remaining lot links.

**Correction:** The logic was changed to delete all `alarm_lots` links for each selected alarm.

### 4.4 Alarm lifecycle initially moved every alarm to CLOSED

The first lifecycle implementation produced an unsuitable result by moving every alarm to the CLOSED state.

**Correction:** The lifecycle work was revised to restore a verified pre-lifecycle backup with alarms in the OPEN state and apply a seeded distribution instead.

The intended distribution was:

- OPEN: 15%
- ACKNOWLEDGED: 15%
- RESOLVED: 25%
- CLOSED: 45%

The lifecycle implementation also recorded actual transitions in append-only history, with update and delete protections.

### 4.5 Alarm-lot rebuild produced an unsuitable distribution

A proposed `alarm_lots` rebuild resulted in approximately 93.8% affected lots.

That distribution was not accepted as an appropriate representation of the intended warehouse relationships.

**Correction:** I cancelled the rebuild and decided to retain the existing alarm-to-lot associations. The proposed result was not treated as a successful project change.

### 4.6 Reproducibility check initially failed on 2,620 timestamp cells

The first reproducibility comparison reported differences across 2,620 timestamp cells.

The differences came from an earlier generator implementation that used the current clock instead of the seeded, reproducible timestamp logic.

**Correction:** The base-table timestamps were aligned with the seeded generator. The reproducibility check was then rerun.

### 4.7 Submission validator incorrectly required unique entity IDs

An initial version of `validate_submission.py` incorrectly treated uniqueness of injected ground-truth `entity_id` values as a mandatory condition.

This validation rule did not correctly represent the intended data semantics.

**Correction:** I reviewed the failed validation and corrected the validator rather than treating its initial failure as proof that the underlying data was invalid.

### 4.8 Database packaging and README path mismatch

The README initially described the clean operational database as being supplied separately, while the repository actually tracked a compressed archive named `data/warehouse_monitor.db.gz`.

The compressed archive also initially differed from the current verified local database.

**Correction:** The archive was regenerated from the current local database, verified by comparing SHA-256 hashes after decompression, and pushed to GitHub. The README was updated to explain how to extract the archive and create `data/warehouse_monitor.db` without overwriting an existing database.

---

## 5. Human Verification

I executed the validation commands in my local development environment and reviewed their outputs.

The following checks were performed:

| Verification | What was checked | Result |
|---|---|---|
| Python compilation (`py_compile`) | Python source files compile without syntax errors. | PASS |
| Automated tests (`pytest`) | Automated project tests. | PASS |
| SQLite `integrity_check` | Database structural integrity. | PASS — `ok` |
| SQLite `foreign_key_check` | Foreign-key violations. | PASS — zero violations |
| `validate_final.py` | Final project validation checks. | PASS — 11/11 |
| `validate_phase10.py` | Phase 10 validation. | PASS |
| `validate_submission.py` | Submission validation. | PASS |
| Reproducibility checker | Two fresh runs compared against the actual database across nine base tables. | PASS — 9/9 tables |
| CSV export comparison | Exported row counts compared against the source database. | PASS — 19 tables, 1,699,396 total rows, zero mismatches |
| Ground-truth export | Exported ground-truth file compared with the source file. | PASS — 1,604 rows, byte-identical |
| Data dictionary validation | Documented schema compared with the actual SQLite database schema. | PASS — the initial schema documentation covered 15 tables and 118 columns; later project artifacts were updated as the schema evolved |
| Database archive verification | SHA-256 of the local database compared with the decompressed packaged archive. | PASS — identical hashes |

The final automated audit reported:

```text
Automated tests:       PASS
Phase 10 validation:   PASS
Submission validation: PASS

OVERALL RESULT: ALL TESTS PASSED
```

The final audit also checked Python syntax across 77 Python files.

These results describe the checks that were run and their reported outcomes. They do not imply that every possible behavior, deployment environment, or real-world warehouse scenario has been independently tested.

---

## 6. Limits of AI Use

There are several important limitations to the AI-assisted development process.

1. **AI-generated code required human review.** Generated code was not automatically assumed to be correct. Some initial implementations produced incorrect results and required revisions.

2. **Validation was necessary.** Database integrity, foreign-key checks, reproducibility comparisons, export comparisons, and project validators were used to evaluate the results.

3. **Not every pipeline operation is covered by the reproducibility hash proof.** Lifecycle, inspection, and remediation operations were applied through separate scripts. Their execution and resulting records were checked separately; they should not be represented as being proven by the nine-base-table reproducibility comparison.

4. **The reproducibility result has a defined scope.** The 9/9 result applies to the nine base tables checked by the reproducibility process. It does not establish that every generated operational record is reproducible through that same comparison.

5. **AI output was not the final authority.** Decisions such as cancelling the `alarm_lots` rebuild, retaining existing associations, and correcting validation rules were made after reviewing actual results.

6. **The verbatim chat history is not stored in this repository.** The prompt descriptions in this document are paraphrases reconstructed from the development process. They must not be interpreted as exact quotations.

7. **The second AI assistant's contribution is described at a high level.** Claude was used for supplementary review, planning, and checking outputs. This document does not claim a complete per-prompt Claude transcript or attribute specific code changes to Claude where that attribution cannot be established.

8. **Synthetic data is not real warehouse data.** The generated database and anomaly cases are intended for project demonstration and evaluation, not as evidence of actual warehouse operations.

---

## 7. Responsibility Statement

I am responsible for the submitted Warehouse Risk Monitor project, including its implementation, database contents, generated data, validation results, documentation, and final repository.

AI tools were used to assist with planning, code generation, review, debugging, and documentation. I ran the scripts and validation commands, reviewed their outputs, made decisions about whether to accept or reject proposed changes, and corrected issues discovered during development.

I understand that AI-generated code can contain errors and that passing automated checks does not guarantee the absence of every defect.

The final submission represents work that I reviewed and tested, and I accept responsibility for explaining and defending its design, implementation, limitations, and results during evaluation.
