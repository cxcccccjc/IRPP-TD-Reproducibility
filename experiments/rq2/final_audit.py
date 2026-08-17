from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent
MAIN_STEM = "IRPP-TD_RQ1_RQ2_Reorganized_Experiment_Chapter"
APP_STEM = "IRPP-TD_RQ1_RQ2_Reorganized_Supplementary_Experiments"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return sum(1 for _ in csv.reader(stream)) - 1


def resolve(obj):
    return obj.get_object() if hasattr(obj, "get_object") else obj


def font_is_embedded(font) -> bool:
    font = resolve(font)
    subtype = str(font.get("/Subtype", ""))
    if subtype == "/Type3":
        return bool(font.get("/CharProcs"))
    descendants = resolve(font.get("/DescendantFonts", []))
    if descendants:
        return all(font_is_embedded(item) for item in descendants)
    descriptor = resolve(font.get("/FontDescriptor", {}))
    return any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))


def collect_fonts(resources, found: dict[str, bool]) -> None:
    resources = resolve(resources or {})
    for name, font in resolve(resources.get("/Font", {})).items():
        item = resolve(font)
        base = str(item.get("/BaseFont", name))
        found[base] = found.get(base, True) and font_is_embedded(item)
    for xobj in resolve(resources.get("/XObject", {})).values():
        item = resolve(xobj)
        if str(item.get("/Subtype", "")) == "/Form":
            collect_fonts(item.get("/Resources", {}), found)


def audit_pdf(path: Path, expected_pages: int) -> dict:
    reader = PdfReader(path)
    assert len(reader.pages) == expected_pages, (path, len(reader.pages))
    fonts: dict[str, bool] = {}
    for page in reader.pages:
        width = float(page.mediabox.width) / 72.0
        height = float(page.mediabox.height) / 72.0
        assert abs(width - 8.5) < 0.01 and abs(height - 11.0) < 0.01
        collect_fonts(page.get("/Resources", {}), fonts)
    missing = sorted(name for name, embedded in fonts.items() if not embedded)
    assert not missing, f"Unembedded fonts in {path.name}: {missing}"
    return {"pages": len(reader.pages), "embedded_fonts": sorted(fonts)}


def audit_log(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    forbidden = {
        "overfull": r"Overfull \\hbox|Overfull \\vbox",
        "undefined_reference": r"Reference .* undefined|undefined references",
        "undefined_citation": r"Citation .* undefined|undefined citations",
        "multiply_defined_label": r"multiply defined",
        "missing_file": r"File .* not found",
    }
    hits = {key: re.findall(pattern, text, flags=re.IGNORECASE) for key, pattern in forbidden.items()}
    assert not any(hits.values()), (path, hits)
    return {"forbidden_warning_hits": hits}


def main() -> None:
    run_audit = json.loads((ROOT / "metadata/formal_run_audit.json").read_text(encoding="utf-8"))
    result_audit = json.loads((ROOT / "metadata/formal_result_audit.json").read_text(encoding="utf-8"))

    assert run_audit["seed_count"] == 30
    assert run_audit["job_count"] == 1710
    assert result_audit["task_rows"] == 171000
    assert result_audit["run_rows"] == 1710
    assert result_audit["worker_events"] == 171000
    assert result_audit["no_truth_tasks"] == 0
    assert result_audit["nonfinite_valid_task_errors"] == 0
    assert result_audit["angular_unavailable_tasks"] == 0

    row_counts = {
        "formal_task_metrics.csv": count_csv_rows(ROOT / "results/formal_task_metrics.csv"),
        "formal_run_summary.csv": count_csv_rows(ROOT / "results/formal_run_summary.csv"),
        "formal_worker_events.csv": count_csv_rows(ROOT / "results/formal_worker_events.csv"),
    }
    assert row_counts == {
        "formal_task_metrics.csv": 171000,
        "formal_run_summary.csv": 1710,
        "formal_worker_events.csv": 171000,
    }

    source_map = {
        "config.json": ROOT / "config.json",
        "data.py": ROOT / "src/data.py",
        "model.py": ROOT / "src/model.py",
        "core_base.py": ROOT / "src/core_base.py",
        "run_rq2_reorganized.py": ROOT / "run_rq2_reorganized.py",
    }
    actual_hashes = {name: sha256(path) for name, path in source_map.items()}
    assert actual_hashes == run_audit["source_hashes"]

    figure = PdfReader(ROOT / "figures/fig_rq2_reorganized_main_1x4.pdf").pages[0]
    rq1_figure = PdfReader(ROOT / "manuscript/fig_rq1_main.pdf").pages[0]
    figure_size = [float(figure.mediabox.width) / 72.0, float(figure.mediabox.height) / 72.0]
    rq1_figure_size = [
        float(rq1_figure.mediabox.width) / 72.0,
        float(rq1_figure.mediabox.height) / 72.0,
    ]
    assert all(abs(a - b) < 0.01 for a, b in zip(figure_size, rq1_figure_size))

    report = {
        "formal_counts": row_counts,
        "source_hashes_match_formal_run": True,
        "main_figure_media_box_inches": figure_size,
        "rq1_reference_media_box_inches": rq1_figure_size,
        "main_figure_latex_width": "textwidth (7.16 in)",
        "main_pdf": audit_pdf(ROOT / f"manuscript/{MAIN_STEM}.pdf", 5),
        "appendix_pdf": audit_pdf(ROOT / f"appendix/{APP_STEM}.pdf", 5),
        "main_log": audit_log(ROOT / f"manuscript/{MAIN_STEM}.log"),
        "appendix_log": audit_log(ROOT / f"appendix/{APP_STEM}.log"),
        "visual_review": "Completed separately from rendered 160-dpi page PNGs.",
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
