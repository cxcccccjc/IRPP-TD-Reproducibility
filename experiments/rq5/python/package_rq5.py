#!/usr/bin/env python3
"""Create the final RQ5 checksum manifest and reproducibility archive."""

from __future__ import annotations

import csv
import hashlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT.parents[1] / "outputs"
MANIFEST = ROOT / "MANIFEST_SHA256.csv"
ARCHIVE = OUTPUTS / "RQ5_EndToEnd_Reproducibility_20260811.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def include_work(path: Path) -> bool:
    parts = set(path.parts)
    return "__pycache__" not in parts and path.suffix not in {".pyc"}


def main():
    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and include_work(path) and path != MANIFEST)
    rows = [(path.relative_to(ROOT).as_posix(), path.stat().st_size, sha256(path)) for path in files]
    with MANIFEST.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["relative_path", "bytes", "sha256"])
        writer.writerows(rows)
    files.append(MANIFEST)

    output_names = [
        "Fig5_RQ5_EndToEnd_Accountability_Final.pdf",
        "Fig5_RQ5_EndToEnd_Accountability_Final.svg",
        "Fig5_RQ5_EndToEnd_Accountability_Final.png",
        "Fig5_RQ5_EndToEnd_Accountability_Final.tiff",
        "FigS7_RQ5_Resource_Detail_2x2.pdf",
        "FigS8_RQ5_Audit_Detail_2x2.pdf",
        "RQ5_Protocol_Comparison_Table_Final.tex",
        "RQ5_Protocol_Lifecycle_Table_Supplement.tex",
        "RQ5_Setup_Table_Final.tex",
        "RQ5_Numeric_Macros.tex",
        "IRPP-TD_RQ1_RQ2_RQ3_RQ4_RQ5_Main_Formal_20260811.tex",
        "IRPP-TD_RQ1_RQ2_RQ3_RQ4_RQ5_Main_Formal_20260811.pdf",
        "IRPP-TD_RQ1_RQ2_RQ3_RQ4_RQ5_Supplementary_Formal_20260811.tex",
        "IRPP-TD_RQ1_RQ2_RQ3_RQ4_RQ5_Supplementary_Formal_20260811.pdf",
    ]
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, Path("RQ5_EndToEnd_Experiment_20260810") / path.relative_to(ROOT))
        for name in output_names:
            path = OUTPUTS / name
            if not path.exists():
                raise FileNotFoundError(path)
            archive.write(path, Path("manuscript_outputs") / name)
    print(f"{ARCHIVE} ({ARCHIVE.stat().st_size} bytes, {len(files)} experiment files)")


if __name__ == "__main__":
    main()
