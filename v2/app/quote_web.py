from __future__ import annotations

import html
import json
import re
import secrets
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import certifi
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from .address_ai import ai_enabled, gemini_api_key, gemini_model
from .db import ensure_schema, now_iso, open_db
from .settings import get_settings

router = APIRouter(tags=["quote-ai"])

_GEMINI_URL_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)

_SLOT_KEYS = (
    "customer_name",
    "ship_from_raw",
    "ship_to_raw",
    "commodity_desc",
    "weight_raw",
    "volume_raw",
    "customer_quote_raw",
    "driver_rate_raw",
)


def _conn():
    st = get_settings()
    conn = open_db(st.db_path)
    ensure_schema(conn)
    return conn, st


def _http_post_json(url: str, body: dict) -> dict[str, object] | str:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "EW-v2-quote/1.0"},
        method="POST",
    )
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="ignore")
        except Exception:
            detail = ""
        return f"HTTP {e.code}: {e.reason} {detail}".strip()
    except OSError as e:
        return str(e)
    except json.JSONDecodeError as e:
        return str(e)


def _new_quote_no() -> str:
    return (
        f"AI-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        f"-{secrets.token_hex(2).upper()}"
    )


def _recompute_status(slots: dict[str, str]) -> str:
    cq = (slots.get("customer_quote_raw") or "").strip()
    dr = (slots.get("driver_rate_raw") or "").strip()
    if cq or dr:
        return "quoted"
    return "pending_quote"


def _status_customer_label(status: str) -> str:
    if status == "quoted":
        return "已记录报价信息"
    return "信息收集中"


def _row_to_slots(row) -> dict[str, str]:
    return {k: str(row[k] if row[k] is not None else "") for k in _SLOT_KEYS}


def _missing_labels(slots: dict[str, str]) -> list[str]:
    miss: list[str] = []
    if not (slots.get("customer_name") or "").strip():
        miss.append("客户名称")
    if not (slots.get("ship_from_raw") or "").strip():
        miss.append("提货地址")
    if not (slots.get("ship_to_raw") or "").strip():
        miss.append("送货地址")
    if not (slots.get("commodity_desc") or "").strip():
        miss.append("货物描述")
    w = (slots.get("weight_raw") or "").strip()
    v = (slots.get("volume_raw") or "").strip()
    if not w and not v:
        miss.append("重量或体积（至少一项）")
    return miss


def _gemini_extract(user_message: str, current: dict[str, str]) -> dict[str, str] | str:
    if not ai_enabled():
        return "AI_DISABLED"
    key = gemini_api_key()
    if not key:
        return "MISSING_GEMINI_API_KEY"
    model = gemini_model()
    prompt = (
        "你是中美跨境零担业务助手，负责从对话中收集报价所需字段。根据用户最新消息，更新报价字段。\n"
        "已知字段（JSON，空字符串表示尚未填写）：\n"
        f"{json.dumps(current, ensure_ascii=False)}\n"
        "用户最新消息：\n"
        f"{user_message}\n"
        "请只输出一个 JSON 对象，键为："
        "customer_name, ship_from_raw, ship_to_raw, commodity_desc, "
        "weight_raw, volume_raw, customer_quote_raw, driver_rate_raw。\n"
        "规则：仅当用户明确提供或修改某字段时填写该键；未提及的键用空字符串；"
        "不要编造地址或数字；金额可带货币说明放在同一字符串内。\n"
    )
    url = _GEMINI_URL_TMPL.format(
        model=urllib.parse.quote(model, safe=""),
        key=urllib.parse.quote(key, safe=""),
    )
    body = {
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        "contents": [{"parts": [{"text": prompt}]}],
    }
    raw = _http_post_json(url, body)
    if isinstance(raw, str):
        return raw
    candidates = raw.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        return "AI_EMPTY"
    parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
    if not isinstance(parts, list) or not parts:
        return "AI_EMPTY_TEXT"
    text = str((parts[0] or {}).get("text") or "").strip()
    if not text:
        return "AI_EMPTY_TEXT"
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return "AI_BAD_JSON"
    delta: dict[str, str] = {}
    for k in _SLOT_KEYS:
        v = obj.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            delta[k] = s
    return delta


def _naive_weight_volume(text: str) -> tuple[str, str]:
    w, v = "", ""
    m_w = re.search(
        r"(\d+(?:\.\d+)?\s*(?:lb|lbs|LB|LBS|kg|KG|吨|磅|公斤))\b", text, re.I
    )
    if m_w:
        w = m_w.group(1).strip()
    m_cbm = re.search(
        r"(\d+(?:\.\d+)?\s*(?:cbm|CBM|立方米|立方尺|cu\.?\s*ft|ft³))\b", text, re.I
    )
    if m_cbm:
        v = m_cbm.group(1).strip()
    return w, v


