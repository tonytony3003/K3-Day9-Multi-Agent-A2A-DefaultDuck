from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "output"
CANDIDATE_ROOT = ROOT / "submission_candidates"
CANDIDATE_DIR = CANDIDATE_ROOT / "canceled_minimal_evidence"
ZIP_PATH = CANDIDATE_ROOT / "canceled_minimal_evidence.zip"

# These are derived from the current 50-case dataset, not used to choose an
# answer. The assertion prevents a broader accidental rewrite.
EXPECTED_CHANGED_CASES = {
    "EC_003",
    "EC_007",
    "EC_008",
    "EC_015",
    "EC_021",
    "EC_026",
    "EC_041",
    "EC_045",
}


def atomic_write(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build() -> dict:
    # Import after resolving ROOT so the script works when called directly.
    sys.path.insert(0, str(ROOT))
    from src.models import OutputCase

    source_files = sorted(SOURCE_DIR.glob("EC_*.json"))
    if len(source_files) != 50:
        raise RuntimeError(f"Expected 50 baseline outputs, found {len(source_files)}")

    if CANDIDATE_DIR.exists():
        shutil.rmtree(CANDIDATE_DIR)
    CANDIDATE_DIR.mkdir(parents=True)
    changed: list[str] = []

    for source_path in source_files:
        baseline = json.loads(source_path.read_text(encoding="utf-8"))
        candidate = json.loads(json.dumps(baseline))
        if candidate["assessment"]["primary_issue"] == "canceled_order_paid":
            candidate["evidence_ids"] = [
                evidence_id
                for evidence_id in candidate["evidence_ids"]
                if not evidence_id.startswith("item:")
            ]
            changed.append(candidate["case_id"])

        # Validate the public output contract and ensure this experiment only
        # changes evidence_ids on the intended canceled cases.
        try:
            OutputCase.model_validate(candidate)
        except ValidationError as exc:
            raise RuntimeError(f"Schema failure in {source_path.name}: {exc}") from exc
        baseline_without_evidence = {
            key: value for key, value in baseline.items() if key != "evidence_ids"
        }
        candidate_without_evidence = {
            key: value for key, value in candidate.items() if key != "evidence_ids"
        }
        if candidate_without_evidence != baseline_without_evidence:
            raise RuntimeError(f"Unexpected non-evidence change in {source_path.name}")
        atomic_write(CANDIDATE_DIR / source_path.name, candidate)

    if set(changed) != EXPECTED_CHANGED_CASES:
        raise RuntimeError(
            f"Changed case set mismatch: expected {sorted(EXPECTED_CHANGED_CASES)}, "
            f"got {sorted(changed)}"
        )

    candidate_files = sorted(CANDIDATE_DIR.glob("EC_*.json"))
    if [path.name for path in candidate_files] != [path.name for path in source_files]:
        raise RuntimeError("Candidate filenames do not exactly match baseline filenames")

    CANDIDATE_ROOT.mkdir(exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in candidate_files:
            # Store JSON files at ZIP root, as required by the submission spec.
            archive.write(path, arcname=path.name)

    with zipfile.ZipFile(ZIP_PATH) as archive:
        zipped_names = sorted(archive.namelist())
    if zipped_names != [path.name for path in candidate_files]:
        raise RuntimeError("ZIP content audit failed")

    return {
        "source_count": len(source_files),
        "candidate_count": len(candidate_files),
        "changed_cases": sorted(changed),
        "candidate_dir": str(CANDIDATE_DIR),
        "zip_path": str(ZIP_PATH),
        "zip_entries": len(zipped_names),
    }


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
