def validate_ground_truth():
    """Validate injected and detector-derived ground-truth rows separately."""
    gt = ROOT / "docs" / "phase10" / "ground_truth.csv"

    if not gt.exists():
        check(False, "Ground-truth CSV exists", str(gt))
        return

    try:
        with gt.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)

            # Remove any stray BOM or whitespace from header names.
            reader.fieldnames = [
                (name or "").lstrip("\ufeff").strip()
                for name in (reader.fieldnames or [])
            ]

            fields = set(reader.fieldnames)
            rows = list(reader)

    except Exception as exc:
        check(False, "Ground-truth CSV can be read", str(exc))
        return

    required_columns = {
        "label_status",
        "issue_type",
        "entity_id",
        "ground_truth_id",
    }

    missing_columns = sorted(required_columns - fields)
    schema_ok = not missing_columns

    check(
        schema_ok,
        "Ground-truth CSV contains required classification and identity columns",
        f"Missing: {missing_columns}",
    )

    if not schema_ok:
        return

    injected = [
        row for row in rows
        if row.get("label_status") == "CONFIRMED_INJECTED"
    ]

    detector_rows = [
        row for row in rows
        if row.get("label_status") == "REVIEW_REQUIRED"
    ]

    unknown_rows = [
        row for row in rows
        if row.get("label_status") not in {
            "CONFIRMED_INJECTED",
            "REVIEW_REQUIRED",
        }
    ]

    check(
        not unknown_rows,
        "Ground-truth rows use supported label statuses",
        f"{len(unknown_rows)} unsupported rows",
    )

    # Every injected row must carry both identifiers.
    injected_ids_present = all(
        (row.get("entity_id") or "").strip()
        and (row.get("ground_truth_id") or "").strip()
        for row in injected
    )

    check(
        injected_ids_present,
        "Injected ground truth has entity_id and ground_truth_id",
        f"{len(injected)} injected rows",
    )

    # ground_truth_id must be unique. entity_id is NOT unique by design:
    # one alarm or sensor can have many deleted links or readings.
    ground_truth_ids = [
        (row.get("ground_truth_id") or "").strip()
        for row in injected
    ]

    check(
        len(ground_truth_ids) == len(set(ground_truth_ids)),
        "Injected ground_truth_id values are unique",
        f"{len(ground_truth_ids)} rows",
    )

    injected_counts = Counter(
        (row.get("issue_type") or "").strip()
        for row in injected
    )

    missing_types = EXPECTED_INJECTED_TYPES - set(injected_counts)

    insufficient_types = {
        issue_type: injected_counts.get(issue_type, 0)
        for issue_type in EXPECTED_INJECTED_TYPES
        if injected_counts.get(issue_type, 0) < MIN_INJECTED_CASES_PER_TYPE
    }

    check(
        not missing_types and not insufficient_types,
        "All four injected anomaly types have at least 10 cases",
        "; ".join(
            f"{issue_type}={injected_counts.get(issue_type, 0)}"
            for issue_type in sorted(EXPECTED_INJECTED_TYPES)
        ),
    )

    # Detector-derived rows keep the original evidence requirements.
    detector_schema_ok = (
        not detector_rows
        or {"evidence", "source_tables"}.issubset(fields)
    )

    detector_evidence_ok = detector_schema_ok and all(
        (row.get("evidence") or "").strip()
        and (row.get("source_tables") or "").strip()
        for row in detector_rows
    )

    check(
        detector_evidence_ok,
        "Detector-derived REVIEW_REQUIRED rows contain source evidence",
        f"{len(detector_rows)} detector-derived rows",
    )

    print(
        "Ground-truth summary: "
        f"{len(rows)} total; "
        f"{len(injected)} CONFIRMED_INJECTED; "
        f"{len(detector_rows)} REVIEW_REQUIRED"
    )