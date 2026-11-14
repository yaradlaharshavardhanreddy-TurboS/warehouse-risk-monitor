#!/usr/bin/env bash
# One-command, non-destructive final submission workflow.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

pass() { printf '\n\033[32mPASS\033[0m %s\n' "$1"; }
fail() { printf '\n\033[31mFAIL\033[0m %s\n' "$1" >&2; exit 1; }

printf '\n========== WAREHOUSE RISK MONITOR FINALIZATION ==========\n'
[[ -f data/warehouse_monitor.db ]] || fail "Operational database not found; run from the complete project checkout."

python -m compileall -q app scripts tests || fail "Python compile check failed"
pass "Python source compilation"

python -m scripts.run_test_suite || fail "Pytest failed"
pass "Automated test suite"

python -m scripts.build_ground_truth || fail "Evidence-based ground-truth generation failed"
python -m scripts.build_controlled_business_fixtures || fail "Controlled business fixtures failed"
python -m scripts.build_data_dictionary || fail "Data dictionary generation failed"
if [[ ! -s docs/phase10/remediation_traceability.csv ]]; then
  python -m scripts.build_remediation_traceability || fail "Remediation traceability generation failed"
else
  pass "Existing 118 MB remediation traceability evidence preserved (not regenerated)"
fi
python -m scripts.build_generation_manifest || fail "Generation manifest generation failed"
pass "Ground truth and supporting evidence artifacts"

python -m scripts.run_profiles --profiles starter full --runs 2 || fail "Starter/full profile execution or reproducibility failed"
pass "Starter and full profile two-run reproducibility"

python -m scripts.validate_submission --profile full || fail "Comprehensive database/business validation failed"
python -m scripts.validate_phase10 || fail "Phase 10 validation failed"
pass "Database integrity, business rules and challenge validation"

python -m scripts.build_submission_readiness || fail "Submission readiness report failed"
python -m scripts.package_submission || fail "Submission package failed"
pass "Documentation, readiness report and packaged project"

printf '\n========== FINAL RESULT ==========\n'
printf 'All scripted finalization stages passed.\n'
printf 'Package: dist/warehouse-risk-monitor-submission.zip\n'
printf 'Readiness: docs/phase10/phase15_submission_readiness.json\n'
printf 'Reproducibility: reports/profile_execution_reproducibility.json\n'
printf 'No Git commit/push was performed. Operational database was not modified.\n'
