# 企业微信任务自动化交付系统 - 工作计划

## TL;DR

> **目标**: 构建一个自动化流水线：从企业微信群捕获任务消息 → LLM分析 → 用户确认 → OpenCode执行代码生成 → 飞书多维表格记录

> **技术栈**: Webhook (消息捕获) + 混合LLM (Ollama+云端) + OpenCode (代码生成) + lark-oapi (飞书记录)
> 
> **运行环境**: Windows + Python 3.10 + Docker (用于Ollama)

---

## Context

### 用户需求
用户在网络上检索到一套企业微信任务自动化方案，想要实际落地实现。

**核心流程**:
```
企微互通群消息 → 捕获识别 → LLM分析摘要 → 用户确认 → 本地Agent执行 → 飞书记录
```

**用户决策**:
- 代码生成Agent: **OpenCode** (开源多模型支持)
- LLM服务: **混合方案** (简单任务→Ollama本地, 复杂任务→Claude/OpenAI)
- 运行环境: **Windows**
- 使用规模: **个人使用**

### 研究发现

#### 1. NtWork (消息捕获层)
- 基于PC企业微信API的开源Python SDK
- 支持消息监听、发送、图片/文件等
- 需要企业微信 Windows客户端 (Wecom)
- Python 3.10最高支持版本
- GitHub: dev-kang/ntwork

#### 2. OpenCode (执行层)
- 开源CLI编码Agent，支持多模型
- 客户端/服务器架构，支持远程控制
- 支持MCP协议扩展
- 可通过`llama-server`连接本地Ollama
- 支持CLAUDE.md项目上下文

#### 3. 飞书多维表格
- lark-oapi官方Python SDK
- 支持创建/读取/更新记录
- 需要在飞书开放平台创建应用获取凭证

#### 4. LLM混合方案架构
```
┌─────────────────────────────────────────────────┐
│              LLM调度层                           │
├─────────────────────────────────────────────────┤
│  任务复杂度判断 → 简单/复杂                       │
│     ↓                  ↓                        │
│  Ollama (本地)      Claude/GPT (云端)           │
│  - 快速响应          - 强推理能力                │
│  - 免费              - 代码生成更强               │
│  - 7B-14B模型        - Claude 3.5/GPT-4o       │
└─────────────────────────────────────────────────┘
```

---

## Work Objectives

### 核心目标
实现一个可在Windows环境运行的自动化任务交付系统，完成从企业微信消息捕获到代码生成交付的全流程。

### 具体交付物

| 序号 | 交付物 | 说明 |
|------|--------|------|
| 1 | `wechat_listener/` | NtWork消息捕获模块 |
| 2 | `llm_router/` | 混合LLM调度器 (Ollama+云端) |
| 3 | `task_analyzer/` | 任务分析器，提取需求摘要 |
| 4 | `code_executor/` | OpenCode调用封装 |
| 5 | `feishu_recorder/` | 飞书多维表格记录器 |
| 6 | `workflow_orchestrator/` | 主流程编排，协调各模块 |
| 7 | `config.yaml` | 全局配置文件 |
| 8 | `main.py` | 入口脚本 |
| 9 | `CLAUDE.md` | OpenCode项目上下文 |

### 定义完成

- [ ] Windows环境下成功捕获企微群消息
- [ ] 消息过滤识别"项目发布"类任务
- [ ] LLM成功生成任务摘要 (含技术栈、功能点)
- [ ] 用户可通过私聊确认执行
- [ ] OpenCode成功执行代码生成
- [ ] 任务结果同步到飞书多维表格
- [ ] 全流程可手动触发/自动执行

### 约束条件 (Guardrails)

**必须做到**:
- NtWork连接稳定，支持长时间运行
- LLM调度有fallback机制
- 所有凭证信息不硬编码，通过环境变量读取
- 模块化设计，便于单独测试和替换

**明确排除**:
- 不实现企业微信官方API (需企业认证，复杂)
- 不实现复杂的权限管理系统 (用户说单人使用)
- 不实现高可用/集群部署 (超出需求范围)

---

## Verification Strategy

### 测试策略
- **单元测试**: 各模块独立测试 (pytest)
- **集成测试**: 端到端流程测试
- **QA验证**: 模拟真实消息触发，验证输出

### 验证命令
```bash
# 单元测试
pytest tests/ -v

# 模拟消息测试
python -m tests.test_message_flow --mock-wechat

# 端到端测试 (需要真实环境)
python main.py --mode test
```

---

## Execution Strategy

### Wave 1: 基础架构 (Day 1)
```
┌─────────────────────────────────────────────────────────┐
│  Wave 1: 基础模块搭建 (可并行)                            │
├─────────────────────────────────────────────────────────┤
│  T1. 项目脚手架 + 依赖安装 (config.yaml, requirements.txt)│
│  T2. 日志和配置管理模块                                   │
│  T3. NtWork消息捕获模块 (wechat_listener/)               │
│  T4. 飞书多维表格客户端 (feishu_recorder/)              │
│  T5. LLM调度器基础框架 (llm_router/)                     │
└─────────────────────────────────────────────────────────┘
```

### Wave 2: 核心逻辑 (Day 2)
```
┌─────────────────────────────────────────────────────────┐
│  Wave 2: 核心业务逻辑 (T6-T8 可并行)                      │
├─────────────────────────────────────────────────────────┤
│  T6. 任务分析器 - 消息解析、关键词提取、摘要生成           │
│  T7. OpenCode封装 - 命令执行、结果捕获、超时处理          │
│  T8. 飞书记录器完善 - 记录创建、状态更新、链接附加        │
│  T9. 决策确认机制 - 私聊确认、超时处理                    │
└─────────────────────────────────────────────────────────┘
```

