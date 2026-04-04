"""
EW 界面主题：未来简约（冷色深底、天青强调、细线、大留白、轻阴影）。
"""

# 登录 / 注册 / 用户管理等仅用 LAYOUT_SHELL_CSS、未单独设 body 的页面（避免浅字叠浏览器白底）
AUTH_PAGE_BODY_CSS = """
    html, body {
      margin: 0;
      min-height: 100dvh;
      font-family: "DM Sans", "Inter", system-ui, sans-serif;
      background: radial-gradient(ellipse 100% 65% at 50% -22%, rgba(56, 189, 248, 0.1), transparent 52%),
        linear-gradient(168deg, #07080c 0%, #0c1018 48%, #080a0f 100%);
      color: #e8edf4;
      -webkit-font-smoothing: antialiased;
    }
"""

# 左侧导航 + 主区（首页、订单等共用；置于各页 CSS 之前）
LAYOUT_SHELL_CSS = """
    :root {
      --ew-accent: #38bdf8;
      --ew-accent-dim: #0ea5e9;
      --ew-border: rgba(255, 255, 255, 0.07);
      --ew-border-hover: rgba(255, 255, 255, 0.12);
      --ew-text: #e8edf4;
      --ew-muted: #8b98a8;
      --ew-nav-bg: rgba(10, 12, 18, 0.88);
    }
    .ew-shell {
      display: flex;
      min-height: 100dvh;
      width: 100%;
      max-width: 100%;
    }
    .ew-nav {
      flex: 0 0 clamp(200px, 22vw, 240px);
      width: clamp(200px, 22vw, 240px);
      max-width: 100%;
      background: var(--ew-nav-bg);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border-right: 1px solid var(--ew-border);
      padding: max(16px, env(safe-area-inset-top)) 16px 24px max(14px, env(safe-area-inset-left));
      display: flex;
      flex-direction: column;
      gap: 20px;
      position: sticky;
      top: 0;
      align-self: flex-start;
      height: 100dvh;
      overflow-y: auto;
    }
    .ew-nav-brand {
      display: flex;
      align-items: baseline;
      gap: 8px;
      text-decoration: none;
      font-weight: 700;
      letter-spacing: -0.03em;
      color: var(--ew-text);
    }
    .ew-nav-brand-mark {
      color: var(--ew-accent);
      font-size: 19px;
      font-weight: 800;
      letter-spacing: -0.04em;
    }
    .ew-nav-brand-sub {
      font-size: 10px;
      font-weight: 600;
      color: var(--ew-muted);
      text-transform: uppercase;
      letter-spacing: 0.14em;
    }
    .ew-nav-list {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .ew-nav-link {
      display: block;
      padding: 11px 14px;
      border-radius: 10px;
      text-decoration: none;
      font-size: 13px;
      font-weight: 600;
      color: #c8d0dc;
      border: 1px solid transparent;
      transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
    }
    .ew-nav-link:hover {
      background: rgba(56, 189, 248, 0.06);
      color: #f1f5f9;
      border-color: var(--ew-border-hover);
    }
    .ew-nav-link--active {
      color: #f0f9ff;
      background: rgba(56, 189, 248, 0.12);
      border-color: rgba(56, 189, 248, 0.28);
      box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.08);
    }
    .ew-nav-auth {
      margin-top: auto;
      padding-top: 16px;
      border-top: 1px solid var(--ew-border);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .ew-nav-auth--row {
      flex-direction: row;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }
    .ew-nav-user {
      font-size: 11px;
      font-weight: 600;
      color: #bae6fd;
      padding: 0 2px;
      letter-spacing: 0.02em;
    }
    .ew-nav-link--sub {
      font-size: 12px;
      font-weight: 600;
      color: var(--ew-muted);
    }
    .ew-nav-link--sub:hover {
      color: var(--ew-text);
      background: rgba(255, 255, 255, 0.04);
    }
    .ew-main {
      flex: 1 1 auto;
      min-width: 0;
      padding: max(12px, env(safe-area-inset-top)) max(20px, env(safe-area-inset-right))
        max(28px, env(safe-area-inset-bottom)) max(20px, env(safe-area-inset-left));
    }
    @media (max-width: 900px) {
      .ew-shell { flex-direction: column; min-height: 0; }
      .ew-nav {
        flex: none;
        width: 100%;
        max-width: none;
        height: auto;
        min-height: 0;
        position: relative;
        border-right: none;
        border-bottom: 1px solid var(--ew-border);
        flex-direction: row;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px 14px;
        padding: max(12px, env(safe-area-inset-top)) 14px 12px 14px;
        margin-top: 0;
      }
      .ew-nav-auth { margin-top: 0; padding-top: 0; border-top: none; }
      .ew-nav-list {
        flex-direction: row;
        flex-wrap: wrap;
        flex: 1;
        justify-content: flex-end;
        gap: 4px;
      }
      .ew-nav-link { padding: 9px 12px; font-size: 12px; }
    }
"""

