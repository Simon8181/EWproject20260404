"""Load sheet rows through rules config (shared by CLI and HTTP service)."""

from __future__ import annotations

from collections.abc import Iterator

from .config import AppConfig
from .sync import _open_sheet_client, fetch_worksheet_rows, normalize_row_strings, row_passes_filters


def iter_mapped_rows(cfg: AppConfig) -> Iterator[tuple[str, dict[str, str]]]:
    """Yield (job_label, row_dict) for every row passing filters."""
    gc = _open_sheet_client()
    for job in cfg.jobs:
        _, rows = fetch_worksheet_rows(gc, cfg.spreadsheet_id, job)
        for r in rows:
            nr = normalize_row_strings(r, job.reading)
            if not row_passes_filters(nr, job.reading, job):
                continue
            row_dict = job.project_normalized_row(nr)
            yield job.label, row_dict


def read_mapped_rows(cfg: AppConfig, limit: int | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for _label, row in iter_mapped_rows(cfg):
        out.append(row)
        if limit is not None and len(out) >= limit:
            break
    return out


def read_mapped_sections(cfg: AppConfig, limit: int | None) -> list[tuple[str, list[dict[str, str]]]]:
    """One section per job (for HTML); limit applies to total rows across jobs."""
    sections: list[tuple[str, list[dict[str, str]]]] = []
    current_label: str | None = None
    current_rows: list[dict[str, str]] = []
    count = 0

    for label, row in iter_mapped_rows(cfg):
        if current_label is not None and label != current_label:
            sections.append((current_label, current_rows))
            current_rows = []
        current_label = label
        current_rows.append(row)
        count += 1
        if limit is not None and count >= limit:
            if current_label is not None:
                sections.append((current_label, current_rows))
            return sections

    if current_label is not None and current_rows:
        sections.append((current_label, current_rows))
    return sections