### Wave 3: 集成编排 (Day 3)
```
┌─────────────────────────────────────────────────────────┐
│  Wave 3: 流程编排 + 优化                                  │
├─────────────────────────────────────────────────────────┤
│  T10. 主流程编排器 - 状态机、事件驱动、错误恢复           │
│  T11. CLAUDE.md配置 - OpenCode项目上下文                │
│  T12. 配置文件完善 - 环境变量、密钥管理                   │
│  T13. 错误处理和日志增强                                 │
│  T14. 文档编写 - README、快速开始指南                    │
└─────────────────────────────────────────────────────────┘
```

### Wave 4: 测试优化 (Day 4)
```
┌─────────────────────────────────────────────────────────┐
│  Wave 4: 测试 + 调优                                      │
├─────────────────────────────────────────────────────────┤
│  T15. 单元测试编写 - 各模块测试用例                      │
│  T16. 集成测试 - 端到端流程测试                          │
│  T17. 性能优化 - Ollama预热、缓存、并发                   │
│  T18. 稳定性测试 - 长时间运行、断线重连                   │
└─────────────────────────────────────────────────────────┘
```

### 关键路径
```
T1 → T3 → T6 → T9 → T10 → 端到端测试
         ↑                    ↓
         T5 ──────────────→ T7
                               ↓
         T4 ──────────────→ T8 → T10
```

---

## TODOs

- [ ] 1. 项目脚手架搭建

  **What to do**:
  - 创建项目目录结构
  - 初始化Python虚拟环境 (Python 3.10)
  - 创建 `requirements.txt`:
    ```
    ntwork>=0.9.0
    lark-oapi>=1.0.0
    openai>=1.0.0
    anthropic>=0.20.0
    pydantic>=2.0
    pyyaml>=6.0
    python-dotenv>=1.0
    loguru>=0.7
    pytest>=8.0
    pytest-asyncio>=0.23
    ```
  - 创建 `config.yaml` 模板
  - 创建 `.env.example` 环境变量模板
  - 创建 `.gitignore`

  **Must NOT do**:
  - 不安装不兼容的Python版本
  - 不硬编码任何凭证

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 基础设施搭建，模式固定，文件创建为主
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2-5)
  - **Blocks**: All other tasks
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - Python项目标准结构: `src/`, `tests/`, `config/`, `docs/`

  **API/Type References**:
  - NtWork GitHub: https://github.com/dev-kang/ntwork
  - lark-oapi PyPI: https://pypi.org/project/lark-oapi/
  - OpenCode GitHub: https://github.com/sigoden/opencode

  **External References**:
  - Python虚拟环境最佳实践
  - dotenv环境变量管理

  **Acceptance Criteria**:

  - [ ] 项目目录创建完成
  - [ ] `requirements.txt` 包含所有依赖
  - [ ] `.env.example` 包含所有需要的环境变量
  - [ ] `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` 成功

  **QA Scenarios**:

  ```
  Scenario: 依赖安装测试
    Tool: Bash
    Preconditions: .venv已创建
    Steps:
      1. source .venv/bin/activate
      2. pip install -r requirements.txt
      3. python -c "import ntwork; import lark_oapi; print('OK')"
    Expected Result: 无错误输出，打印 "OK"
    Failure Indicators: ImportError, VersionConflict
    Evidence: .sisyphus/evidence/task-1-deps-install.log
  ```

  **Commit**: YES (Wave 1 batch)
  - Message: `chore: initialize project structure`
  - Files: `requirements.txt`, `config.yaml`, `.env.example`, `.gitignore`

---

- [ ] 2. 日志和配置管理模块

  **What to do**:
  - 创建 `src/config/` 模块
  - 实现 `ConfigManager` 类:
    - 加载 `config.yaml`
    - 读取环境变量覆盖
    - Pydantic模型验证
  - 实现日志配置:
    - 使用 loguru
    - 日志轮转 (按天/按大小)
    - 分级输出 (console + file)
    - 结构化日志格式
  - 创建配置模型:
    - `WeChatConfig`: NtWork配置
    - `LLMConfig`: Ollama + 云端API配置
    - `OpenCodeConfig`: OpenCode执行配置
    - `FeishuConfig`: 飞书应用凭证
    - `WorkflowConfig`: 流程参数

  **Must NOT do**:
  - 不打印敏感信息 (API keys, tokens)
  - 不在日志中记录完整凭证

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 配置管理，模式固定
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3-5)
  - **Blocks**: T6, T10
  - **Blocked By**: T1

  **References**:

  **Pattern References**:
  - `src/config/` - 配置管理标准结构
  - Pydantic settings pattern

  **API/Type References**:
  - loguru文档: 日志配置
  - Pydantic BaseSettings

  **Acceptance Criteria**:

  - [ ] `python -c "from src.config import ConfigManager; c = ConfigManager(); print(c.llm.provider)"` 无错误
  - [ ] 日志文件正常写入
  - [ ] 环境变量覆盖生效

  **QA Scenarios**:

  ```
  Scenario: 配置加载测试
    Tool: Bash
    Preconditions: config.yaml存在
    Steps:
      1. 设置环境变量: export LLM_OLLAMA_BASE_URL="http://localhost:11434"
      2. python -c "from src.config import ConfigManager; c = ConfigManager(); print(c.llm.ollama.base_url)"
    Expected Result: 输出 "http://localhost:11434"
    Evidence: .sisyphus/evidence/task-2-config-load.log

  Scenario: 日志输出测试
    Tool: Bash
    Preconditions: 日志配置完成
    Steps:
      1. python -c "from src.utils import get_logger; logger = get_logger('test'); logger.info('Test message')"
      2. 检查 logs/ 目录
    Expected Result: 日志文件存在，包含测试消息
    Evidence: logs/test.log
  ```

  **Commit**: YES (Wave 1 batch)

