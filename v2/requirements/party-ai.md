# 需求：参与方信息与地址 AI 抽取

> 路径：`v2/requirements/party-ai.md`

## 目的

在原始地址字段不可靠或需结构化参与方信息时，使用规则与/或大模型（Gemini）从文本中抽取 `shipper`/`consignee` 相关信息，辅助地址校验重试或展示；不替代 Sheet 导入主路径。

## 范围

- **在内**：`party_extract`（规则）、`party_ai`（可选 Gemini）、与 `address_ai` / 校验失败路径的衔接方式（以 `validation_runner` 与地址模块调用链为准）。
- **不在内**：完整 CRM、合同文本解析。

## 功能需求

1. **可配置**：模型名、API Key、开关等由 `settings`/环境变量控制；未配置 AI 时规则路径仍应可工作。
2. **降级**：AI 超时或失败不应导致整个导入管道崩溃；验证批处理中行为以 `validation_runner` 为准。
3. **输出**：结构化字段写回或供重试使用，具体字段集合以代码与校验模块契约为准。

## 非功能约束

- 不对第三方 API 密钥打点日志；注意 PII 出网合规（由使用方环境负责）。

## 实现参考

- 代码：`v2/app/party_extract.py`、`v2/app/party_ai.py`、`v2/app/address_ai.py`
- 单测：`v2/tests/test_party_extract.py`、`v2/tests/test_party_ai.py`（若存在）

## 验收要点

- 无 `GEMINI_API_KEY` 时关键路径仍可通过或明确跳过 AI 步骤。
- 与地址验证任务联调时，抽取结果可观察且可重复（固定输入下）。