def _fallback_merge(user_message: str, cur: dict[str, str]) -> dict[str, str]:
    delta: dict[str, str] = {}
    text = (user_message or "").strip()
    if not text:
        return delta
    nw, nv = _naive_weight_volume(text)
    if nw and not (cur.get("weight_raw") or "").strip():
        delta["weight_raw"] = nw
    if nv and not (cur.get("volume_raw") or "").strip():
        delta["volume_raw"] = nv
    return delta


def _insert_placeholder(conn, quote_no: str) -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO load (
          quote_no, status, source_tabs,
          first_seen_at, last_seen_at, created_at, updated_at
        ) VALUES (?, 'pending_quote', 'quote', ?, ?, ?, ?)
        """,
        (quote_no, ts, ts, ts, ts),
    )
    conn.commit()


def _persist_slots(conn, quote_no: str, merged: dict[str, str]) -> None:
    status = _recompute_status(merged)
    ts = now_iso()
    conn.execute(
        f"""
        UPDATE load SET
          customer_name = ?,
          ship_from_raw = ?,
          ship_to_raw = ?,
          commodity_desc = ?,
          weight_raw = ?,
          volume_raw = ?,
          customer_quote_raw = ?,
          driver_rate_raw = ?,
          status = ?,
          last_seen_at = ?,
          updated_at = ?
        WHERE quote_no = ?
        """,
        (
            merged.get("customer_name", ""),
            merged.get("ship_from_raw", ""),
            merged.get("ship_to_raw", ""),
            merged.get("commodity_desc", ""),
            merged.get("weight_raw", ""),
            merged.get("volume_raw", ""),
            merged.get("customer_quote_raw", ""),
            merged.get("driver_rate_raw", ""),
            status,
            ts,
            ts,
            quote_no,
        ),
    )
    conn.commit()


def _build_reply(quote_no: str, merged: dict[str, str], ai_note: str = "") -> str:
    miss = _missing_labels(merged)
    parts = []
    if ai_note:
        parts.append(ai_note)
    if miss:
        parts.append(
            "已保存当前内容。"
            f"报价编号 {quote_no}。还缺：{'、'.join(miss)}。请继续说明。"
        )
    else:
        st = _recompute_status(merged)
        parts.append(
            f"必填项已齐，报价编号 {quote_no}（{_status_customer_label(st)}）。"
            "如需补充费用说明，可直接写出金额。"
        )
    return "\n\n".join(parts)


class ChatMessageIn(BaseModel):
    quote_no: str = Field(default="")
    message: str = Field(min_length=1)


@router.get("/quote", response_class=HTMLResponse)
def quote_page() -> HTMLResponse:
    body = """
<h1 class="gf-title">AI 收集报价数据</h1>
<p class="muted">请用自然语言描述托运需求，我们通过多轮对话帮您补齐报价所需信息。首次回复后会生成报价编号，请妥善保存以便跟进。</p>
<div id="banner" class="ok" style="display:none"></div>
<p class="muted">您的报价编号：<strong id="qn">—</strong></p>
<div id="chat" class="chat-log" aria-live="polite"></div>
<div class="chat-compose">
  <textarea id="msg" rows="3" placeholder="例如：Acme 公司；从洛杉矶 90021 提货；新泽西 08820 送货；塑料托盘约 20 托，约 18000 lb"></textarea>
  <button type="button" class="gf-btn gf-btn-primary" id="send">发送</button>
</div>
<script>
const chat = document.getElementById('chat');
const qnEl = document.getElementById('qn');
const banner = document.getElementById('banner');
let quoteNo = '';

function addBubble(role, text) {
  const d = document.createElement('div');
  d.className = 'bubble ' + (role === 'user' ? 'user' : 'bot');
  d.textContent = text;
  chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
}

function showBanner(t, err) {
  banner.textContent = t;
  banner.style.display = 'block';
  banner.className = err ? 'err' : 'ok';
}

async function send() {
  const ta = document.getElementById('msg');
  const text = (ta.value || '').trim();
  if (!text) return;
  ta.value = '';
  addBubble('user', text);
  const r = await fetch('/quote/api/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quote_no: quoteNo, message: text }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    addBubble('bot', '错误：' + (j.detail || r.status));
    return;
  }
  if (j.quote_no) {
    quoteNo = j.quote_no;
    qnEl.textContent = quoteNo;
  }
  addBubble('bot', j.reply || '');
  if (j.warning) showBanner(j.warning, true);
}

