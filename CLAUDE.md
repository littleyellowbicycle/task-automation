# 企业微信任务自动化系统 (WeChat Task Automation)

## 项目概述

这是一个基于企业微信群消息的任务自动化系统，能够：
1. 捕获企业微信群中的任务消息
2. 使用 LLM 分析并提取任务需求
3. 用户确认后自动执行代码生成
4. 将任务结果同步到飞书多维表格

## 技术栈

- **消息捕获**: NtWork (企业微信 Windows API)
- **LLM**: 混合方案 (Ollama 本地 + Claude/GPT 云端)
- **代码生成**: OpenCode (开源多模型 Agent)
- **记录存储**: 飞书多维表格 (lark-oapi)
- **运行环境**: Python 3.10+, Windows

## 目录结构

```
.
├── src/
│   ├── config/           # 配置管理
│   ├── wechat_listener/  # 企业微信消息监听
│   ├── llm_router/       # LLM 路由调度
│   ├── task_analyzer/    # 任务分析
│   ├── code_executor/    # OpenCode 执行器
│   ├── feishu_recorder/  # 飞书记录
│   ├── decision_manager/  # 决策确认
│   ├── workflow_orchestrator/  # 主流程编排
│   ├── exceptions/       # 自定义异常
│   └── utils/            # 工具函数
├── config/
│   └── config.yaml       # 配置文件
├── tests/               # 测试
└── main.py              # 入口文件
```

## 工作流程

```
企微群消息 → 消息捕获 → 关键词过滤 → LLM 分析摘要 → 用户确认 → OpenCode 执行 → 飞书记录
```

## 配置说明

所有配置通过 `config/config.yaml` 管理，支持环境变量覆盖。

### 必需的环境变量

```bash
# 企业微信
WECHAT_DEVICE_ID=your_device_id

# LLM (至少配置一个)
OLLAMA_BASE_URL=http://localhost:11434
ANTHROPIC_API_KEY=your_key  # 或
OPENAI_API_KEY=your_key

# 飞书
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_secret
FEISHU_TABLE_ID=your_table_id
```

## 使用方法

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入实际值
```

### 3. 启动服务

```bash
python main.py
```

### 4. 测试模式

```bash
python main.py --mode test --mock
```

## 代码生成规则

当 OpenCode 执行代码生成任务时：
- 默认在工作目录 `/tmp/opencode_workspace` 下创建
- 禁止修改 `/etc`, `/root`, `/sys`, `/proc` 等系统路径
- 禁止执行危险的系统命令

## LLM 路由策略

- **简单任务** (关键词: hello, test, basic): 使用 Ollama 本地模型
- **复杂任务** (关键词: analyze, architect, optimize): 使用 Claude/GPT 云端模型
- **自动降级**: Ollama 不可用时自动切换到云端

## 任务过滤关键词

系统会自动识别包含以下关键词的消息为任务：
- 项目发布
- 需求
- 开发任务
- 功能开发
- bug修复
- 重构

## 状态码

| 状态 | 说明 |
|------|------|
| pending | 待确认 |
| approved | 已确认 |
| executing | 执行中 |
| completed | 已完成 |
| failed | 失败 |
| cancelled | 已取消 |
| timeout | 超时 |
