#!/usr/bin/env python3
"""Enforce global branch coverage percentage from coverage.xml."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _read_branch_coverage(path: Path) -> tuple[float, str, str]:
    tree = ET.parse(path)
    root = tree.getroot()

    branch_rate = root.attrib.get("branch-rate")
    if branch_rate is None:
        print(
            "Branch coverage gate: 'branch-rate' not found in coverage XML.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    try:
        branch_pct = float(branch_rate) * 100.0
    except ValueError:
        print(
            f"Branch coverage gate: invalid branch-rate value '{branch_rate}'.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None

    covered = root.attrib.get("branches-covered", "?")
    valid = root.attrib.get("branches-valid", "?")
    return branch_pct, covered, valid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--coverage-xml",
        default="coverage.xml",
        help="Path to coverage XML report (Cobertura format).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=70.0,
        help="Minimum required global branch coverage percentage.",
    )
    args = parser.parse_args()

    coverage_xml = Path(args.coverage_xml)
    if not coverage_xml.is_file():
        print(f"Branch coverage gate: file not found: {coverage_xml}", file=sys.stderr)
        return 2

    branch_pct, covered, valid = _read_branch_coverage(coverage_xml)
    print(
        f"Global branch coverage: {branch_pct:.2f}% "
        f"({covered}/{valid}) [required: {args.threshold:.2f}%]"
    )

    if branch_pct + 1e-9 < args.threshold:
        print("Branch coverage gate FAILED.", file=sys.stderr)
        return 1

    print("Branch coverage gate PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
