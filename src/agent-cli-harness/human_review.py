"""Prepare blind patch reviews and import human scores without rewriting trials."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import shutil

import harness


RUBRIC = """# Blind cleanup review

Open only this reviewer directory until every score is submitted. The controller
directory contains identities and must stay hidden from the reviewer.

Read task.txt, base/, and each cases/<anonymous-id>/changes.patch. Each patch is
relative to the same base. Fresh unit and independent Chromium checks passed
for every included patch. Those checks do not establish maintainability.

For each case, count changed lines you would revert before merging: an added
line removed or a deleted line restored counts as one. A replacement can count
as two. Count only changes in the patch, once each. Do not count unchanged
context, preferred alternative implementations, or hypothetical new work.
Use zero only after reviewing the full patch; leave null if unreviewed.
Record specific files/hunks and a reason (including why zero needs no cleanup).
The score cannot exceed the patch's added-plus-deleted line count.

Fill scores.json with your name, all six scores (or all cases in this package),
and blind_attestation=true only if you have not seen the identity mapping or
recognized which lane produced any case. If you already know the identities,
use another human reviewer; do not attest that the review was blind.

The code is unchanged, so style can suggest an author; anonymization removes
explicit run metadata, not every possible inference. Do not run patch code as
part of this review. Return only the completed scores.json to the controller.
"""


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def validate_scores(form, cases):
    if not isinstance(form, dict) or not isinstance(form.get("reviewer"), str) or not form["reviewer"].strip():
        raise ValueError("A named human reviewer is required")
    if form.get("blind_attestation") is not True:
        raise ValueError("The human reviewer must attest that the review was blind")
    rows = form.get("scores")
    if not isinstance(rows, list):
        raise ValueError("Scores must be a list")
    scores = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Malformed score")
        key = row.get("case_id")
        if not isinstance(key, str) or key not in cases or key in scores:
            raise ValueError("Unknown or duplicate case")
        value = row.get("human_cleanup_lines")
        if type(value) is not int or not 0 <= value <= cases[key]["changed_lines"]:
            raise ValueError("Cleanup lines must be an integer within the patch's changed-line count")
        if not isinstance(row.get("reason"), str) or not row["reason"].strip():
            raise ValueError("Every score needs a review reason")
        scores[key] = {"human_cleanup_lines": value, "reason": row["reason"].strip()}
    if scores.keys() != cases.keys():
        raise ValueError("Review must cover every case exactly once")
    return scores


def prepare(report_path, batches, output):
    """Bind anonymized patches to native evidence, not caller-supplied labels."""
    report_path, output = Path(report_path).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Review package already exists; never overwrite it")
    report = read(report_path)
    roots = {Path(root).resolve().name: Path(root).resolve() for root in batches}
    if len(roots) != len(batches):
        raise ValueError("Batch names must be unique")
    candidates = []
    identities = set()
    for row in report["runs"]:
        if not row["valid"] or not row["task_passed"]:
            raise ValueError("Blind review requires accepted task passes")
        root = roots.get(row["source_batch"])
        if root is None:
            raise ValueError("Source batch missing")
        run_id = row["run_id"]
        if not isinstance(run_id, str) or Path(run_id).name != run_id or run_id in (".", ".."):
            raise ValueError("Invalid run ID")
        identity = (root.name, run_id)
        if identity in identities:
            raise ValueError("Duplicate trial")
        identities.add(identity)
        manifest = harness.load_manifest(root)
        if harness.protocol_version(manifest) != report["protocol_version"] or any(
                manifest[key] != report[key] for key in ("seed_commit", "prompt_sha256")):
            raise ValueError("Report and source protocol/task differ")
        if harness.file_hash(root / "manifest.json") != row["source_manifest_sha256"]:
            raise ValueError("Source manifest hash mismatch")
        result_path = root / "results" / run_id / "result.json"
        native = harness.assess_record(result_path, manifest)
        patch = result_path.with_name("changes.patch")
        if not native["valid"] or not native["task_passed"] or native["lane"] != row["lane"]:
            raise ValueError("Native trial is not an accepted matching result")
        if harness.file_hash(patch) != native["patch_sha256"] or native["patch_sha256"] != row["patch_sha256"]:
            raise ValueError("Patch hash mismatch")
        candidates.append((root, row, patch, native))
    if not candidates:
        raise ValueError("No accepted cases")
    secrets.SystemRandom().shuffle(candidates)
    reviewer = output / "reviewer"
    reviewer.mkdir(parents=True)
    controller = {"schema_version": 1, "review_id": secrets.token_hex(12),
                  "source_report": str(report_path), "source_report_sha256": harness.file_hash(report_path),
                  "cases": {}, "files": {}}
    shutil.copyfile(candidates[0][0] / "task.txt", reviewer / "task.txt")
    (reviewer / "base").mkdir()
    base_manifest = harness.load_manifest(candidates[0][0])
    for name in base_manifest["fixture_hashes"]:
        source = harness.HERE / "fixture" / name
        shutil.copyfile(source, reviewer / "base" / name)
    form = {"review_id": controller["review_id"], "reviewer": "", "blind_attestation": False, "scores": []}
    for root, row, patch, native in candidates:
        key = "case-" + secrets.token_hex(6)
        target = reviewer / "cases" / key / "changes.patch"
        target.parent.mkdir(parents=True)
        shutil.copyfile(patch, target)
        controller["cases"][key] = {"source_batch": root.name, "run_id": row["run_id"],
            "lane": row["lane"], "patch_sha256": native["patch_sha256"], "changed_lines": native["changed_lines"]}
        form["scores"].append({"case_id": key, "human_cleanup_lines": None, "reason": ""})
    (reviewer / "README.md").write_text(RUBRIC, encoding="utf-8")
    harness.save(reviewer / "scores.json", form)
    for path in reviewer.rglob("*"):
        if path.is_file() and path != reviewer / "scores.json":
            controller["files"][path.relative_to(output).as_posix()] = harness.file_hash(path)
    harness.save(output / "controller" / "mapping.json", controller)
    (output / "controller" / "mapping.sha256").write_text(harness.file_hash(output / "controller/mapping.json"))
    render(output)
    return reviewer


def load_package(output):
    output = Path(output).resolve()
    if harness.file_hash(output / "controller/mapping.json") != (output / "controller/mapping.sha256").read_text().strip():
        raise ValueError("Controller mapping changed")
    mapping = read(output / "controller/mapping.json")
    if harness.file_hash(mapping["source_report"]) != mapping["source_report_sha256"]:
        raise ValueError("Source report changed; preserve the report used for review")
    for relative, expected in mapping["files"].items():
        target = (output / relative).resolve()
        if not target.is_relative_to(output) or harness.file_hash(target) != expected:
            raise ValueError("Review package changed")
    return mapping


def import_scores(output, scores_path):
    output = Path(output).resolve()
    mapping = load_package(output)
    receipt = output / "controller/accepted-scores.json"
    if receipt.exists():
        raise ValueError("Scores already imported; never overwrite a review")
    form = read(scores_path)
    if form.get("review_id") != mapping["review_id"]:
        raise ValueError("Scores belong to a different review")
    scores = validate_scores(form, mapping["cases"])
    harness.save(receipt, {"review_id": mapping["review_id"], "reviewer": form["reviewer"].strip(),
        "blind_attestation": True, "imported_at": datetime.now(timezone.utc).isoformat(),
        "input_sha256": harness.file_hash(scores_path), "scores": scores})
    receipt.with_suffix(".sha256").write_text(harness.file_hash(receipt))
    render(output)


def render(output):
    output = Path(output).resolve()
    mapping = load_package(output)
    source = read(mapping["source_report"])
    receipt_path = output / "controller/accepted-scores.json"
    scores = {}
    reviewer = None
    if receipt_path.exists():
        if harness.file_hash(receipt_path) != receipt_path.with_suffix(".sha256").read_text().strip():
            raise ValueError("Accepted scores changed")
        receipt = read(receipt_path)
        scores, reviewer = receipt["scores"], receipt["reviewer"]
    indexed = {(r["source_batch"], r["run_id"]): r for r in source["runs"]}
    for key, case in mapping["cases"].items():
        row = indexed[case["source_batch"], case["run_id"]]
        row["human_cleanup_lines"] = scores.get(key, {}).get("human_cleanup_lines")
        row["cleanup_reason"] = scores.get(key, {}).get("reason")
    source["human_review"] = {"review_id": mapping["review_id"], "reviewer": reviewer,
        "state": "measured" if scores else "unmeasured", "source_report_sha256": mapping["source_report_sha256"]}
    harness.save(output / "controller/report.json", source)
    lines = ["# Human effort measurements", "", "| Trial | Approval interruptions | Cleanup lines |", "|---|---:|---:|"]
    for row in source["runs"]:
        values = ["unmeasured" if row.get(k) is None else str(row[k]) for k in ("interruptions", "human_cleanup_lines")]
        lines.append(f"| {row['source_batch']}/{row['run_id']} | {' | '.join(values)} |")
    lines += ["", "Cleanup is measured only after a named human's blind review. Approval counts require separate supervised sessions.",
              "This is a derived report; original trials and reports are unchanged."]
    (output / "controller/report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--report", required=True, type=Path)
    prep.add_argument("--batch", required=True, action="append", type=Path)
    prep.add_argument("--output", required=True, type=Path)
    score = sub.add_parser("import-scores")
    score.add_argument("--package", required=True, type=Path)
    score.add_argument("--scores", required=True, type=Path)
    render_parser = sub.add_parser("report")
    render_parser.add_argument("--package", required=True, type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        print(prepare(args.report, args.batch, args.output))
    elif args.action == "import-scores":
        import_scores(args.package, args.scores)
    else:
        render(args.package)


if __name__ == "__main__":
    main()
