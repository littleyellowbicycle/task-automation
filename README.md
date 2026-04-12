# 企业微信任务自动化系统

> 从企业微信群捕获任务消息 → LLM分析 → 用户确认 → OpenCode执行 → 飞书记录

## 项目概述

本系统通过 API Gateway + Workers 微服务架构，实现从企业微信群消息到代码生成的全链路自动化。网关作为唯一公网入口，负责消息分发和路由，各业务模块通过 REST API 通信，可独立部署和扩展。

## 架构设计

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              外部系统                                        │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│   │  企业微信     │    │   飞书服务器   │    │  用户浏览器   │                  │
│   │  (群消息)     │    │  (卡片回调)   │    │  (管理界面)   │                  │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                  │
└──────────┼───────────────────┼───────────────────┼───────────────────────────┘
           │                   │                   │
           ▼                   ▼                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         API Gateway (公网部署)                               │
│                                                                              │
│   ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐   │
│   │ 消息处理器   │  │  任务管理器   │  │  队列管理器   │  │  消息路由器   │   │
│   │ (校验/去重)  │  │ (状态机)     │  │ (FIFO队列)   │  │ (分发调度)    │   │
│   └─────────────┘  └──────────────┘  └──────────────┘  └───────────────┘   │
│                                                                              │
│   REST API: /api/v1/listener/*  /api/v1/feishu/*  /api/v1/decisions/*      │
│             /api/v1/tasks/*  /api/v1/queue/*  /health                       │
└──────────┬──────────┬──────────┬──────────┬─────────────────────────────────┘
           │          │          │          │
           ▼          ▼          ▼          ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  分析 Worker  │ │  决策 Worker  │ │  执行 Worker  │ │  记录 Worker  │
│              │ │              │ │              │ │              │
│ 消息过滤     │ │ 飞书卡片推送  │ │ OpenCode调用 │ │ 飞书表格记录 │
│ 任务识别     │ │ 用户确认/取消 │ │ 代码生成执行 │ │ 状态通知推送 │
│ LLM分析     │ │ 超时处理     │ │ 结果收集     │ │ Webhook通知  │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

### 核心设计原则

- **网关只做分发**：不执行具体业务逻辑，只负责消息校验、标准化、路由
- **消除内网穿透**：网关部署在公网，飞书回调直接打到网关
- **模块解耦**：各 Worker 通过 REST API 通信，可独立部署和扩展
- **双模式部署**：支持单进程模式（开发）和分布式模式（生产）

## 任务状态流转

```
received → filtering → awaiting_confirmation → approved → executing → recording → completed
                    ↘ cancelled                           ↘ rejected              ↘ failed
                                                          ↘ later (requeue)
                                                          ↘ timeout
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入实际配置
```

### 运行

```bash
# 单进程模式（开发/测试，所有组件在同一进程）
python main.py --mode standalone

# 分布式模式（生产部署）
python main.py --mode gateway          # 公网服务器：启动 API Gateway
python main.py --mode filter-analysis  # 内网服务器：启动分析 Worker
python main.py --mode decision         # 内网服务器：启动决策 Worker
python main.py --mode execution        # 内网服务器：启动执行 Worker
python main.py --mode recording        # 内网服务器：启动记录 Worker

# 可选参数
python main.py --dry-run               # 干跑模式（不实际执行代码）
python main.py --config path/to/config.yaml  # 自定义配置文件
python main.py --log-level DEBUG       # 日志级别
```

### 测试

```bash
# 运行所有单元测试
pytest tests/ -v

# 运行单个测试文件
pytest tests/unit/test_gateway.py -v

# 运行集成测试（需要先启动 gateway）
pytest tests/ -v -m integration

# 带覆盖率报告
pytest tests/ -v --cov=src --cov-report=html
```

## 项目结构

```
.
├── src/
│   ├── gateway/                  # API Gateway
│   │   ├── app.py               # FastAPI 应用
│   │   ├── core/                # 核心组件
│   │   │   ├── message_processor.py  # 消息校验与标准化
│   │   │   ├── task_manager.py       # 任务状态管理
│   │   │   ├── queue_manager.py      # 任务队列管理
│   │   │   └── router.py             # 消息路由分发
│   │   ├── dispatcher/          # 调度器
│   │   │   ├── base.py               # 调度器基类
│   │   │   ├── http_dispatcher.py    # HTTP 调度（分布式模式）
│   │   │   └── inprocess_dispatcher.py  # 进程内调度（单进程模式）
│   │   ├── models/              # 数据模型
│   │   │   ├── messages.py           # 标准消息模型
│   │   │   ├── tasks.py              # 任务状态模型
│   │   │   └── requests.py           # API 请求模型
│   │   └── routes/              # API 路由
│   │       ├── listener.py           # 监听消息接口
│   │       ├── feishu.py             # 飞书回调接口
│   │       ├── decisions.py          # 决策接口
│   │       ├── analysis.py           # 分析接口
│   │       ├── execution.py          # 执行接口
│   │       ├── recording.py          # 记录接口
│   │       ├── tasks.py              # 任务查询接口
│   │       └── queue.py              # 队列状态接口
│   ├── workers/                  # 业务 Workers
│   │   ├── filter_analysis/     # 分析 Worker
│   │   │   ├── app.py                # FastAPI 应用
│   │   │   └── handler.py            # 分析处理器
│   │   ├── decision/            # 决策 Worker
│   │   │   ├── app.py                # FastAPI 应用
│   │   │   └── handler.py            # 决策处理器
│   │   ├── execution/           # 执行 Worker
│   │   │   ├── app.py                # FastAPI 应用
│   │   │   └── handler.py            # 执行处理器
│   │   └── recording/           # 记录 Worker
│   │       ├── app.py                # FastAPI 应用
│   │       └── handler.py            # 记录处理器
│   ├── listener_push/            # 监听层推送客户端
│   ├── config/                   # 配置管理
│   ├── wechat_listener/          # 企业微信消息捕获
│   ├── llm_router/               # LLM 智能路由
│   ├── task_analyzer/            # 任务分析
│   ├── code_executor/            # OpenCode 执行
│   ├── feishu_recorder/          # 飞书记录
│   ├── decision_manager/         # 用户决策确认
│   ├── workflow_orchestrator/    # 旧版流程编排（兼容）
│   ├── exceptions/               # 自定义异常
│   └── utils/                    # 工具函数
├── config/
│   └── config.yaml               # 主配置文件
├── tests/                        # 测试套件
│   ├── unit/                     # 单元测试
│   └── conftest.py               # 测试配置和 fixture
├── docs/
│   └── ARCHITECTURE_V2.md        # 架构设计文档
├── main.py                       # 入口
├── requirements.txt
└── .env.example
```

## API 接口

### Gateway API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/listener/msg` | 接收监听层消息 |
| POST | `/api/v1/feishu/callback` | 飞书事件回调 |
| POST | `/api/v1/decisions` | 提交用户决策 |
| POST | `/api/v1/analysis/done` | 分析完成回调 |
| POST | `/api/v1/execution/done` | 执行完成回调 |
| POST | `/api/v1/execution/progress` | 执行进度更新 |
| POST | `/api/v1/recording/done` | 记录完成回调 |
| GET | `/api/v1/tasks/{task_id}` | 查询任务状态 |
| GET | `/api/v1/tasks` | 列出所有任务 |
| GET | `/api/v1/queue/status` | 队列状态 |
| GET | `/health` | 健康检查 |

## 核心模块

| 模块 | 职责 | 关键类 |
|------|------|--------|
| **gateway** | API 网关，消息分发 | `MessageProcessor`, `TaskManager`, `QueueManager`, `MessageRouter` |
| **workers/filter_analysis** | 消息过滤与任务分析 | `FilterAnalysisHandler` |
| **workers/decision** | 用户决策确认 | `DecisionHandler` |
| **workers/execution** | OpenCode 代码执行 | `ExecutionHandler` |
| **workers/recording** | 飞书记录与通知 | `RecordingHandler` |
| **llm_router** | LLM 智能路由 | `LLMRouter`, `OllamaProvider`, `ClaudeProvider` |
| **task_analyzer** | 任务分析 | `TaskAnalyzer` |
| **code_executor** | OpenCode 调用封装 | `CodeExecutor` |
| **feishu_recorder** | 飞书多维表格 | `FeishuClient`, `TaskRecord` |
| **config** | 配置管理 | `ConfigManager`, `AppConfig` |

## LLM 混合调度策略

| 复杂度 | 判断条件 | 路由 |
|--------|----------|------|
| **Simple** | 单一功能、明确技术栈 | Ollama (本地) |
| **Medium** | 2-3个功能点、需技术选型 | Ollama (本地) |
| **Complex** | 多功能、复杂逻辑、需架构设计 | Claude/GPT (云端) |

Fallback: Ollama 不可用时自动切换到云端 API。

## 飞书多维表格字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 任务 ID | 文本 | 任务唯一 ID |
| 任务标题 | 文本 | LLM 生成的摘要 |
| 任务描述 | 文本 | 原始消息 + 技术栈 + 功能点 |
| 任务完成状态 | 复选框 | 是否完成 |
| 代码仓库链接 | 链接 | OpenCode 生成的仓库 URL |

## 配置管理

所有敏感信息通过环境变量管理（参见 `.env.example`）：

```bash
# 企业微信
WECHAT_DEVICE_ID=xxx

# 飞书
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_TABLE_ID=xxx
FEISHU_BITABLE_TOKEN=xxx

# LLM
OLLAMA_BASE_URL=http://localhost:11434
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=sk-xxx

# OpenCode
OPENCODE_API_URL=http://localhost:4096
OPENCODE_WORK_DIR=./workspace

# Gateway
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8000
```

## 部署方案

### 方案 A: 单进程模式（开发/测试）

```bash
python main.py --mode standalone
```

所有组件在同一进程内运行，通过进程内调度器通信，无需启动多个服务。

### 方案 B: 分布式模式（生产）

```
公网服务器 (1核1G)
├── API Gateway (python main.py --mode gateway)
│   └── 接收: 企微消息、飞书回调、用户决策
│
内网服务器 A (GPU, 可选)
├── 分析 Worker (python main.py --mode filter-analysis)
│
内网服务器 B
├── 决策 Worker (python main.py --mode decision)
├── 执行 Worker (python main.py --mode execution)
├── 记录 Worker (python main.py --mode recording)
```

**优势**：
- 网关部署在公网，飞书回调直接打到网关，**无需内网穿透**
- 各 Worker 可按需独立扩展
- 分析 Worker 可部署在 GPU 服务器上加速推理

## 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| Web 框架 | FastAPI | >=0.109.0 |
| 飞书 SDK | lark-oapi | >=1.3.0 |
| LLM SDK | openai, anthropic | >=1.12.0, >=0.20.0 |
| 配置 | pydantic, pyyaml | >=2.6.0, >=6.0.1 |
| 日志 | loguru | >=0.7.2 |
| 测试 | pytest, pytest-asyncio | >=8.0.0 |
| HTTP 客户端 | httpx | >=0.27.0 |

## 安全考虑

- **Webhook 安全**：签名验证、频率限制
- **凭证管理**：所有凭证通过环境变量管理，不硬编码密钥
- **执行安全**：命令白名单、路径限制、危险操作拦截
- **网关安全**：输入校验、去重防护、CORS 配置