---

- [ ] 3. NtWork消息捕获模块

  **What to do**:
  - 创建 `src/wechat_listener/` 模块
  - 实现 `WeChatListener` 类:
    - 初始化WeWork连接
    - 注册消息回调 (文本、图片、文件、链接)
    - 消息类型过滤 (群消息/私聊)
    - 自动重连机制
  - 实现消息解析:
    - 消息类型识别
    - 群ID/用户ID提取
    - 发送者信息
    - 消息内容解析
  - 实现消息队列:
    - 线程安全队列
    - 批量处理支持
    - 消息去重 (基于msgid)
  - 关键词过滤:
    - "项目发布"、"需求"、"开发任务" 等关键词
    - 正则匹配支持
    - 可配置关键词列表

  **Must NOT do**:
  - 不处理微信官方的隐私数据
  - 不在群里发送无关消息

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: NtWork SDK模式固定，主要是封装调用
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4, 5)
  - **Blocks**: T6, T10
  - **Blocked By**: T1, T2

  **References**:

  **Pattern References**:
  - NtWork官方示例: https://github.com/dev-kang/ntwork
  - 消息回调注册模式

  **API/Type References**:
  - `ntwork.WeWork` - 主类
  - `ntwork.MT_RECV_TEXT_MSG` - 消息类型常量
  - `message["data"]` - 消息数据结构

  **External References**:
  - 企业微信PC客户端 (Wecom) 下载
  - NtWork版本要求: Python 3.10, Wecom客户端

  **Acceptance Criteria**:

  - [ ] 模块可导入: `from src.wechat_listener import WeChatListener`
  - [ ] 实例化不报错
  - [ ] 消息回调注册成功

  **QA Scenarios**:

  ```
  Scenario: 模块导入测试
    Tool: Bash
    Preconditions: requirements安装完成
    Steps:
      1. python -c "from src.wechat_listener import WeChatListener; print('OK')"
    Expected Result: 打印 "OK"，无错误
    Evidence: .sisyphus/evidence/task-3-import.log

  Scenario: 消息解析测试 (Mock)
    Tool: Bash
    Preconditions: Mock消息数据
    Steps:
      1. python -c "
        from src.wechat_listener.parser import MessageParser
        mock_msg = {'msgtype': 'text', 'content': '项目发布: 登录功能开发', 'conversation_id': 'R:xxx'}
        parser = MessageParser()
        result = parser.parse(mock_msg)
        print(result.is_project_task)
      "
    Expected Result: 输出 "True" (检测到"项目发布"关键词)
    Evidence: .sisyphus/evidence/task-3-parser.log
  ```

  **Commit**: YES (Wave 1 batch)

---

- [ ] 4. 飞书多维表格客户端

  **What to do**:
  - 创建 `src/feishu_recorder/` 模块
  - 实现 `FeishuClient` 类:
    - OAuth2认证 (app_access_token / tenant_access_token)
    - Token自动刷新
    - 请求重试机制
  - 实现多维表格操作:
    - 创建记录
    - 查询记录
    - 更新记录
    - 批量操作
  - 实现任务记录模型:
    ```python
    class TaskRecord:
        task_id: str           # 任务唯一ID
        raw_message: str       # 原始消息
        summary: str           # LLM生成的摘要
        tech_stack: List[str]  # 技术栈列表
        core_features: List[str] # 核心功能点
        status: TaskStatus     # pending/approved/executing/completed/failed
        code_repo_url: str      # 代码仓库链接 (可选)
        created_at: datetime
        updated_at: datetime
    ```
  - 实现字段映射:
    - 多维表格字段ID动态获取
    - 类型转换处理

  **Must NOT do**:
  - 不缓存长期token (使用官方刷新机制)
  - 不暴露app_secret

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: SDK封装为主，API调用模式固定
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-3, 5)
  - **Blocks**: T10
  - **Blocked By**: T1, T2

  **References**:

  **Pattern References**:
  - lark-oapi官方示例
  - 多维表格API文档

  **API/Type References**:
  - `lark_oapi.api.bitable.v1` - 多维表格API
  - `BitableAppTableRecordApi` - 记录操作

  **External References**:
  - 飞书开放平台: https://open.feishu.cn/
  - 多维表格API文档

  **Acceptance Criteria**:

  - [ ] `from src.feishu_recorder import FeishuClient` 无错误
  - [ ] Token获取成功 (需要真实凭证)
  - [ ] 创建测试记录成功

  **QA Scenarios**:

  ```
  Scenario: 客户端初始化测试
    Tool: Bash
    Preconditions: .env配置正确
    Steps:
      1. python -c "from src.feishu_recorder import FeishuClient; client = FeishuClient(); print('OK')"
    Expected Result: 打印 "OK"
    Evidence: .sisyphus/evidence/task-4-client-init.log

  Scenario: 记录创建测试 (Mock模式)
    Tool: Bash
    Preconditions: Mock模式
    Steps:
      1. python -c "
        from src.feishu_recorder import FeishuClient
        from src.feishu_recorder.models import TaskRecord, TaskStatus
        client = FeishuClient()
        record = TaskRecord(
            task_id='test-001',
            raw_message='测试消息',
            summary='测试摘要',
            tech_stack=['Python'],
            core_features=['测试功能'],
            status=TaskStatus.PENDING
        )
        result = client.create_record(record, dry_run=True)
        print('Created:', result.task_id)
      "
    Expected Result: 输出创建的任务ID
    Evidence: .sisyphus/evidence/task-4-create-record.log
  ```

  **Commit**: YES (Wave 1 batch)

