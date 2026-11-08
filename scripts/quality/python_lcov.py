"""Write an LCOV file with a record for every executable physical line (#1160).

The CRAP gate inventories a Python body's executable lines from the bytecode line
table, so a multi-line statement contributes every line it spans. coverage.py's LCOV
report folds such a statement onto its first line, which left the continuation lines
without a record and the body UNVERIFIED. The raw measured lines in coverage's data
file do carry them (the interpreter reports each new line it executes), so this writes
the LCOV from those: every executable line gets a record, hit or zero.

Usage: python python_lcov.py --data-file .coverage --source app --output lcov.info
Paths in the output are relative to the working directory, as coverage writes them.
"""

import argparse
from pathlib import Path
from types import CodeType

from coverage import CoverageData


def executable_lines(code: CodeType) -> set[int]:
    """Lines with bytecode, nested code objects included: the gate's own inventory."""
    lines = {line for _, _, line in code.co_lines() if line}
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            lines |= executable_lines(constant)
    return lines


def record(path: Path, measured: set[int]) -> str:
    source = path.read_text(encoding="utf-8")
    inventory = sorted(executable_lines(compile(source, str(path), "exec", dont_inherit=True, optimize=0)))
    hit = [line for line in inventory if line in measured]
    rows = [f"DA:{line},{int(line in measured)}" for line in inventory]
    relative = path.resolve().relative_to(Path.cwd().resolve())
    return "\n".join([f"SF:{relative}", *rows, f"LF:{len(inventory)}", f"LH:{len(hit)}", "end_of_record"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-file", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()

    data = CoverageData(basename=str(arguments.data_file))
    data.read()
    measured = {str(Path(name).resolve()): set(data.lines(name) or ()) for name in data.measured_files()}
    files = sorted(arguments.source.resolve().rglob("*.py"))
    records = [record(path, measured.get(str(path), set())) for path in files]
    arguments.output.write_text("\n".join(records) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
