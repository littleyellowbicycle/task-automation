# 企业微信任务自动化系统 - 项目规划

> 从企业微信群捕获任务消息 → LLM分析 → 用户确认 → OpenCode执行 → 飞书记录

## 一、项目目标

构建一个自动化流水线：从企业微信群捕获任务消息 → LLM分析 → 用户确认 → OpenCode执行代码生成 → 飞书多维表格记录

## 二、技术架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           用户 (你)                                         │
│                  确认/取消任务 │  查看飞书记录                               │
└───────────────────────────────┬─────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      主流程编排器 (WorkflowOrchestrator)                     │
│    状态机管理 │ 事件驱动 │ 错误恢复 │ 日志记录                              │
└──────────┬──────────┬──────────┬──────────┬──────────┬────────────────────┘
           │          │          │          │          │
           ▼          ▼          ▼          ▼          ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Webhook     │ │   LLM        │ │    任务      │ │   OpenCode   │ │    飞书      │
│  消息接收    │ │   调度器     │ │    分析器    │ │   执行器     │ │    记录器    │
│              │ │              │ │              │ │              │ │              │
│  FastAPI     │ │  Ollama+     │ │  消息解析    │ │  代码生成    │ │  多维表格    │
│  端点        │ │  Claude路由  │ │  摘要生成    │ │  执行        │ │  记录        │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

## 三、核心模块

| 模块 | 职责 | 关键类/函数 |
|------|------|-------------|
| **wechat_listener** | 接收企微群消息 | `WebhookServer`, `MessageParser` |
| **llm_router** | LLM智能路由 (本地/云端) | `LLMRouter`, `OllamaProvider`, `ClaudeProvider` |
| **task_analyzer** | 任务分析和摘要提取 | `TaskAnalyzer` |
| **code_executor** | OpenCode调用封装 | `CodeExecutor` |
| **feishu_recorder** | 飞书多维表格记录 | `FeishuClient`, `TaskRecord` |
| **decision_manager** | 用户决策确认 | `DecisionManager` |
| **workflow_orchestrator** | 主流程编排 | `WorkflowOrchestrator` |
| **config** | 配置和日志管理 | `ConfigManager` |

## 四、完整流程

```
1️⃣ 捕获消息
┌─────────────┐
│ 企微群机器人 │ ──POST──→ Webhook服务器 ──→ 消息解析
└─────────────┘
     │
     ▼
2️⃣ 过滤识别
┌─────────────────────────────────────┐
│ 关键词: "项目发布"、"需求"、"开发任务" │ ── 匹配 ──→ 进入处理流程
│ 排除词: "测试"、"内部"              │ ── 匹配 ──→ 忽略
└─────────────────────────────────────┘
     │
     ▼
3️⃣ LLM分析
┌─────────────────────────────────────┐
│ • 提取需求摘要 (50字内)             │
│ • 识别技术栈 (Python/React/...)     │
│ • 提取核心功能点                    │
│ • 评估复杂度 (simple/medium/complex)│
└─────────────────────────────────────┘
     │
     ▼
4️⃣ 用户确认
┌─────────────────────────────────────┐
│ 发送确认消息到企微私聊:             │
│ 📋 任务摘要: xxx                    │
│ 🛠️ 技术栈: xxx                      │
│ ⚡ 功能点: xxx                       │
│                                     │
│ 回复 "确认" 执行 / "取消" 终止      │
│ ⏱️ 超时: 5分钟                       │
└─────────────────────────────────────┘
     │
     ▼
5️⃣ OpenCode执行
┌─────────────────────────────────────┐
│ • 转换任务为OpenCode指令            │
│ • 设置工作目录                      │
│ • 执行代码生成                      │
│ • 捕获执行结果和仓库链接            │
└─────────────────────────────────────┘
     │
     ▼
6️⃣ 飞书记录
┌─────────────────────────────────────┐
│ 多维表格记录:                        │
│ • task_id: 任务ID                   │
│ • raw_message: 原始消息             │
│ • summary: LLM摘要                  │
│ • tech_stack: 技术栈                │
│ • status: 状态流转                  │
│ • code_repo_url: 代码仓库链接        │
│ • created_at/updated_at: 时间       │
└─────────────────────────────────────┘
```

## 五、LLM混合调度策略

### 复杂度判断规则

| 复杂度 | 判断条件 | 路由 |
|--------|----------|------|
| **Simple** | 单一功能、明确技术栈、无复杂逻辑 | Ollama (本地) |
| **Medium** | 2-3个功能点、需技术选型 | Ollama (本地) |
| **Complex** | 多功能、复杂逻辑、需要架构设计 | Claude (云端) |

### Fallback机制
如果Ollama不可用，自动切换到Claude/GPT云端API。

## 六、消息过滤规则

```yaml
wechat:
  filter:
    include:
      - "项目发布"
      - "需求"
      - "开发任务"
      - "新功能"
      - "做一个"
    exclude:
      - "测试"
      - "[内部]"
      - "demo"
```

