#!/usr/bin/env python3
"""Small dependency-free helpers for the study scripts."""

from __future__ import annotations

import csv
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return {}
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        if any(ch in value for ch in [".", "e", "E"]):
            return float(value)
        return int(value)
    except ValueError:
        return value


def load_simple_yaml(path: Path) -> Dict[str, Any]:
    """Parse the small YAML subset used by this repository.

    The project intentionally avoids a PyYAML dependency on machines where only
    the ns-3 Debian package is installed.  The parser supports nested mappings
    with two-space indentation and inline arrays.
    """

    root: Dict[str, Any] = {}
    stack: List[tuple[int, Dict[str, Any]]] = [(-1, root)]
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line:
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, sep, value = line.strip().partition(":")
        if not sep:
            continue
        while stack and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        parsed = _parse_scalar(value)
        current[key] = parsed
        if isinstance(parsed, dict):
            stack.append((indent, parsed))
    return root


def flatten_dict(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in data.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten_dict(value, name))
        else:
            out[name] = value
    return out


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def write_csv_rows(path: Path, rows: Iterable[Dict[str, Any]], fieldnames: List[str] | None = None) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not fieldnames and rows:
        fieldnames = list(rows[0].keys())
    fieldnames = fieldnames or []
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def to_float(row: Dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key, "")
        if value in {"", "nan", "NaN"}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(row: Dict[str, str], key: str, default: int = 0) -> int:
    try:
        value = row.get(key, "")
        if value in {"", "nan", "NaN"}:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        return "unknown"


def ensure_binary(binary: Path) -> None:
    if binary.exists():
        return
    subprocess.run(["make", "-j"], cwd=ROOT, check=True)


def quadriga_distances(trace_path: Path) -> List[float]:
    rows = read_csv_rows(trace_path)
    distances = sorted({float(row["distance_m"]) for row in rows if row.get("distance_m")})
    return distances


def scenario_retry_limit(scenario: str) -> int:
    if scenario == "S8":
        return 9
    if scenario == "S9":
        return 11
    return 7


def env_with_git() -> Dict[str, str]:
    env = os.environ.copy()
    env["GIT_COMMIT"] = git_commit()
    return env
