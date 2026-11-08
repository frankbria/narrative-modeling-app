"""#1160: the CRAP gate's Python LCOV has a record for every executable physical line.

coverage.py's own LCOV report folds a multi-line statement onto its first line, so the
gate (which inventories bytecode lines) found continuation lines missing and marked the
body UNVERIFIED. `scripts/quality/python_lcov.py` writes the LCOV from coverage's raw
measured lines instead. These run real coverage over a probe module.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "quality" / "python_lcov.py"

PROBE = '''def subject(value, flag):
    result = dict(
        doubled=value * 2,
        label=(
            "big" if value > 10
            else "small"
        ),
    )
    if flag:
        return (
            result["doubled"]
        )
    return result


def never_called(
    x,
):
    return (
        x
    )


subject(3, False)
'''


def _lcov(tmp_path: Path) -> dict[str, dict[int, int]]:
    source = tmp_path / "pkg"
    source.mkdir()
    (source / "probe.py").write_text(PROBE)
    (source / "unimported.py").write_text('"""Never imported."""\nVALUE = (\n    1\n)\n')
    data = tmp_path / ".coverage"
    subprocess.run(
        [sys.executable, "-m", "coverage", "run", f"--data-file={data}", f"--source={source}", "probe.py"],
        cwd=source, check=True, capture_output=True,
    )
    out = tmp_path / "lcov.info"
    subprocess.run(
        [sys.executable, str(SCRIPT), "--data-file", str(data), "--source", str(source), "--output", str(out)],
        cwd=tmp_path, check=True, capture_output=True,
    )
    records: dict[str, dict[int, int]] = {}
    for line in out.read_text().splitlines():
        if line.startswith("SF:"):
            current = records.setdefault(line[3:], {})
        elif line.startswith("DA:"):
            number, hits = line[3:].split(",")
            current[int(number)] = int(hits)
    return records


def test_every_executable_line_has_a_record_and_continuation_lines_are_measured(tmp_path):
    probe = _lcov(tmp_path)["pkg/probe.py"]

    assert {line for line, hits in probe.items() if hits} == {1, 2, 3, 5, 6, 9, 13, 16, 24}
    # The branch not taken and the function never called are measured zero, not absent.
    assert {line for line, hits in probe.items() if not hits} == {10, 11, 19, 20}


def test_a_file_never_imported_is_measured_zero(tmp_path):
    unimported = _lcov(tmp_path)["pkg/unimported.py"]

    assert unimported and not any(unimported.values())


def test_paths_are_relative_to_the_working_directory_as_coverage_writes_them(tmp_path):
    assert set(_lcov(tmp_path)) == {"pkg/probe.py", "pkg/unimported.py"}