document.getElementById('send').addEventListener('click', send);
document.getElementById('msg').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); send(); }
});
</script>
"""
    return HTMLResponse(_quote_shell("AI 收集报价数据", body))


def _quote_shell(title: str, body: str) -> str:
    t = html.escape(title)
    return f"""<!doctype html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{t}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet"/>
  <style>
    :root {{
      --gf-primary: #673ab7;
      --gf-primary-hover: #5e35b1;
      --gf-surface: #ffffff;
      --gf-page: #f8f7fc;
      --gf-text: #202124;
      --gf-muted: #5f6368;
      --gf-border: #dadce0;
      --gf-success: #34a853;
      --gf-error: #d93025;
      --gf-radius: 8px;
      --gf-shadow: 0 1px 2px rgba(60,64,67,.3), 0 1px 3px 1px rgba(60,64,67,.15);
    }}
    *, *::before, *::after {{ box-sizing: border-box; }}
    body.gf-page {{
      margin: 0; min-height: 100vh;
      font-family: Roboto, system-ui, sans-serif;
      font-size: 14px; line-height: 1.5;
      color: var(--gf-text); background: var(--gf-page);
    }}
    .gf-header {{
      background: var(--gf-primary); color: #fff;
      box-shadow: var(--gf-shadow);
    }}
    .gf-header__inner {{
      max-width: 1200px; margin: 0 auto; padding: 12px 20px;
      display: flex; flex-wrap: wrap; align-items: center; gap: 12px;
    }}
    .gf-header__brand {{ font-weight: 500; font-size: 1.125rem; }}
    .gf-main {{ padding: 24px 16px 48px; }}
    .gf-card {{
      max-width: 800px; margin: 0 auto; background: var(--gf-surface);
      border-radius: var(--gf-radius); box-shadow: var(--gf-shadow);
      padding: 28px 32px 36px;
    }}
    .gf-title {{ margin: 0 0 8px; font-size: 1.5rem; font-weight: 500; }}
    .muted {{ color: var(--gf-muted); font-size: 13px; }}
    .ok {{
      border-left: 4px solid var(--gf-success); background: #e6f4ea;
      padding: 12px 16px; border-radius: 0 var(--gf-radius) var(--gf-radius) 0;
      margin: 0 0 16px;
    }}
    .err {{
      border-left: 4px solid var(--gf-error); background: #fce8e6;
      padding: 12px 16px; border-radius: 0 var(--gf-radius) var(--gf-radius) 0;
      margin: 0 0 16px;
    }}
    .gf-btn {{
      display: inline-flex; align-items: center; justify-content: center;
      min-height: 40px; padding: 0 24px; font-family: inherit;
      font-size: 14px; font-weight: 500; border-radius: 4px;
      cursor: pointer; border: none; text-decoration: none;
    }}
    .gf-btn-primary {{ background: var(--gf-primary); color: #fff; }}
    .gf-btn-primary:hover {{ background: var(--gf-primary-hover); }}
    .chat-log {{
      border: 1px solid var(--gf-border); border-radius: var(--gf-radius);
      min-height: 200px; max-height: 420px; overflow: auto;
      padding: 12px; background: #fafafa; margin: 16px 0;
    }}
    .bubble {{ margin: 8px 0; padding: 10px 12px; border-radius: 8px; max-width: 95%; white-space: pre-wrap; }}
    .bubble.user {{ background: #e8eaf6; margin-left: 12%; }}
    .bubble.bot {{ background: #fff; border: 1px solid var(--gf-border); margin-right: 8%; }}
    .chat-compose textarea {{
      width: 100%; font-family: inherit; font-size: 14px;
      padding: 10px 12px; border: 1px solid var(--gf-border);
      border-radius: var(--gf-radius); resize: vertical;
    }}
    .chat-compose {{ display: flex; flex-direction: column; gap: 10px; }}
  </style>
</head>
<body class="gf-page">
  <header class="gf-header">
    <div class="gf-header__inner">
      <div class="gf-header__brand">AI 收集报价数据</div>
    </div>
  </header>
  <main class="gf-main">
    <div class="gf-card">
      {body}
    </div>
  </main>
</body>
</html>"""


@router.post("/quote/api/message")
def quote_api_message(payload: ChatMessageIn) -> JSONResponse:
    conn, _ = _conn()
    msg = payload.message.strip()
    if not msg:
        return JSONResponse({"detail": "消息为空"}, status_code=422)
    qn_in = (payload.quote_no or "").strip()

    quote_no = qn_in or _new_quote_no()
    row = conn.execute("SELECT * FROM load WHERE quote_no = ?", (quote_no,)).fetchone()
    if not row:
        if qn_in:
            return JSONResponse(
                {"detail": f"未知 quote_no：{qn_in}"},
                status_code=404,
            )
        _insert_placeholder(conn, quote_no)
        row = conn.execute("SELECT * FROM load WHERE quote_no = ?", (quote_no,)).fetchone()

    cur = _row_to_slots(row)
    warning = ""
    ex = _gemini_extract(msg, cur)
    delta: dict[str, str] = {}
    if isinstance(ex, dict):
        delta = ex
    else:
        warning = f"（Gemini 不可用：{ex}，已尝试简单规则提取。）"
        delta = _fallback_merge(msg, cur)

    merged = dict(cur)
    for k, v in delta.items():
        if v.strip():
            merged[k] = v.strip()

    _persist_slots(conn, quote_no, merged)
    reply = _build_reply(quote_no, merged, ai_note=warning if warning else "")
    return JSONResponse(
        {
            "quote_no": quote_no,
            "reply": reply,
            "slots": merged,
            "missing": _missing_labels(merged),
            "warning": warning or None,
        }
    )