# 订单页完整 CSS（供 order_view 内联；勿在外层 f-string 中手写含单花括号的字面量）
ORDER_PAGE_CSS = """
    :root {
      --dat-orange: #38bdf8;
      --dat-orange-dim: #0ea5e9;
      --dat-bg: #090b10;
      --dat-surface: rgba(255, 255, 255, 0.035);
      --dat-surface2: rgba(255, 255, 255, 0.055);
      --dat-border: rgba(255, 255, 255, 0.09);
      --dat-text: #e8edf4;
      --dat-muted: #8b98a8;
      --radius: 12px;
    }
    * { box-sizing: border-box; }
    html { -webkit-text-size-adjust: 100%; }
    body {
      margin: 0;
      min-height: 100dvh;
      font-family: "DM Sans", "Inter", system-ui, sans-serif;
      background:
        radial-gradient(ellipse 100% 70% at 50% -25%, rgba(56, 189, 248, 0.09), transparent 52%),
        radial-gradient(ellipse 60% 40% at 100% 50%, rgba(99, 102, 241, 0.05), transparent 45%),
        linear-gradient(168deg, #07080c 0%, var(--dat-bg) 45%, #06070b 100%);
      color: var(--dat-text);
      -webkit-font-smoothing: antialiased;
      padding: 0;
    }
    .oc-wrap { max-width: min(1280px, 100%); margin: 0 auto; }
    .oc-top {
      display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
      gap: 10px; margin-bottom: 16px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
      padding-bottom: 14px;
    }
    .oc-top h1 {
      font-size: clamp(17px, 4.2vw, 22px); font-weight: 700; letter-spacing: -0.03em; margin: 0;
      color: #f1f5f9;
    }
    .oc-brand { color: var(--dat-orange); }
    .oc-title-sub { color: #e5e7eb; font-weight: 700; }
    .oc-top a {
      color: var(--dat-orange);
      text-decoration: none; font-size: 13px; font-weight: 700;
      padding: 6px 4px;
    }
    .oc-top a:hover { text-decoration: underline; }
    .oc-top-actions {
      flex: 1 1 280px;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 8px;
      min-width: 0;
    }
    .oc-sync-meta {
      margin: 0;
      font-size: 11px;
      line-height: 1.45;
      color: var(--dat-muted);
      text-align: right;
      max-width: 52ch;
    }
    .oc-sync-meta code { font-size: 10px; color: #7dd3fc; }
    .oc-sync-meta--muted { max-width: 48ch; }
    .oc-sync-form {
      display: flex;
      flex-wrap: wrap;
      align-items: flex-end;
      justify-content: flex-end;
      gap: 8px;
    }
    .oc-sync-form--inline { align-items: center; align-self: center; }
    .oc-sync-admin {
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.04em;
      color: #bae6fd;
      margin-right: 2px;
    }
    .oc-sync-token { display: flex; flex-direction: column; gap: 4px; font-size: 11px; font-weight: 700; color: #d4d4d8; }
    .oc-sync-token input {
      min-width: 200px;
      max-width: 280px;
      padding: 9px 12px;
      font-size: 13px;
      border-radius: 10px;
      border: 1px solid var(--dat-border);
      background: rgba(0, 0, 0, 0.35);
      color: #f1f5f9;
    }
    .oc-sync-btn {
      padding: 9px 16px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.04em;
      border-radius: 10px;
      border: 1px solid rgba(56, 189, 248, 0.45);
      background: linear-gradient(165deg, rgba(56, 189, 248, 0.22), rgba(14, 165, 233, 0.55));
      color: #020617;
      cursor: pointer;
      transition: filter 0.15s ease, box-shadow 0.15s ease;
      box-shadow: 0 1px 0 rgba(255, 255, 255, 0.12) inset;
    }
    .oc-sync-btn:hover { filter: brightness(1.06); }
    .oc-sync-btn:active { filter: brightness(0.96); }
    .oc-sync-flash {
      font-size: 13px;
      font-weight: 700;
      padding: 10px 12px;
      border-radius: 8px;
      margin-bottom: 10px;
    }
    .oc-sync-flash--ok {
      color: #bbf7d0;
      background: rgba(22, 163, 74, 0.2);
      border: 1px solid rgba(74, 222, 128, 0.4);
    }
    .oc-sync-flash--err {
      color: #fecaca;
      background: rgba(127, 29, 29, 0.35);
      border: 1px solid rgba(248, 113, 113, 0.45);
    }
    .oc-db-fallback {
      font-size: 12px;
      line-height: 1.55;
      color: #e0e7ef;
      background: rgba(56, 189, 248, 0.08);
      border: 1px solid rgba(56, 189, 248, 0.22);
      border-radius: 10px;
      padding: 12px 14px;
      margin-bottom: 12px;
    }
    .oc-db-fallback code { font-size: 11px; color: #7dd3fc; }
    .oc-maps-hint {
      font-size: 12px;
      line-height: 1.45;
      color: #fecaca;
      background: rgba(127, 29, 29, 0.35);
      border: 1px solid rgba(248, 113, 113, 0.45);
      border-radius: 8px;
      padding: 8px 10px;
      margin-bottom: 10px;
    }
    .oc-maps-hint code { font-size: 11px; color: #fecaca; }
    .oc-debug {
      font-size: 11px;
      line-height: 1.4;
      color: #d1d5db;
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 12px;
    }
    .oc-debug strong { display: block; margin-bottom: 6px; color: #94a3b8; font-size: 12px; }
    .oc-debug pre {
      margin: 8px 0 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 11px;
      color: #e2e8f0;
    }
    .oc-card {
      background: var(--dat-surface);
      border: 1px solid var(--dat-border);
      border-radius: var(--radius);
      padding: 12px 14px;
      margin-bottom: 12px;
      box-shadow: 0 1px 0 rgba(255, 255, 255, 0.04) inset, 0 12px 40px rgba(0, 0, 0, 0.25);
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
      background: rgba(56, 189, 248, 0.12); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.35);
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
    .oc-a--open {
      color: #e4e4e7;
      background: rgba(82, 82, 91, 0.28);
      border: 1px solid rgba(161, 161, 170, 0.5);
    }
    /* Land use：仓库橙 / 住家蓝 / 商业绿 / 未知红（与 .oc-a 同尺寸） */
    .oc-lu {
      font-size: 10px;
      font-weight: 800;
      padding: 2px 8px;
      border-radius: 999px;
      letter-spacing: .02em;
      text-transform: lowercase;
    }
    .oc-lu--warehouse {
      color: #7dd3fc;
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.38);
    }
    .oc-lu--residential {
      color: #93c5fd;
      background: rgba(37, 99, 235, 0.2);
      border: 1px solid rgba(96, 165, 250, 0.45);
    }
    .oc-lu--commercial {
      color: #bbf7d0;
      background: rgba(22, 163, 74, 0.22);
      border: 1px solid rgba(74, 222, 128, 0.4);
    }
    .oc-lu--unknown {
      color: #fecaca;
      background: rgba(220, 38, 38, 0.25);
      border: 1px solid rgba(248, 113, 113, 0.45);
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
      border-radius: 12px;
      font-size: 11px;
      font-weight: 700;
      text-decoration: none;
      color: #020617;
      background: linear-gradient(165deg, rgba(125, 211, 252, 0.95), #0ea5e9);
      border: 1px solid rgba(56, 189, 248, 0.55);
      writing-mode: vertical-rl;
      text-orientation: mixed;
      letter-spacing: 0.14em;
      -webkit-tap-highlight-color: transparent;
      box-shadow: 0 1px 0 rgba(255, 255, 255, 0.2) inset;
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
    .oc-from h3 { color: #7dd3fc; }
    .oc-to h3 { color: #93c5fd; }
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
    .oc-addr-type {
      margin-top: 6px;
      padding-top: 6px;
      border-top: 1px dashed rgba(46, 46, 46, 0.95);
      font-size: 10px;
      line-height: 1.4;
      color: var(--dat-muted);
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px 8px;
    }
    .oc-at-k { font-weight: 800; letter-spacing: 0.04em; color: #9ca3af; }
    .oc-at-v { color: #d1d5db; word-break: break-word; }
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
      font-weight: 700;
      letter-spacing: .08em;
      color: var(--dat-orange);
    }
    .oc-km { margin-bottom: 8px; display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
    .oc-km:last-child { margin-bottom: 0; }
    .oc-km-label { font-size: 10px; font-weight: 800; color: var(--dat-muted); }
    .oc-km-val {
      font-size: clamp(15px, 3.6vw, 17px);
      font-weight: 700;
      color: #f8fafc;
      letter-spacing: -0.02em;
    }
    .oc-pnl {
      margin-top: 8px;
      padding: 8px 10px;
      border-radius: 10px;
      border: 1px solid rgba(56, 189, 248, 0.22);
      background: linear-gradient(165deg, rgba(56, 189, 248, 0.08), rgba(8, 10, 16, 0.92));
    }
    .oc-pnl h3 {
      margin: 0 0 6px;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: .07em;
      color: #7dd3fc;
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
      font-weight: 700;
      letter-spacing: .07em;
      color: #93c5fd;
    }
    .oc-dims {
      font-size: 13px;
      font-weight: 500;
      line-height: 1.45;
      color: #f1f5f9;
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
    .oc-chip--miss {
      border-color: rgba(248, 113, 113, 0.55) !important;
      background: rgba(127, 29, 29, 0.22) !important;
      box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.15) inset;
    }
    .oc-chip--miss .v { color: #fecaca; }
    .oc-booking {
      margin-top: 8px;
      padding: 8px 10px;
      border-radius: 8px;
      border: 1px solid rgba(59, 130, 246, 0.35);
      background: linear-gradient(165deg, rgba(37, 99, 235, 0.1), rgba(20, 20, 20, 0.95));
    }
    .oc-booking h3 {
      margin: 0 0 6px;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .06em;
      color: #93c5fd;
    }
    .oc-bk-warn {
      font-size: 11px;
      font-weight: 700;
      line-height: 1.45;
      color: #fecaca;
      background: rgba(127, 29, 29, 0.35);
      border: 1px solid rgba(248, 113, 113, 0.45);
      border-radius: 8px;
      padding: 8px 10px;
      margin-bottom: 8px;
    }
    .oc-bk-warn code { font-size: 10px; color: #fde68a; }
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
    .oc-dat { color: #94a3b8; }
    .empty { color: var(--dat-muted); font-style: italic; }
    .oc-empty { text-align: center; color: var(--dat-muted); padding: 24px 12px; font-size: 14px; }
"""

