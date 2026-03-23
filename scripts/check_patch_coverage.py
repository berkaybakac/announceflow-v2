#!/usr/bin/env python3
"""Enforce patch (changed executable lines) coverage from coverage.xml."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


HUNK_RE = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _norm(path: str) -> str:
    return Path(path).as_posix().lstrip("./")


def parse_coverage_xml(path: Path) -> dict[str, tuple[set[int], set[int]]]:
    tree = ET.parse(path)
    root = tree.getroot()
    by_file: dict[str, tuple[set[int], set[int]]] = {}

    for cls in root.findall(".//class"):
        filename = cls.attrib.get("filename")
        if not filename:
            continue
        measured: set[int] = set()
        covered: set[int] = set()
        for line in cls.findall("./lines/line"):
            try:
                line_no = int(line.attrib["number"])
                hits = int(line.attrib.get("hits", "0"))
            except (KeyError, ValueError):
                continue
            measured.add(line_no)
            if hits > 0:
                covered.add(line_no)
        by_file[_norm(filename)] = (measured, covered)

    return by_file


def _run_diff(base_sha: str) -> str:
    commands = [
        ["git", "diff", "--unified=0", "--no-color", f"{base_sha}...HEAD", "--"],
        ["git", "diff", "--unified=0", "--no-color", f"{base_sha}..HEAD", "--"],
    ]
    for cmd in commands:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            return proc.stdout
    print(
        f"Patch coverage gate: git diff failed for base sha '{base_sha}'.",
        file=sys.stderr,
    )
    raise SystemExit(2)


def parse_changed_lines(base_sha: str) -> dict[str, set[int]]:
    diff = _run_diff(base_sha)
    changed: dict[str, set[int]] = defaultdict(set)
    current_file: str | None = None

    for raw_line in diff.splitlines():
        if raw_line.startswith("+++ "):
            new_path = raw_line[4:].strip()
            if new_path == "/dev/null":
                current_file = None
                continue
            if new_path.startswith("b/"):
                new_path = new_path[2:]
            current_file = _norm(new_path)
            continue

        if current_file is None:
            continue

        if raw_line.startswith("@@"):
            match = HUNK_RE.search(raw_line)
            if not match:
                continue
            start = int(match.group(1))
            count = int(match.group(2) or "1")
            if count <= 0:
                continue
            changed[current_file].update(range(start, start + count))

    return changed


def compute_patch_coverage(
    changed_lines: dict[str, set[int]],
    coverage_map: dict[str, tuple[set[int], set[int]]],
) -> tuple[int, int, dict[str, list[int]]]:
    covered_total = 0
    relevant_total = 0
    uncovered_by_file: dict[str, list[int]] = {}

    for file_path, changed in changed_lines.items():
        measured, covered = coverage_map.get(file_path, (set(), set()))
        relevant = changed & measured
        if not relevant:
            continue
        covered_changed = relevant & covered
        uncovered = sorted(relevant - covered_changed)

        covered_total += len(covered_changed)
        relevant_total += len(relevant)
        if uncovered:
            uncovered_by_file[file_path] = uncovered

    return covered_total, relevant_total, uncovered_by_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--coverage-xml",
        default="coverage.xml",
        help="Path to coverage XML report (Cobertura format).",
    )
    parser.add_argument(
        "--base-sha",
        required=True,
        help="Base commit SHA for git diff.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        help="Minimum required patch coverage percentage.",
    )
    args = parser.parse_args()

    coverage_xml = Path(args.coverage_xml)
    if not coverage_xml.is_file():
        print(f"Patch coverage gate: file not found: {coverage_xml}", file=sys.stderr)
        return 2

    changed_lines = parse_changed_lines(args.base_sha)
    if not changed_lines:
        print("Patch coverage gate: no changed lines found, skipping.")
        return 0

    coverage_map = parse_coverage_xml(coverage_xml)
    covered, relevant, uncovered_by_file = compute_patch_coverage(
        changed_lines, coverage_map
    )
    if relevant == 0:
        print("Patch coverage gate: no executable changed lines, skipping.")
        return 0

    patch_pct = (covered / relevant) * 100.0
    print(
        f"Patch coverage: {patch_pct:.2f}% ({covered}/{relevant}) "
        f"[required: {args.threshold:.2f}%]"
    )
    if uncovered_by_file:
        print("Uncovered changed executable lines:")
        for file_path in sorted(uncovered_by_file):
            lines = ",".join(str(n) for n in uncovered_by_file[file_path])
            print(f"  - {file_path}: {lines}")

    if patch_pct + 1e-9 < args.threshold:
        print("Patch coverage gate FAILED.", file=sys.stderr)
        return 1

    print("Patch coverage gate PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