---

- [ ] 5. LLM调度器基础框架

  **What to do**:
  - 创建 `src/llm_router/` 模块
  - 实现 `LLMProvider` 抽象基类:
    ```python
    class LLMProvider(ABC):
        @abstractmethod
        async def complete(self, prompt: str, **kwargs) -> str: ...
        
        @abstractmethod
        async def chat(self, messages: List[Message], **kwargs) -> Message: ...
    ```
  - 实现 `OllamaProvider`:
    - 连接本地Ollama服务
    - 流式响应支持
    - 模型列表获取
    - 健康检查
  - 实现 `CloudProvider` (支持Claude/OpenAI):
    - API Key认证
    - 模型选择
    - 请求格式化
    - 错误处理和重试
  - 实现 `LLMRouter`:
    - 任务复杂度评估
    - 自动路由 (本地/云端)
    - Fallback机制
    - 成本统计
    - 响应缓存 (可选)

  **Must NOT do**:
  - 不存储API密钥
  - 不发送敏感日志

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: SDK封装为主，模式固定
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-4)
  - **Blocks**: T6
  - **Blocked By**: T1, T2

  **References**:

  **Pattern References**:
  - Provider模式
  - 策略模式

  **API/Type References**:
  - OpenAI Chat API格式
  - Anthropic Messages API格式
  - Ollama API格式

  **External References**:
  - Ollama文档: https://ollama.ai/
  - Anthropic API文档

  **Acceptance Criteria**:

  - [ ] `from src.llm_router import LLMRouter` 无错误
  - [ ] Provider切换正常工作
  - [ ] 路由逻辑正确

  **QA Scenarios**:

  ```
  Scenario: Provider切换测试
    Tool: Bash
    Preconditions: config配置正确
    Steps:
      1. python -c "
        from src.llm_router import LLMRouter
        router = LLMRouter()
        # 模拟简单任务
        result = router.route_task('你好', complexity='simple')
        print('Provider:', result.provider)
      "
    Expected Result: 对于简单任务，应选择Ollama (如果可用)
    Evidence: .sisyphus/evidence/task-5-router.log

  Scenario: Fallback测试
    Tool: Bash
    Preconditions: Ollama不可用
    Steps:
      1. 停止Ollama服务
      2. python -c "
        from src.llm_router import LLMRouter
        router = LLMRouter()
        result = router.complete('Say hello')
        print('Fallback worked:', len(result) > 0)
      "
    Expected Result: 自动切换到云端Provider
    Evidence: .sisyphus/evidence/task-5-fallback.log
  ```

  **Commit**: YES (Wave 1 batch)

---

- [ ] 6. 任务分析器

  **What to do**:
  - 创建 `src/task_analyzer/` 模块
  - 实现 `TaskAnalyzer`:
    - 消息预处理 (清洗、格式化)
    - 关键词提取
    - 结构化解析
  - 实现任务摘要生成:
    - 使用LLM分析原始消息
    - 提取技术栈
    - 识别核心功能点
    - 生成可执行描述
  - 实现Prompt模板:
    ```python
    TASK_ANALYSIS_PROMPT = """
    你是一个需求分析助手。请分析以下消息，提取关键信息。
    
    原始消息: {message}
    
    请以JSON格式输出:
    {{
      "summary": "简短的需求摘要 (50字内)",
      "tech_stack": ["技术栈列表"],
      "core_features": ["核心功能1", "核心功能2"],
      "constraints": ["约束条件"],
      "estimated_complexity": "simple/medium/complex"
    }}
    """
    ```
  - 实现结构化输出解析:
    - JSON解析
    - 错误处理
    - 默认值填充

  **Must NOT do**:
  - 不假设消息格式
  - 不丢失原始信息

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 主要是Prompt工程和解析逻辑
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (依赖T5)
  - **Parallel Group**: Wave 2
  - **Blocks**: T10
  - **Blocked By**: T5

  **References**:

  **Pattern References**:
  - LLM Prompt工程最佳实践
  - JSON输出解析模式

  **API/Type References**:
  - TaskRecord模型 (来自T4)

  **Acceptance Criteria**:

  - [ ] `from src.task_analyzer import TaskAnalyzer` 无错误
  - [ ] 成功解析测试消息
  - [ ] 输出符合TaskRecord格式

  **QA Scenarios**:

  ```
  Scenario: 任务分析测试
    Tool: Bash
    Preconditions: LLM配置正确
    Steps:
      1. python -c "
        from src.task_analyzer import TaskAnalyzer
        analyzer = TaskAnalyzer()
        result = analyzer.analyze('需要开发一个用户登录功能，使用Python Flask框架，支持邮箱验证码登录')
        print('Summary:', result.summary)
        print('Tech:', result.tech_stack)
        print('Features:', result.core_features)
      "
    Expected Result: 正确提取技术栈(Flask/Python)、功能点(登录、验证码)
    Evidence: .sisyphus/evidence/task-6-analyzer.log

  Scenario: 格式容错测试
    Tool: Bash
    Preconditions: 异常格式消息
    Steps:
      1. python -c "
        from src.task_analyzer import TaskAnalyzer
        analyzer = TaskAnalyzer()
        # 无效消息
        result = analyzer.analyze('项目发布')
        print('Summary:', result.summary)
      "
    Expected Result: 提供默认值，不崩溃
    Evidence: .sisyphus/evidence/task-6-error-handle.log
  ```

  **Commit**: YES (Wave 2 batch)