HOME_PAGE_CSS = """
    :root {
      --dat-orange: #38bdf8;
      --dat-bg0: #07080c;
      --dat-bg1: #0c1018;
      --dat-card: rgba(255, 255, 255, 0.04);
      --dat-border: rgba(255, 255, 255, 0.09);
      --dat-text: #e8edf4;
      --dat-muted: #8b98a8;
    }
    * { box-sizing: border-box; }
    html { -webkit-text-size-adjust: 100%; }
    body {
      margin: 0;
      min-height: 100dvh;
      font-family: "DM Sans", "Inter", system-ui, sans-serif;
      background:
        radial-gradient(ellipse 100% 65% at 50% -20%, rgba(56, 189, 248, 0.1), transparent 50%),
        radial-gradient(ellipse 50% 35% at 90% 20%, rgba(99, 102, 241, 0.06), transparent 50%),
        linear-gradient(172deg, var(--dat-bg0), var(--dat-bg1) 55%, #080a0f);
      color: var(--dat-text);
      -webkit-font-smoothing: antialiased;
      padding: 0;
    }
    .wrap { max-width: min(1320px, 100%); margin: 0 auto; padding-bottom: 32px; }
    .hero {
      position: relative;
      padding-bottom: clamp(12px, 2vw, 20px);
      margin-bottom: clamp(24px, 4vw, 36px);
      border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    }
    .hero::before {
      content: "";
      position: absolute;
      left: 0;
      right: 0;
      top: -6px;
      height: 1px;
      border-radius: 1px;
      background: linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.45), rgba(99, 102, 241, 0.35), transparent);
      opacity: 1;
    }
    header { margin-bottom: 0; }
    .hero-sub {
      font-size: clamp(15px, 2.8vw, 18px);
      font-weight: 500;
      line-height: 1.55;
      color: #b8c5d4;
      max-width: 42rem;
      margin: 0 0 12px;
      letter-spacing: -0.02em;
    }
    .hero-cta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin: 16px 0 18px;
    }
    .hero-cta .btn { min-height: 46px; padding: 10px 18px; border-radius: 12px; }
    .hero-strip {
      list-style: none;
      margin: 0 0 16px;
      padding: 0;
      display: flex;
      flex-wrap: wrap;
      gap: 10px 20px;
      font-size: 12px;
      font-weight: 700;
      color: #9ca3af;
      letter-spacing: 0.04em;
    }
    .hero-strip li {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .hero-strip li::before {
      content: "";
      width: 5px;
      height: 5px;
      border-radius: 999px;
      background: linear-gradient(135deg, #7dd3fc, var(--dat-orange));
      flex-shrink: 0;
      opacity: 0.9;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 5px 12px;
      border-radius: 999px;
      font-size: 10px;
      font-weight: 600;
      letter-spacing: .12em;
      text-transform: uppercase;
      color: #7dd3fc;
      background: rgba(56, 189, 248, 0.08);
      border: 1px solid rgba(56, 189, 248, 0.25);
      margin-bottom: 14px;
    }
    h1 {
      font-size: clamp(26px, 5vw, 40px);
      font-weight: 700;
      letter-spacing: -0.04em;
      line-height: 1.1;
      margin: 0 0 14px;
      color: #f1f5f9;
    }
    h1 .dat { color: var(--dat-orange); }
    .lead {
      font-size: clamp(13px, 3.2vw, 15px);
      line-height: 1.55;
      color: var(--dat-muted);
      max-width: 52ch;
      margin: 0 0 0;
    }
    .section-head {
      margin-bottom: 14px;
    }
    .section-head h2 {
      font-size: clamp(16px, 2.5vw, 20px);
      font-weight: 600;
      letter-spacing: -0.02em;
      color: #f1f5f9;
      margin: 0 0 8px;
    }
    .section-desc {
      font-size: 13px;
      line-height: 1.45;
      color: var(--dat-muted);
      margin: 0;
      max-width: 56ch;
    }
    .meta { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; font-size: 13px; margin-top: 4px; }
    .meta a { color: #7dd3fc; text-decoration: none; font-weight: 600; }
    .meta a:hover { text-decoration: underline; }
    .meta span { color: var(--dat-muted); }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(min(100%, 240px), 1fr));
      gap: 12px;
    }
    @media (max-width: 480px) { .grid { grid-template-columns: 1fr; gap: 10px; } }
    .card {
      padding: 16px 18px;
      border-radius: 14px;
      background: var(--dat-card);
      border: 1px solid var(--dat-border);
      box-shadow: 0 1px 0 rgba(255, 255, 255, 0.04) inset, 0 16px 48px rgba(0, 0, 0, 0.22);
      transition: border-color .2s ease, box-shadow .2s ease;
    }
    @media (hover: hover) {
      .card:hover {
        border-color: rgba(56, 189, 248, 0.22);
        box-shadow: 0 1px 0 rgba(255, 255, 255, 0.05) inset, 0 20px 50px rgba(0, 0, 0, 0.28);
      }
    }
    .card-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 10px;
    }
    .pill {
      font-size: 12px;
      font-weight: 600;
      color: #020617;
      background: linear-gradient(135deg, rgba(125, 211, 252, 0.95), #0ea5e9);
      padding: 4px 10px;
      border-radius: 8px;
      letter-spacing: 0.02em;
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
      color: #020617;
      background: linear-gradient(165deg, rgba(125, 211, 252, 0.98), #0ea5e9);
      border: 1px solid rgba(56, 189, 248, 0.5);
      font-weight: 600;
      letter-spacing: 0.03em;
      box-shadow: 0 1px 0 rgba(255, 255, 255, 0.15) inset;
    }
    .btn.ghost {
      color: var(--dat-text);
      border: 1px solid var(--dat-border);
      background: rgba(255, 255, 255, 0.03);
      font-weight: 500;
    }
    .empty { color: var(--dat-muted); text-align: center; padding: 40px; }
    footer {
      margin-top: 28px;
      padding-top: 16px;
      border-top: 1px solid var(--dat-border);
      font-size: 11px;
      line-height: 1.5;
      color: var(--dat-muted);
    }
    footer a.ref {
      color: #7dd3fc;
      text-decoration: none;
      font-weight: 500;
    }
    footer a.ref:hover { text-decoration: underline; }
"""
