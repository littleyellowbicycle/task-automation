# 企业微信任务自动化系统

基于企业微信群消息的自动化任务交付系统，使用 LLM 分析 + OpenCode 执行 + 飞书记录。

## 功能特性

- ✅ 企业微信群消息实时捕获
- ✅ 智能任务识别 (关键词 + 正则)
- ✅ LLM 自动分析生成摘要
- ✅ 用户确认机制
- ✅ OpenCode 自动代码生成
- ✅ 飞书多维表格同步记录
- ✅ 混合 LLM 调度 (本地 + 云端)
- ✅ 完善的错误处理和日志

## 系统要求

- Windows 10/11
- Python 3.10+
- 企业微信 Windows 客户端
- Docker (用于 Ollama，本地模型)

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd wechat-task-automation
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置

```bash
cp .env.example .env
# 编辑 .env 填入你的配置
```

主要配置项：
- `WECHAT_DEVICE_ID`: 企业微信设备 ID
- `OLLAMA_BASE_URL`: Ollama 服务地址 (可选)
- `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY`: 云端 LLM API Key
- `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_TABLE_ID`: 飞书配置

### 5. 启动 Ollama (可选，本地 LLM)

```bash
docker run -d -p 11434:11434 ollama/ollama
ollama pull llama3.2
```

### 6. 运行

```bash
python main.py
```

## 使用流程

1. **消息捕获**: 系统监控企业微信群消息
2. **任务识别**: 自动识别包含关键词的消息 (项目发布、需求等)
3. **LLM 分析**: 使用 LLM 提取技术栈、功能点、约束条件
4. **用户确认**: 发送确认消息到私聊，用户回复"确认"执行
5. **代码生成**: OpenCode 根据指令生成代码
6. **结果记录**: 自动同步到飞书多维表格

## 命令行参数

```bash
python main.py [选项]

选项:
  --mode MODE         运行模式: normal, test, mock (默认: normal)
  --dry-run          不实际执行代码生成
  --config PATH      指定配置文件路径
  --log-level LEVEL  日志级别: DEBUG, INFO, WARNING, ERROR
```

## 配置说明

### config/config.yaml

主配置文件，支持以下配置块：

| 配置块 | 说明 |
|--------|------|
| wechat | 企业微信连接配置 |
| llm | LLM 提供商配置 (Ollama, Anthropic, OpenAI) |
| opencode | OpenCode 执行器配置 |
| feishu | 飞书应用配置 |
| task_filters | 任务关键词过滤配置 |
| workflow | 工作流参数配置 |
| logging | 日志配置 |

### 环境变量

配置文件中的 `${VAR}` 或 `${VAR:-default}` 语法会自动从环境变量读取。

## 目录结构

```
.
├── src/
│   ├── config/              # 配置管理
│   │   ├── models.py        # Pydantic 模型
│   │   └── config_manager.py
│   ├── wechat_listener/     # 企业微信消息监听
│   │   ├── models.py        # 消息模型
│   │   ├── parser.py        # 消息解析
│   │   └── listener.py      # 监听器
│   ├── llm_router/          # LLM 路由
│   │   ├── providers.py     # 抽象基类
│   │   ├── ollama_provider.py
│   │   ├── cloud_provider.py
│   │   └── router.py
│   ├── task_analyzer/       # 任务分析器
│   ├── code_executor/       # OpenCode 封装
│   ├── feishu_recorder/     # 飞书记录
│   ├── decision_manager/    # 决策确认
│   ├── workflow_orchestrator/ # 流程编排
│   ├── exceptions/          # 异常定义
│   └── utils/               # 工具函数
├── config/
│   └── config.yaml
├── tests/
├── CLAUDE.md                # OpenCode 项目上下文
├── requirements.txt
└── main.py
```

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 带覆盖率
pytest tests/ -v --cov=src --cov-report=html

# Mock 模式测试
python main.py --mode mock
```

## 常见问题

### Q: 企业微信消息捕获失败
A: 确保企业微信 Windows 客户端已登录，设备 ID 已正确配置。

### Q: LLM 调用失败
A: 检查网络连接和 API Key 配置。Ollama 服务需要手动启动。

### Q: 飞书记录失败
A: 确认飞书应用已开通多维表格权限，Table ID 正确。

## License

MIT