---

- [ ] 7. OpenCode封装

  **What to do**:
  - 创建 `src/code_executor/` 模块
  - 实现 `CodeExecutor`:
    - OpenCode CLI调用封装
    - 命令构建和执行
    - 工作目录管理
    - 超时控制
  - 实现任务转换:
    - 将TaskRecord转换为OpenCode指令
    - 生成CLAUDE.md上下文
  - 实现执行监控:
    - 实时输出捕获
    - 进度回调
    - 取消机制
  - 实现结果处理:
    - 输出解析
    - 错误识别
    - 仓库链接提取
  - 实现安全检查:
    - 命令白名单
    - 路径限制
    - 危险操作拦截

  **Must NOT do**:
  - 不执行未授权的命令
  - 不修改系统关键路径

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 涉及系统调用和进程管理，需要仔细处理
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T6, T8, T9)
  - **Parallel Group**: Wave 2
  - **Blocks**: T10
  - **Blocked By**: T5

  **References**:

  **Pattern References**:
  - subprocess进程管理
  - OpenCode CLI用法

  **API/Type References**:
  - TaskRecord模型

  **External References**:
  - OpenCode文档

  **Acceptance Criteria**:

  - [ ] `from src.code_executor import CodeExecutor` 无错误
  - [ ] OpenCode命令成功执行
  - [ ] 超时机制正常工作

  **QA Scenarios**:

  ```
  Scenario: 简单命令执行测试
    Tool: Bash
    Preconditions: OpenCode已安装
    Steps:
      1. python -c "
        from src.code_executor import CodeExecutor
        import asyncio
        async def test():
            executor = CodeExecutor()
            result = await executor.execute('Create a simple hello.py that prints Hello World')
            print('Exit code:', result.exit_code)
        asyncio.run(test())
      "
    Expected Result: hello.py被创建，exit_code=0
    Evidence: .sisyphus/evidence/task-7-simple-exec.log

  Scenario: 超时测试
    Tool: Bash
    Preconditions: 超时配置
    Steps:
      1. python -c "
        from src.code_executor import CodeExecutor
        executor = CodeExecutor(timeout=1)
        result = executor.execute('sleep 10')
        print('Timeout worked:', result.is_timeout)
      "
    Expected Result: is_timeout=True
    Evidence: .sisyphus/evidence/task-7-timeout.log
  ```

  **Commit**: YES (Wave 2 batch)

---

- [ ] 8. 飞书记录器完善

  **What to do**:
  - 完善 `src/feishu_recorder/` 模块
  - 实现状态流转:
    - pending → approved → executing → completed/failed
    - 状态变更回调
  - 实现附件处理:
    - 代码仓库链接
    - 生成的代码片段 (可选)
    - 执行日志 (可选)
  - 实现查询功能:
    - 按状态查询
    - 按时间范围查询
    - 分页支持
  - 实现Webhook通知 (可选):
    - 任务状态变更通知
    - 执行结果通知

  **Must NOT do**:
  - 不在失败后删除记录
  - 不覆盖历史状态

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 主要是功能扩展
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T6, T7, T9)
  - **Parallel Group**: Wave 2
  - **Blocks**: T10
  - **Blocked By**: T4

  **References**:

  **Pattern References**:
  - 状态机模式
  - 观察者模式 (状态变更通知)

  **API/Type References**:
  - TaskRecord模型

  **Acceptance Criteria**:

  - [ ] 状态更新正常工作
  - [ ] 历史记录不丢失

  **QA Scenarios**:

  ```
  Scenario: 状态流转测试
    Tool: Bash
    Preconditions: 测试记录存在
    Steps:
      1. python -c "
        from src.feishu_recorder import FeishuClient
        from src.feishu_recorder.models import TaskStatus
        client = FeishuClient()
        # 更新状态
        result = client.update_status('test-001', TaskStatus.EXECUTING)
        print('Updated:', result.status)
      "
    Expected Result: 状态更新为EXECUTING
    Evidence: .sisyphus/evidence/task-8-state-flow.log
  ```

  **Commit**: YES (Wave 2 batch)

---

