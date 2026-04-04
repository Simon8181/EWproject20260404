"""Read-only admin UI: API / integration status (no secrets in full)."""

from __future__ import annotations

import html
import os
from pathlib import Path

from function.api_config import integration_snapshot

_ADMIN_CSS = """
  :root { --bg:#0a0a0a; --fg:#e5e7eb; --muted:#9ca3af; --orange:#ff6600; --bd:#2e2e2e; }
  body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--fg); margin: 0; padding: 24px; }
  h1 { font-size: 1.25rem; color: var(--orange); margin: 0 0 8px; }
  .lead { color: var(--muted); font-size: 0.9rem; margin-bottom: 20px; max-width: 56ch; }
  table { border-collapse: collapse; width: 100%; max-width: 720px; }
  th, td { border: 1px solid var(--bd); padding: 10px 12px; text-align: left; font-size: 0.9rem; }
  th { background: #141414; color: var(--muted); font-weight: 600; }
  .ok { color: #86efac; font-weight: 600; }
  .no { color: #fca5a5; font-weight: 600; }
  code { font-size: 0.8rem; color: #fdba74; }
  .foot { margin-top: 24px; font-size: 0.75rem; color: var(--muted); max-width: 56ch; line-height: 1.5; }
"""


def render_admin_page() -> str:
    rows = integration_snapshot()
    body_rows: list[str] = []
    for row in rows:
        st = row["configured"]
        cls = "ok" if st else "no"
        label = "Configured" if st else "Missing"
        body_rows.append(
            "<tr>"
            f"<td>{html.escape(row['name'])}</td>"
            f"<td><span class='{cls}'>{label}</span></td>"
            f"<td><code>{html.escape(row['env_hint'])}</code></td>"
            f"<td>{html.escape(row.get('masked_preview') or '—')}</td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>EW · API status</title>
  <style>{_ADMIN_CSS}</style>
</head>
<body>
  <h1>API & integration status</h1>
  <p class="lead">Read-only. Keys are never shown in full — only whether each integration is loaded and a masked preview where applicable.</p>
  <table>
    <thead><tr><th>Integration</th><th>Status</th><th>Env / file</th><th>Preview</th></tr></thead>
    <tbody>{"".join(body_rows)}</tbody>
  </table>
  <p class="foot">
    To change values, edit <code>config/api.secrets.env</code> or root <code>.env</code>, then restart the server.
    For production, prefer a secret manager (GCP Secret Manager, AWS Secrets Manager) and inject env at deploy time.
  </p>
</body>
</html>"""


def admin_token_configured() -> bool:
    return bool(os.environ.get("EW_ADMIN_TOKEN", "").strip())


def verify_admin_token(token: str | None) -> bool:
    expected = os.environ.get("EW_ADMIN_TOKEN", "").strip()
    if not expected:
        return False
    return (token or "").strip() == expected
