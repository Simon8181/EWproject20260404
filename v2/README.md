# EW v2

从零重做版本。第一阶段先完成 `load` 数据底座与一次性导入。

## 目录
- `app/` 应用与导入逻辑
- `config/` 环境与映射配置
- `requirements/` 功能需求文档（短英文名，一功能一文件；索引见 `requirements/README.md`）
- `tests/` 测试
- `data/` 本地 sqlite 数据库（运行时生成）

## 安装
```bash
pip install -r requirements.txt
```

## 配置
1. 复制 `config/.env.example` 为 `config/.env`
2. 配置 `GOOGLE_APPLICATION_CREDENTIALS`（service account json）
3. 编辑 `config/load_mapping.yaml`（我已给出初版，你可手动调整列名和规则）
4. 把 `spreadsheet_id` 改成你的 Sheet ID

## 当前导入列范围
- 仅导入已定义列：`A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P,U`
- 明确不导入：`Q,R,S` 及其它未定义列
- A 列颜色在 `报价 quote`、`下单 BOL need booking` 参与状态判定（对齐 `text1` §2）：
  - `red -> ordered`（待找车）
  - `green -> carrier_assigned`（已找到车 / truck_found；**禁止**再映射到 `ready_to_pick`）
- **仅 quote、且无 A 列色**：`P` 与 `U` 皆空 → `pending_quote`；任一非空 → `quoted`。
- **重导入**：若 `load` 上已有运营字段（提货/送达 ETA、时区、承运备注、`cargo_ready`、操作者审计等），则不再用 Sheet 覆盖 `status`（见 `text1` 附录 B）。

## Debug 运营字段与提醒
- `load` 上仍有运营列（ETA/时区/备注/审计等），**Sheet 重导入时对 `status` 的保护逻辑也仍在**；当前 **Debug 页不展示运营字段表单**（若需写入可暂时直接改库或以后再加回 UI）。
- 提货超期提醒：浏览器需授权通知；默认每 30 分钟提醒一次，满 24 小时停止弹窗。开发时可打开  
  `http://127.0.0.1:8010/debug?reminder_interval_ms=60000`（或任意 tab 带同一 query）缩短间隔。

## 一次性导入
```bash
python -m app.import_once --trigger initial
```

- 生产语义：默认只导入一次（写导入锁）
- 测试语义：可反复清理后重导

```bash
python -m app.import_once --reset --force-reimport --trigger test-reimport
```

> 安全限制：`APP_ENV=prod` 时禁止 `--reset` 和 `--force-reimport`。

## 调试页面（4 tab + 两个按钮）
启动：
```bash
uvicorn app.debug_web:app --host 127.0.0.1 --port 8010 --reload
```

页面：
- `http://127.0.0.1:8010/debug`（总览 + 按钮）
- `http://127.0.0.1:8010/debug/tab/quote`
- `http://127.0.0.1:8010/debug/tab/order`
- `http://127.0.0.1:8010/debug/tab/complete`
- `http://127.0.0.1:8010/debug/tab/cancel`

各 tab 列表：默认单行展示 **单号 · City, ST ZIP → City, ST ZIP**，点击行展开完整字段；行为见 `requirements/debug-web.md`。

按钮说明：
- `验证地址（全量 I->K）`：对全量 `load` 用 Google Maps 验证 `ship_from_raw -> ship_to_raw`，
  回写里程和场所类型；若地址验证失败，按当前规则会删除该行及其验证日志。
- `仅验证当前 tab`：在各 `tab` 页面单独触发，只处理当前 tab 数据（同样失败即删除）。
- `清空数据（仅 load）`：只清空 `load` 表，不清日志和导入锁
- `导入数据`：触发一次导入（遵守导入锁）

地址 AI 二次修复（Gemini）：
- 仅在 Google 直接验证失败时触发 AI 清洗地址并重试
- 无 `GEMINI_API_KEY` 时自动跳过 AI（不阻断流程）
- 调试页会显示：`ai_retry / ai_conf / origin_norm / dest_norm`
- 推荐变量名（无前缀）：`GOOGLE_MAPS_API_KEY`、`AI_ADDRESS_ENABLED`、`GEMINI_API_KEY`、`AI_ADDRESS_MODEL`