- [ ] 9. 决策确认机制

  **What to do**:
  - 创建 `src/decision_manager/` 模块
  - 实现 `DecisionManager`:
    - 生成确认请求
    - 私聊发送确认消息
    - 等待用户响应
    - 超时处理
  - 实现确认模板:
    ```markdown
    📋 **任务确认**
    
    **摘要**: {summary}
    **技术栈**: {tech_stack}
    **核心功能**:
    {for feature in core_features}
    - {feature}
    
    **执行命令**: `opencode {instruction}`
    
    ⏱️ 超时时间: {timeout}分钟
    
    回复 "确认" 执行 / "取消" 终止
    ```
  - 实现多种确认方式:
    - 企微私聊确认
    - 命令行确认 (备选)
  - 实现确认结果处理:
    - 执行/取消路由
    - 取消原因记录

  **Must NOT do**:
  - 不自动执行未经确认的任务
  - 不在超时后继续执行

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 主要是消息模板和流程控制
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T6-8)
  - **Parallel Group**: Wave 2
  - **Blocks**: T10
  - **Blocked By**: T3, T5

  **References**:

  **Pattern References**:
  - 确认-执行模式
  - 超时处理

  **API/Type References**:
  - WeChatListener (发送私聊)
  - TaskRecord

  **Acceptance Criteria**:

  - [ ] `from src.decision_manager import DecisionManager` 无错误
  - [ ] 确认消息正确发送
  - [ ] 超时处理正常

  **QA Scenarios**:

  ```
  Scenario: 确认消息生成测试
    Tool: Bash
    Preconditions: TaskRecord存在
    Steps:
      1. python -c "
        from src.decision_manager import DecisionManager
        from src.feishu_recorder.models import TaskRecord
        manager = DecisionManager()
        record = TaskRecord(task_id='test-001', summary='测试任务', ...)
        msg = manager.format_confirmation(record)
        print(msg)
      "
    Expected Result: 生成格式化的确认消息
    Evidence: .sisyphus/evidence/task-9-confirm-msg.log

  Scenario: 超时测试
    Tool: Bash
    Preconditions: Mock用户无响应
    Steps:
      1. python -c "
        from src.decision_manager import DecisionManager
        import asyncio
        async def test():
            manager = DecisionManager(timeout=1)  # 1秒超时
            result = await manager.wait_confirmation('test-001')
            print('Result:', result)
        asyncio.run(test())
      "
    Expected Result: 返回 'timeout'
    Evidence: .sisyphus/evidence/task-9-timeout.log
  ```

  **Commit**: YES (Wave 2 batch)

---

- [ ] 10. 主流程编排器

  **What to do**:
  - 创建 `src/workflow_orchestrator/` 模块
  - 实现 `WorkflowOrchestrator`:
    - 状态机管理
    - 事件驱动架构
    - 错误恢复机制
    - 日志记录
  - 实现主流程:
    ```
    ┌─────────────────┐
    │  捕获消息        │
    └────────┬────────┘
             ↓
    ┌─────────────────┐
    │  过滤项目任务   │ ──否──→ 忽略
    └────────┬────────┘
             ↓ 是
    ┌─────────────────┐
    │  LLM分析摘要    │
    └────────┬────────┘
             ↓
    ┌─────────────────┐
    │  用户确认       │ ──取消──→ 记录取消
    └────────┬────────┘
             ↓ 确认
    ┌─────────────────┐
    │  OpenCode执行   │
    └────────┬────────┘
             ↓
    ┌─────────────────┐
    │  飞书记录       │
    └─────────────────┘
    ```
  - 实现事件钩子:
    - `on_task_captured`
    - `on_task_analyzed`
    - `on_task_confirmed`
    - `on_task_executed`
    - `on_task_completed`
    - `on_task_failed`
  - 实现并发控制:
    - 同时执行任务数限制
    - 资源隔离

  **Must NOT do**:
  - 不丢失任何状态变更
  - 不在错误后静默失败

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 核心编排逻辑，需要仔细设计
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (最终集成)
  - **Parallel Group**: Wave 3
  - **Blocks**: 端到端测试
  - **Blocked By**: T6, T7, T8, T9

  **References**:

  **Pattern References**:
  - 状态机模式
  - 事件驱动架构
  - Pipeline模式

  **API/Type References**:
  - 所有模块的主入口

  **Acceptance Criteria**:

  - [ ] `from src.workflow_orchestrator import WorkflowOrchestrator` 无错误
  - [ ] 完整流程可执行
  - [ ] 状态转换正确

  **QA Scenarios**:

  ```
  Scenario: 完整流程测试 (Mock模式)
    Tool: Bash
    Preconditions: 所有模块就绪
    Steps:
      1. python -c "
        from src.workflow_orchestrator import WorkflowOrchestrator
        import asyncio
        async def test():
            orch = WorkflowOrchestrator(dry_run=True)
            result = await orch.run('项目发布: 登录功能')
            print('Final status:', result.status)
        asyncio.run(test())
      "
    Expected Result: 流程完成，最终状态符合预期
    Evidence: .sisyphus/evidence/task-10-full-flow.log
  ```

  **Commit**: YES (Wave 3 batch)

---

- [ ] 11. CLAUDE.md配置

  **What to do**:
  - 创建项目根目录 `CLAUDE.md`
  - 包含内容:
    - 项目概述
    - 技术栈说明
    - 代码规范
    - 目录结构
    - OpenCode使用指南
    - 常见任务示例

  **Must NOT do**:
  - 不包含敏感信息
  - 不过于冗长

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: 文档编写
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T12-14)
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - CLAUDE.md最佳实践

  **Acceptance Criteria**:

  - [ ] CLAUDE.md存在且格式正确
  - [ ] OpenCode可读取并应用

  **QA Scenarios**:

  ```
  Scenario: OpenCode读取测试
    Tool: Bash
    Preconditions: CLAUDE.md存在
    Steps:
      1. opencode --version
      2. opencode "What is this project about?" (在项目目录)
    Expected Result: OpenCode能回答出项目概要
    Evidence: .sisyphus/evidence/task-11-claudemd.log
  ```

  **Commit**: YES (Wave 3 batch)

