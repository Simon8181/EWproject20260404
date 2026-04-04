"""
DAT 风格参考（货运 load board 常见：深色底 + 橙色强调）。
仅视觉参考，与 DAT 无隶属关系。
"""

# 订单页完整 CSS（供 order_view 内联；勿在外层 f-string 中手写含单花括号的字面量）
ORDER_PAGE_CSS = """
    :root {
      --dat-orange: #ff6600;
      --dat-orange-dim: #cc5200;
      --dat-bg: #0a0a0a;
      --dat-surface: #141414;
      --dat-surface2: #1c1c1c;
      --dat-border: #2e2e2e;
      --dat-text: #f3f4f6;
      --dat-muted: #9ca3af;
      --radius: 10px;
    }
    * { box-sizing: border-box; }
    html { -webkit-text-size-adjust: 100%; }
    body {
      margin: 0;
      min-height: 100dvh;
      font-family: "DM Sans", system-ui, sans-serif;
      background: radial-gradient(ellipse 120% 80% at 50% -20%, rgba(255,102,0,.14), transparent 55%),
        linear-gradient(180deg, #080808 0%, var(--dat-bg) 40%);
      color: var(--dat-text);
      -webkit-font-smoothing: antialiased;
      padding: max(8px, env(safe-area-inset-top)) max(10px, env(safe-area-inset-right))
        max(12px, env(safe-area-inset-bottom)) max(10px, env(safe-area-inset-left));
    }
    .oc-wrap { max-width: 720px; margin: 0 auto; }
    .oc-top {
      display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
      gap: 8px; margin-bottom: 12px;
      border-bottom: 1px solid var(--dat-border);
      padding-bottom: 10px;
    }
    .oc-top h1 {
      font-size: clamp(17px, 4.2vw, 22px); font-weight: 800; letter-spacing: -0.02em; margin: 0;
      color: #fff;
    }
    .oc-brand { color: var(--dat-orange); }
    .oc-title-sub { color: #e5e7eb; font-weight: 700; }
    .oc-top a {
      color: var(--dat-orange);
      text-decoration: none; font-size: 13px; font-weight: 700;
      padding: 6px 4px;
    }
    .oc-top a:hover { text-decoration: underline; }
    .oc-card {
      background: var(--dat-surface);
      border: 1px solid var(--dat-border);
      border-left: 4px solid var(--dat-orange);
      border-radius: var(--radius);
      padding: 10px 12px;
      margin-bottom: 10px;
      box-shadow: 0 4px 24px rgba(0,0,0,.45);
    }
    .oc-head {
      margin-bottom: 8px;
      display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 10px;
    }
    .oc-ew {
      font-size: clamp(15px, 3.8vw, 17px); font-weight: 800; letter-spacing: -0.02em;
      color: var(--dat-orange);
    }
    .oc-meta { display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: center; flex: 1; min-width: 0; }
    .oc-co { font-size: 12px; color: var(--dat-muted); word-break: break-word; }
    .oc-bol {
      font-size: 10px; padding: 2px 8px; border-radius: 999px;
      background: rgba(255,102,0,.15); color: #ffb380; border: 1px solid rgba(255,102,0,.35);
    }
    .oc-a {
      font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 999px;
      letter-spacing: .02em;
    }
    .oc-a--wait {
      color: #fecaca;
      background: rgba(220,38,38,.25);
      border: 1px solid rgba(248,113,113,.45);
    }
    .oc-a--ok {
      color: #bbf7d0;
      background: rgba(22,163,74,.22);
      border: 1px solid rgba(74,222,128,.4);
    }
    .oc-grid-3 {
      display: grid;
      grid-template-columns: 1fr minmax(44px, 52px) 1fr;
      gap: 6px;
      align-items: stretch;
    }
    .oc-mid-route {
      display: flex;
      align-items: center;
      justify-content: center;
      min-width: 0;
    }
    .oc-route-mid {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 72px;
      padding: 8px 10px;
      border-radius: 10px;
      font-size: 12px;
      font-weight: 800;
      text-decoration: none;
      color: #0a0a0a;
      background: linear-gradient(180deg, #ff8533, var(--dat-orange));
      border: 1px solid #ff9933;
      writing-mode: vertical-rl;
      text-orientation: mixed;
      letter-spacing: 0.12em;
      -webkit-tap-highlight-color: transparent;
    }
    .oc-route-mid:active { filter: brightness(0.95); }
    .oc-route-mid--off {
      writing-mode: vertical-rl;
      font-size: 11px;
      color: var(--dat-muted);
      opacity: 0.45;
      cursor: default;
    }
    @media (max-width: 560px) {
      .oc-grid-3 { grid-template-columns: 1fr; }
      .oc-from { order: 1; }
      .oc-mid-route { order: 2; min-height: 44px; padding: 4px 0; }
      .oc-to { order: 3; }
      .oc-route-mid, .oc-route-mid--off {
        writing-mode: horizontal-tb;
        min-height: 44px;
        width: 100%;
        max-width: 220px;
        letter-spacing: 0.06em;
      }
    }
    .oc-lane {
      border-radius: 8px;
      padding: 8px 10px;
      min-height: 0;
      background: var(--dat-surface2);
      border: 1px solid var(--dat-border);
    }
    .oc-lane:has(.oc-lane-link) { cursor: pointer; }
    a.oc-lane-link {
      color: inherit;
      text-decoration: none;
      border-radius: 6px;
      outline-offset: 2px;
    }
    a.oc-lane-link:focus-visible { outline: 2px solid var(--dat-orange); }
    a.oc-lane-link:active { opacity: 0.92; }
    .oc-from h3 { color: #ff9933; }
    .oc-to h3 { color: #ffa366; }
    .oc-lane h3 {
      margin: 0 0 4px;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
      color: var(--dat-muted);
    }
    .oc-body {
      font-size: 13px;
      line-height: 1.4;
      word-break: break-word;
      white-space: pre-wrap;
      color: #e5e7eb;
    }
    .oc-route {
      margin-top: 8px;
      padding: 8px 10px;
      border-radius: 8px;
      border: 1px solid var(--dat-border);
      background: #121212;
    }
    .oc-route h3 {
      margin: 0 0 6px;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .06em;
      color: var(--dat-orange);
    }
    .oc-km { margin-bottom: 6px; display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
    .oc-km-label { font-size: 10px; font-weight: 800; color: var(--dat-muted); }
    .oc-km-val {
      font-size: clamp(15px, 3.6vw, 17px);
      font-weight: 800;
      color: #fff;
      letter-spacing: -0.02em;
    }
    .oc-pnl {
      margin-top: 8px;
      padding: 8px 10px;
      border-radius: 8px;
      border: 1px solid rgba(255,102,0,.45);
      background: linear-gradient(165deg, rgba(255,102,0,.12), rgba(20,20,20,.9));
    }
    .oc-pnl h3 {
      margin: 0 0 6px;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .06em;
      color: #ffb380;
    }
    .oc-chip-muted .v { font-size: 10px; color: var(--dat-muted); line-height: 1.35; }
    .oc-load {
      margin-top: 8px;
      padding: 8px 10px;
      border-radius: 8px;
      border: 1px solid var(--dat-border);
      background: #121212;
    }
    .oc-load h3 {
      margin: 0 0 6px;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .06em;
      color: #fdba74;
    }
    .oc-dims {
      font-size: 13px;
      font-weight: 600;
      line-height: 1.4;
      color: #fff;
      white-space: pre-wrap;
      word-break: break-word;
      margin-bottom: 8px;
    }
    .oc-sub {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 6px;
    }
    @media (max-width: 380px) { .oc-sub { grid-template-columns: 1fr; } }
    .oc-chip {
      padding: 6px 8px;
      border-radius: 8px;
      background: #0d0d0d;
      border: 1px solid var(--dat-border);
      font-size: 11px;
      line-height: 1.35;
    }
    .oc-chip .k {
      display: block;
      font-size: 9px;
      font-weight: 800;
      letter-spacing: .04em;
      color: var(--dat-muted);
      margin-bottom: 2px;
    }
    .oc-chip .v { color: #d1d5db; white-space: pre-wrap; word-break: break-word; }
    .oc-foot {
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid var(--dat-border);
      font-size: 10px;
      line-height: 1.35;
      color: var(--dat-muted);
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .oc-st {
      white-space: pre-wrap;
      word-break: break-word;
      display: -webkit-box;
      -webkit-line-clamp: 4;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .oc-dat { color: #fdba74; }
    .empty { color: var(--dat-muted); font-style: italic; }
    .oc-empty { text-align: center; color: var(--dat-muted); padding: 24px 12px; font-size: 14px; }
"""

