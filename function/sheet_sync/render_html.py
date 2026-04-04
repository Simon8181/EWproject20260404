"""HTML table rendering for sheet rows."""

from __future__ import annotations

import html


def html_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "<p>No matching rows.</p>"
    keys = list(rows[0].keys())
    thead = "<tr>" + "".join(f"<th>{html.escape(str(k))}</th>" for k in keys) + "</tr>"
    body: list[str] = []
    for row in rows:
        tds = "".join(
            f"<td>{html.escape(str(row.get(k, '')))}</td>" for k in keys
        )
        body.append(f"<tr>{tds}</tr>")
    return (
        "<table><thead>"
        + thead
        + "</thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def html_document(sections: list[str]) -> str:
    inner = "".join(f"<section>{s}</section>" for s in sections)
    return f"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<meta name="theme-color" content="#1a365d"/>
<title>Sheet read</title>
<style>
  html {{ -webkit-text-size-adjust: 100%; }}
  body {{
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    margin: 0;
    background: #e8ecf1;
    padding: max(8px, env(safe-area-inset-top)) max(6px, env(safe-area-inset-right))
      max(10px, env(safe-area-inset-bottom)) max(6px, env(safe-area-inset-left));
  }}
  .table-wrap {{
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    max-width: 100vw;
    margin-bottom: 12px;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,.08);
  }}
  table {{ border-collapse: collapse; background: #fff; width: 100%; min-width: 520px;
    table-layout: auto; }}
  th, td {{ border: 1px solid #d9d9d9; padding: 6px 8px; vertical-align: top;
    word-wrap: break-word; white-space: pre-wrap; font-size: 12px; line-height: 1.3; max-width: 48vw; }}
  @media (min-width: 640px) {{
    th, td {{ font-size: 13px; padding: 8px 10px; max-width: none; }}
  }}
  th {{ background: #1a365d; color: #fff; position: sticky; top: 0; z-index: 1; text-align: left; }}
  h2 {{ font-size: clamp(13px, 3.2vw, 15px); color: #2d3748; margin: 16px 0 8px; padding: 0 4px; }}
  section:first-child h2 {{ margin-top: 4px; }}
</style>
</head>
<body>
<div class="table-wrap">{inner}</div>
</body>
</html>
"""