---

- [ ] 12. 配置文件完善

  **What to do**:
  - 完善 `config.yaml`:
    - 所有模块配置项
    - 默认值
    - 注释说明
  - 实现敏感信息管理:
    - 环境变量读取
    - .env文件支持
    - 密钥轮换提示
  - 实现配置验证:
    - 启动时检查必要配置
    - 友好错误提示

  **Must NOT do**:
  - 不在config.yaml中硬编码密钥

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 配置文件编写
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T11, T13, T14)
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: T2

  **References**:

  **Pattern References**:
  - 12-Factor App配置管理

  **Acceptance Criteria**:

  - [ ] config.yaml包含所有配置项
  - [ ] 环境变量覆盖生效
  - [ ] 缺少配置时有友好提示

  **QA Scenarios**:

  ```
  Scenario: 配置验证测试
    Tool: Bash
    Preconditions: 缺少必需配置
    Steps:
      1. rm -f .env && python main.py
    Expected Result: 友好的错误提示，说明缺少哪些配置
    Evidence: .sisyphus/evidence/task-12-config-validation.log
  ```

  **Commit**: YES (Wave 3 batch)

---

- [ ] 13. 错误处理和日志增强

  **What to do**:
  - 完善错误处理:
    - 分层异常定义
    - 统一错误响应
    - 错误恢复策略
  - 增强日志:
    - 结构化日志
    - 敏感信息脱敏
    - 日志聚合支持
  - 实现健康检查:
    - 各组件状态
    - 告警机制 (可选)

  **Must NOT do**:
  - 不在日志中打印密钥

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 完善现有代码
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T11, T12, T14)
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: T2

  **References**:

  **Pattern References**:
  - 分层异常处理
  - 结构化日志

  **Acceptance Criteria**:

  - [ ] 异常分类清晰
  - [ ] 日志格式统一
  - [ ] 错误提示友好

  **QA Scenarios**:

  ```
  Scenario: 异常处理测试
    Tool: Bash
    Preconditions: 触发异常场景
    Steps:
      1. python -c "
        from src.wechat_listener import WeChatListener
        from src.exceptions import WeChatConnectionError
        try:
            listener = WeChatListener()
            listener.connect()  # 无效调用
        except WeChatConnectionError as e:
            print('Caught:', type(e).__name__)
      "
    Expected Result: 抛出自定义异常
    Evidence: .sisyphus/evidence/task-13-error-handling.log
  ```

  **Commit**: YES (Wave 3 batch)

---

- [ ] 14. 文档编写

  **What to do**:
  - 创建 `README.md`:
    - 项目简介
    - 快速开始
    - 架构说明
    - 配置指南
    - 使用示例
    - 常见问题
  - 创建 `docs/` 目录:
    - `ARCHITECTURE.md` - 架构设计文档
    - `API.md` - API接口文档
    - `TROUBLESHOOTING.md` - 故障排除指南

  **Must NOT do**:
  - 不在文档中暴露凭证示例

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: 文档编写
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T11-13)
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - README最佳实践

  **Acceptance Criteria**:

  - [ ] README.md存在且完整
  - [ ] 新手可按文档启动项目

  **QA Scenarios**:

  ```
  Scenario: 文档完整性检查
    Tool: Bash
    Preconditions: 文档存在
    Steps:
      1. 检查README.md是否包含: 安装、配置、使用示例
      2. 检查docs/目录结构
    Expected Result: 所有必需章节存在
    Evidence: .sisyphus/evidence/task-14-docs.log
  ```

  **Commit**: YES (Wave 3 batch)

---

- [ ] 15. 单元测试编写

  **What to do**:
  - 创建 `tests/` 目录结构:
    ```
    tests/
    ├── __init__.py
    ├── conftest.py           # pytest配置
    ├── test_config/
    ├── test_wechat_listener/
    ├── test_llm_router/
    ├── test_feishu_recorder/
    ├── test_task_analyzer/
    ├── test_code_executor/
    └── test_workflow_orchestrator/
    ```
  - 为每个模块编写测试:
    - 基本功能测试
    - 边界条件测试
    - 错误处理测试
  - 使用Mock避免外部依赖

  **Must NOT do**:
  - 不测试第三方库本身
  - 不在测试中使用真实凭证

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 测试编写，模式固定
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T16-18)
  - **Parallel Group**: Wave 4
  - **Blocks**: None
  - **Blocked By**: T1-14

  **References**:

  **Pattern References**:
  - pytest最佳实践
  - Mock使用

  **Acceptance Criteria**:

  - [ ] `pytest tests/ -v` 全部通过
  - [ ] 测试覆盖率 > 70%

  **QA Scenarios**:

  ```
  Scenario: 运行全部测试
    Tool: Bash
    Preconditions: 测试文件存在
    Steps:
      1. pytest tests/ -v --cov=src --cov-report=term-missing
    Expected Result: 所有测试通过，覆盖率报告生成
    Evidence: .sisyphus/evidence/task-15-unit-tests.log
  ```

  **Commit**: YES (Wave 4 batch)

---