HOME_PAGE_CSS = """
    :root {
      --dat-orange: #ff6600;
      --dat-bg0: #080808;
      --dat-bg1: #0f0f0f;
      --dat-card: #141414;
      --dat-border: #2e2e2e;
      --dat-text: #f3f4f6;
      --dat-muted: #9ca3af;
    }
    * { box-sizing: border-box; }
    html { -webkit-text-size-adjust: 100%; }
    body {
      margin: 0;
      min-height: 100dvh;
      font-family: "DM Sans", system-ui, sans-serif;
      background: radial-gradient(ellipse 100% 60% at 50% -15%, rgba(255,102,0,.16), transparent 50%),
        linear-gradient(180deg, var(--dat-bg0), var(--dat-bg1));
      color: var(--dat-text);
      -webkit-font-smoothing: antialiased;
      padding: max(12px, env(safe-area-inset-top)) max(14px, env(safe-area-inset-right))
        max(20px, env(safe-area-inset-bottom)) max(14px, env(safe-area-inset-left));
    }
    .wrap { max-width: 1100px; margin: 0 auto; padding-bottom: 32px; }
    header { margin-bottom: clamp(18px, 4vw, 28px); }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: .06em;
      text-transform: uppercase;
      color: var(--dat-orange);
      background: rgba(255,102,0,.1);
      border: 1px solid rgba(255,102,0,.35);
      margin-bottom: 12px;
    }
    h1 {
      font-size: clamp(24px, 4.5vw, 36px);
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1.15;
      margin: 0 0 10px;
      color: #fff;
    }
    h1 .dat { color: var(--dat-orange); }
    .lead {
      font-size: clamp(13px, 3.2vw, 15px);
      line-height: 1.5;
      color: var(--dat-muted);
      max-width: 52ch;
      margin: 0 0 12px;
    }
    .meta { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; font-size: 13px; }
    .meta a { color: var(--dat-orange); text-decoration: none; font-weight: 700; }
    .meta a:hover { text-decoration: underline; }
    .meta span { color: var(--dat-muted); }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(min(100%, 240px), 1fr));
      gap: 12px;
    }
    @media (max-width: 480px) { .grid { grid-template-columns: 1fr; gap: 10px; } }
    .card {
      padding: 14px 16px;
      border-radius: 12px;
      background: var(--dat-card);
      border: 1px solid var(--dat-border);
      border-left: 4px solid var(--dat-orange);
      box-shadow: 0 8px 32px rgba(0,0,0,.4);
      transition: border-color .2s ease;
    }
    @media (hover: hover) {
      .card:hover { border-color: rgba(255,102,0,.5); }
    }
    .card-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 10px;
    }
    .pill {
      font-size: 13px;
      font-weight: 800;
      color: #fff;
      background: linear-gradient(135deg, #ff8533, var(--dat-orange));
      padding: 4px 10px;
      border-radius: 8px;
    }
    .sid { font-size: 11px; color: var(--dat-muted); word-break: break-all; text-align: right; }
    .note { font-size: 13px; line-height: 1.4; color: #d1d5db; margin: 0 0 6px; }
    .tab { font-size: 11px; color: var(--dat-muted); margin: 0 0 12px; line-height: 1.35; }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 44px;
      padding: 8px 14px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 700;
      text-decoration: none;
      transition: opacity .15s ease;
    }
    .btn:active { opacity: .88; }
    @media (hover: hover) { .btn:hover { opacity: .92; } }
    .btn.primary {
      color: #0a0a0a;
      background: linear-gradient(135deg, #ff9933, var(--dat-orange));
      border: 1px solid #ff8533;
    }
    .btn.ghost {
      color: var(--dat-text);
      border: 1px solid var(--dat-border);
      background: #0d0d0d;
    }
    .empty { color: var(--dat-muted); text-align: center; padding: 40px; }
    footer {
      margin-top: 28px;
      padding-top: 16px;
      border-top: 1px solid var(--dat-border);
      font-size: 11px;
      line-height: 1.45;
      color: var(--dat-muted);
    }
"""