## 七、飞书多维表格结构

| 字段名 | 类型 | 说明 |
|--------|------|------|
| task_id | 文本 | 任务唯一ID (UUID) |
| raw_message | 文本 | 原始消息内容 |
| summary | 文本 | LLM生成的摘要 |
| tech_stack | 多选 | 技术栈列表 |
| core_features | 多选 | 核心功能点 |
| status | 单选 | pending/approved/executing/completed/failed |
| code_repo_url | 链接 | 代码仓库链接 |
| created_at | 创建时间 | 创建时间 |
| updated_at | 修改时间 | 更新时间 |

### 状态流转
```
pending → approved → executing → completed
                   ↘           → failed
                     (取消)
```

## 八、配置管理

所有敏感信息通过环境变量管理：

```bash
# 飞书
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_TABLE_ID=xxx

# LLM - Claude
ANTHROPIC_API_KEY=sk-ant-xxx

# LLM - OpenAI (备用)
OPENAI_API_KEY=sk-xxx

# Ollama (本地)
OLLAMA_BASE_URL=http://localhost:11434

# Webhook
WECHAT_HOOK_TOKEN=xxx
```

## 九、部署架构

### 方案A: 云服务器 (推荐长期)

云服务器 (1核1G, ~30元/月)
├── TaskLoop应用 (FastAPI, 端口: 8080)
├── Ollama (可选, 本地LLM, 端口: 11434)
└── 公网IP/域名 → 企微Webhooks回调

### 方案B: 本地 + 内网穿透 (免费)

你的电脑 → 内网穿透工具 (frp/ngrok) → 公网URL → 企微Webhooks回调

### 免费内网穿透工具

| 工具 | 免费额度 | 适合场景 |
|------|----------|----------|
| ngrok | 1个隧道/分钟断开 | 开发测试 |
| cpolar | 随机URL | 临时使用 |
| frp | 完全免费 | 自建穿透 |
| Cloudflare Tunnel | 免费 | 长期稳定 |

## 十、文件结构

```
TaskLoop/
├── src/
│   ├── config/              # 配置管理
│   │   ├── __init__.py
│   │   └── manager.py      # ConfigManager
│   ├── wechat_listener/    # Webhook接收
│   │   ├── __init__.py
│   │   ├── server.py       # FastAPI服务器
│   │   └── parser.py       # 消息解析
│   ├── llm_router/          # LLM调度
│   │   ├── __init__.py
│   │   ├── base.py         # 抽象基类
│   │   ├── ollama.py       # Ollama Provider
│   │   ├── anthropic.py   # Claude Provider
│   │   └── router.py       # 路由逻辑
│   ├── task_analyzer/       # 任务分析
│   │   ├── __init__.py
│   │   └── analyzer.py     # TaskAnalyzer
│   ├── code_executor/       # OpenCode执行
│   │   ├── __init__.py
│   │   └── executor.py     # CodeExecutor
│   ├── feishu_recorder/     # 飞书记录
│   │   ├── __init__.py
│   │   ├── client.py       # FeishuClient
│   │   └── models.py       # TaskRecord
│   ├── decision_manager/    # 决策确认
│   │   ├── __init__.py
│   │   └── manager.py      # DecisionManager
│   ├── workflow_orchestrator/ # 流程编排
│   │   ├── __init__.py
│   │   └── orchestrator.py # WorkflowOrchestrator
│   ├── utils/               # 工具函数
│   │   └── __init__.py
│   └── exceptions/          # 异常定义
│       └── __init__.py
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
├── config/
│   └── config.yaml
├── CLAUDE.md               # OpenCode上下文
├── README.md
├── requirements.txt
├── .env.example
└── main.py                 # 入口
```

## 十一、关键决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 消息捕获 | Webhook | 官方支持、无封号风险、只需新消息 |
| 代码Agent | OpenCode | 开源、多模型支持、本地LLM友好 |
| LLM | 混合方案 | 简单任务用Ollama(免费快)、复杂用Claude |
| 环境 | Windows | 符合用户环境 |
| 规模 | 个人使用 | 无需复杂权限管理 |

## 十二、技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| Web框架 | FastAPI | >=0.109.0 |
| 飞书SDK | lark-oapi | >=1.3.0 |
| LLM SDK | openai, anthropic | >=1.12.0, >=0.20.0 |
| 配置 | pydantic, pyyaml | >=2.6.0, >=6.0.1 |
| 日志 | loguru | >=0.7.2 |
| 测试 | pytest | >=8.0.0 |

## 十三、安全考虑

### Webhook安全
- ✅ 使用签名验证 (msg_signature)
- ✅ 频率限制 (20条/分钟)
- ✅ 不获取用户隐私信息

### 凭证管理
- ✅ 所有凭证通过环境变量管理
- ✅ 不硬编码任何密钥
- ✅ .env文件加入.gitignore

### 执行安全
- ✅ 命令白名单
- ✅ 路径限制
- ✅ 危险操作拦截