- [ ] 16. 集成测试

  **What to do**:
  - 创建 `tests/integration/` 目录
  - 实现端到端测试:
    - 模拟完整流程
    - 使用Mock服务
    - 验证状态流转
  - 实现组件集成测试:
    - 模块间接口测试
    - 错误传播测试
  - 实现性能测试:
    - 并发任务处理
    - 响应时间基准

  **Must NOT do**:
  - 不在集成测试中使用真实API

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 涉及多模块协调
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T15, T17, T18)
  - **Parallel Group**: Wave 4
  - **Blocks**: None
  - **Blocked By**: T10, T15

  **References**:

  **Pattern References**:
  - 集成测试最佳实践

  **Acceptance Criteria**:

  - [ ] 端到端测试通过
  - [ ] 组件接口兼容

  **QA Scenarios**:

  ```
  Scenario: 端到端集成测试
    Tool: Bash
    Preconditions: Mock模式
    Steps:
      1. pytest tests/integration/ -v -k "test_full_flow"
    Expected Result: 完整流程测试通过
    Evidence: .sisyphus/evidence/task-16-integration.log
  ```

  **Commit**: YES (Wave 4 batch)

---

- [ ] 17. 性能优化

  **What to do**:
  - LLM预热:
    - 启动时预加载模型
    - 请求缓存
  - 并发优化:
    - 异步IO
    - 连接池
  - 内存优化:
    - 大消息分块
    - 缓存清理
  - 数据库/文件IO优化

  **Must NOT do**:
  - 不牺牲稳定性换性能

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 性能调优
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T15, T16, T18)
  - **Parallel Group**: Wave 4
  - **Blocks**: None
  - **Blocked By**: T10

  **References**:

  **Pattern References**:
  - 性能优化最佳实践

  **Acceptance Criteria**:

  - [ ] 响应时间改善明显
  - [ ] 内存使用稳定

  **QA Scenarios**:

  ```
  Scenario: 性能基准测试
    Tool: Bash
    Preconditions: 性能测试脚本
    Steps:
      1. python -m benchmarks.latency_test
    Expected Result: 响应时间在预期范围内
    Evidence: .sisyphus/evidence/task-17-performance.log
  ```

  **Commit**: YES (Wave 4 batch)

---

- [ ] 18. 稳定性测试

  **What to do**:
  - 长时间运行测试:
    - 24小时+ 运行
    - 内存泄漏检测
  - 断线重连测试:
    - 网络中断模拟
    - 服务重启恢复
  - 异常输入测试:
    - 各种边界消息
    - 恶意输入防护
  - 资源限制测试:
    - 磁盘满
    - 内存不足

  **Must NOT do**:
  - 不在实际环境测试破坏性场景

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 稳定性验证
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T15-17)
  - **Parallel Group**: Wave 4
  - **Blocks**: None
  - **Blocked By**: T10

  **References**:

  **Pattern References**:
  - 混沌工程原则

  **Acceptance Criteria**:

  - [ ] 长时间运行无内存泄漏
  - [ ] 断线可自动恢复

  **QA Scenarios**:

  ```
  Scenario: 断线重连测试
    Tool: Bash
    Preconditions: Mock网络中断
    Steps:
      1. python -m tests.stability.test_reconnect
    Expected Result: 自动重连成功
    Evidence: .sisyphus/evidence/task-18-stability.log
  ```

  **Commit**: YES (Wave 4 batch)

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — `oracle`
  
  读取计划并验证:
  - 每个Must Have是否存在
  - 每个Must NOT Have是否避免
  - 所有交付物是否完成
  - 验证证据文件存在

- [ ] F2. **Code Quality Review** — `unspecified-high`
  
  运行检查:
  - `python -m py_compile src/**/*.py`
  - 代码风格一致性
  - 无硬编码凭证
  - 测试覆盖率

- [ ] F3. **Real Manual QA** — `unspecified-high`
  
  端到端验证:
  - 模拟企微消息触发
  - 完整流程执行
  - 飞书记录验证
  - 截图/日志证据

- [ ] F4. **Scope Fidelity Check** — `deep`
  
  检查:
  - 无多余功能
  - 无scope creep
  - 符合用户决策

---

## Commit Strategy

- **Wave 1**: `chore: setup project scaffolding and base modules`
- **Wave 2**: `feat: implement core business logic`
- **Wave 3**: `feat: integrate workflow and add documentation`
- **Wave 4**: `test: add tests and optimize performance`

---

## Success Criteria

### 验证命令
```bash
# 1. 环境检查
python -c "from src.config import ConfigManager; print('Config OK')"
python -c "from src.wechat_listener import WeChatListener; print('WeChat OK')"
python -c "from src.llm_router import LLMRouter; print('LLM OK')"
python -c "from src.feishu_recorder import FeishuClient; print('Feishu OK')"
python -c "from src.task_analyzer import TaskAnalyzer; print('Analyzer OK')"
python -c "from src.code_executor import CodeExecutor; print('Executor OK')"
python -c "from src.workflow_orchestrator import WorkflowOrchestrator; print('Orchestrator OK')"

# 2. 单元测试
pytest tests/ -v --tb=short

# 3. 集成测试 (需要真实环境)
python main.py --mode test --mock
```

### 最终检查清单
- [ ] 所有模块可导入
- [ ] 配置正确加载
- [ ] 单元测试全部通过
- [ ] 集成测试通过
- [ ] 文档完整
- [ ] 无硬编码敏感信息
- [ ] README可指导新用户上手
