# 需求：AI 收集报价数据

> 路径：`v2/requirements/quote-ai-collect.md`  
> 实现：`v2/app/quote_web.py`（由 `debug_web` 挂载）、`v2/app/address_ai.py`（Gemini）

## 目的

通过**多轮对话**从用户（含可对外分享的页面）收集**报价所需字段**，写入 `load` 表，与 Sheet 导入、`schema-load.md` 中的 `pending_quote` / `quoted` 等业务状态一致。功能侧重**数据采集与引导补全**，不承诺在对话内完成计费或正式报价输出。

## 范围

- **在内**：`GET /quote` 对话页、`POST /quote/api/message` JSON API、首轮生成报价编号、槽位合并写库、缺项中文追问、Gemini 抽取与无密钥或 API 失败时的简单规则兜底。
- **不在内**：对话页上的**数据清空**、返回 Debug 或其它内部导航（页面定位为可给客户使用，不包含运维操作入口）；正式鉴权、独立域名部署、与 Sheet 的双向实时同步。

**运维清空**：仅删除「quote 来源」的 `load` 行由 Debug **quote tab** 负责（见 `debug-web.md`），不在本页提供。

## 入口与导航

- **调试侧**：Debug 应用（见 `debug-web.md`）顶栏与首页操作区提供「**AI 收集报价数据**」链接至 `/quote`；点击时在**新浏览器标签**打开，保留当前 Debug 页。
- **对外**：可直接访问与 Debug **同源**的 `/quote`（同一 FastAPI 进程、同一路由前缀）。

## 页面与文案

- 浏览器标题、顶栏品牌与主标题统一为 **「AI 收集报价数据」**。
- 说明文案面向客户：自然语言描述需求、多轮确认、首轮回复后生成报价编号并请用户保存。
- 不在此页暴露 `load`、`source_tabs` 等实现术语给用户。
- 助手回复中状态展示使用客户可读文案（如「信息收集中」「已记录报价信息」），不直接输出内部 `status` 枚举英文原文。

## API

### `POST /quote/api/message`

- **请求体**（JSON）：`quote_no`（可选，字符串；首轮为空）、`message`（必填，非空 trimmed）。
- **行为**：
  - 若未带 `quote_no`：生成新主键（格式 `AI-` + UTC 时间戳 + `-` + 4 位十六进制），插入 `load` 占位行后处理消息。
  - 若带 `quote_no` 且库中不存在：返回 404。
  - 每条消息：用当前行槽位 + 用户消息调用抽取逻辑，**非空字段覆盖合并**，写回 `load`，返回助手 `reply` 及 `quote_no`、`slots`、`missing`、`warning`（如 Gemini 不可用或 HTTP 错误时的简要说明）。
- **响应**（成功）：JSON；错误场景返回 `detail`（如 404、422）。

### `GET /quote`

- 返回对话页 HTML；前端通过 `fetch` 调用 `/quote/api/message`（JSON）。

## 数据与字段

- **表**：`load`（定义见 `schema-load.md`）。
- **来源标记**：新建行 `source_tabs = 'quote'`（与 tab 过滤 `instr(',' || source_tabs || ',', ',quote,') > 0` 一致）。
- **收集字段**（槽位键与 `load` 列一致）：
  - `customer_name`、`ship_from_raw`、`ship_to_raw`、`commodity_desc`
  - `weight_raw`、`volume_raw`（**至少填一**才算该项齐备）
  - `customer_quote_raw`、`driver_rate_raw`（可选；参与状态切换，见下）
- **报价编号**：`quote_no`（`AI-…` 前缀），在对话中告知用户以便跟进。

## 状态规则

- `customer_quote_raw` 与 `driver_rate_raw` **均为空**时：`status = 'pending_quote'`。
- **任一非空**时：`status = 'quoted'`（与 `sheet-import.md` 中 quote tab P/U 有值 → `quoted` 对齐）。

## 配置与环境变量（Gemini）

以下与地址校验、参与方抽取等共用（`address_ai.gemini_api_key()` / `gemini_model()`），**每次读 Key 前会 `load_env()`**。

| 变量 | 说明 |
|------|------|
| `GEMINI_API_KEY` | 主密钥；可为空时试 `V2_GEMINI_API_KEY` |
| `AI_ADDRESS_ENABLED` / `V2_AI_ADDRESS_ENABLED` | 若为 `0`/`false`/`off` 等则关闭 AI 路径 |
| `AI_ADDRESS_MODEL` / `V2_AI_ADDRESS_MODEL` | 模型名；**默认 `gemini-2.5-flash`** |

**文件加载**（`v2/app/settings.py`）：

- 按顺序加载 `v2/config/.env`（`override=False`）与 `v2/config/.env.local`（`override=True`）。
- **仅 `config/.env` 与 `config/.env.local` 会加载**；**`config/.env.example` 不会自动加载**（需复制为 `.env`）。
- **补洞**：若 shell 中某变量已存在但为空字符串，`load_dotenv` 可能不写入文件中的值；实现对 `config/.env` 再做一轮 **「仅填补未设置或全空白」** 的合并，避免「文件里有 Key 仍报 MISSING」。

**模型弃用**：`gemini-2.0-flash` 等旧 ID 对新开 API 项目可能返回 **404**；应使用当前文档推荐的 Flash 型号（见 Google AI Studio / Gemini API 模型列表），并在 `.env` 中设置 `AI_ADDRESS_MODEL`。

**无密钥或 API 失败**：对话仍返回 200；对 `weight_raw` / `volume_raw` 做简单正则兜底；`warning` 告知原因（如无 Key、HTTP 错误摘要）。

## AI 提示策略

- 仅根据用户**明确提供**的内容更新字段，禁止编造地址或数字；模型输出为 JSON，键为上述槽位名。
- 实现细节与 prompt 文本以 `quote_web.py` 为准。

## 实现参考

- 路由与页面：`v2/app/quote_web.py`（`debug_web.include_router`）。
- 库：`v2/app/db.py`（`clear_load_quote_only` 供 Debug quote tab「清空数据」使用，**不在** `/quote` 暴露）。

## 验收要点

- 从 Debug 新标签打开 `/quote` 可完成多轮对话；首轮返回 `AI-` 报价编号。
- 必填槽位未齐时，回复列出**中文**缺项；齐备后提示保存编号并可继续补费用类字段。
- 填写客户/司机报价相关字段后，`load.status` 为 `quoted`，否则为 `pending_quote`。
- 客户页面无清空入口、无指向 `/debug` 的链接。
- 配置正确时 Gemini 可抽取字段；缺 Key 或模型 404 时有可理解的 `warning` 与规则兜底。
