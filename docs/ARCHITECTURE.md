# WeChat Task Automation System - 架构设计文档

## 一、系统概述

这是一个**企业微信任务自动化系统**，核心流程为：

```
企业微信群消息捕获 → 任务过滤 → 任务分析 → 用户确认 → 代码执行 → 飞书记录
```

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Layer 1: 监听层                                                              │
│ ─────────────────────────────────────────────────────────────────────────── │
│ NtWorkListener / WebhookListener / UIAutomationListener                     │
│ 职责: 只负责消息收发，输出原始消息数据                                        │
│ 输出: raw_message (dict)                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Layer 2: 网关层                                                              │
│ ─────────────────────────────────────────────────────────────────────────── │
│ MessageGateway                                                               │
│ 职责: 消息校验、标准化、去重、分发                                            │
│ 输出: StandardMessage                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Layer 3: 过滤层 (Qwen3-0.6B)                                                 │
│ ─────────────────────────────────────────────────────────────────────────── │
│ TaskFilter                                                                   │
│ 职责: 任务分类 + 语义去重                                                     │
│ 输出: TaskMessage (is_task: bool)                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Layer 4: 队列层                                                              │
│ ─────────────────────────────────────────────────────────────────────────── │
│ TaskQueue                                                                    │
│ 职责: 串行队列管理，超时控制                                                  │
│ 配置: max_size=20, timeout=3h                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Layer 5: 分析层                                                              │
│ ─────────────────────────────────────────────────────────────────────────── │
│ TaskAnalyzer                                                                 │
│ 职责: 摘要提取、技术栈识别、功能点提取、复杂度评估                            │
│ 输出: TaskRecord                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Layer 6: 决策层                                                              │
│ ─────────────────────────────────────────────────────────────────────────── │
│ DecisionManager (飞书卡片)                                                   │
│ 职责: 推送确认卡片，接收用户决策                                              │
│ 输出: Decision (APPROVED/REJECTED/TIMEOUT)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Layer 7: 执行层                                                              │
│ ─────────────────────────────────────────────────────────────────────────── │
│ CodeExecutor                                                                 │
│ 职责: 安全检查、代码生成执行、超时控制                                        │
│ 输出: ExecutionResult                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Layer 8: 记录层                                                              │
│ ─────────────────────────────────────────────────────────────────────────── │
│ FeishuRecorder                                                               │
│ 职责: 结果持久化到飞书表格                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、各层详细设计

### 3.1 监听层 (Listener Layer)

**职责**: 只负责消息收发，不包含任何业务逻辑

**接口设计**:
```python
class BaseListener(ABC):
    """监听器抽象基类"""
    
    @abstractmethod
    async def start(self) -> None:
        """启动监听"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止监听"""
        pass
    
    @abstractmethod
    async def send(self, conversation_id: str, content: str) -> bool:
        """发送消息"""
        pass
    
    @property
    @abstractmethod
    def on_message(self) -> Callable[[dict], None]:
        """消息回调"""
        pass
```

**实现类型**:
| 监听器 | 平台 | 说明 |
|--------|------|------|
| NtWorkListener | 企业微信 | 基于 ntwork 库的网络监听 |
| WebhookListener | 企业微信/微信 | HTTP Webhook 接收 |
| UIAutomationListener | 企业微信/微信 | UI 自动化监听 |

**平台支持**:
```python
class Platform(str, Enum):
    WEWORK = "wework"    # 企业微信
    WECHAT = "wechat"    # 微信
```

---

### 3.2 网关层 (Gateway Layer)

**职责**: 消息校验、标准化、分发

**核心功能**:
1. 数据校验（签名验证、格式检查、必填字段）
2. 消息标准化（统一消息结构）
3. 平台标识
4. 分发到后续流程

**数据结构**:
```python
@dataclass
class StandardMessage:
    msg_id: str
    platform: Platform
    listener_type: ListenerType
    content: str
    sender: SenderInfo
    conversation: ConversationInfo
    timestamp: datetime
    raw_data: dict
```

---

### 3.3 过滤层 (Filter Layer)

**职责**: 任务分类 + 语义去重

**技术方案**: Qwen3-0.6B

**任务分类 Prompt**:
```
你是一个消息分类器。判断以下消息是否是一个需要执行的任务。

消息："{message}"

任务定义：需要有人去完成的具体工作，如开发需求、bug修复、功能实现等。

只回答：是/否
```

**语义去重**:
```python
# 用 Qwen 生成 embedding
embedding = model.encode(message)

# 与历史消息计算余弦相似度
for hist_embedding in recent_embeddings:
    similarity = cosine_similarity(embedding, hist_embedding)
    if similarity > 0.85:  # 阈值可调
        return True  # 重复
```

**资源消耗**:
| 配置 | 内存 | 延迟 | 适用场景 |
|------|------|------|----------|
| CPU only | ~2GB | 100-300ms | 低频消息 |
| GPU (4GB) | ~1.5GB | 10-50ms | 高频消息 |

---

### 3.4 队列层 (Queue Layer)

**职责**: 串行队列管理，超时控制

**配置**:
```yaml
workflow:
  max_queue_size: 20           # 队列最大容量
  confirmation_timeout: 10800  # 确认超时 3小时
```

**数据结构**:
```python
@dataclass
class TaskQueue:
    pending: List[TaskRecord]      # 等待处理
    current: Optional[TaskRecord]  # 当前处理中
    completed: List[TaskRecord]    # 已完成
    
    max_size: int = 20
    confirmation_timeout: int = 10800
    
    def enqueue(self, task: TaskRecord) -> bool:
        """新任务入队"""
        if len(self.pending) >= self.max_size:
            return False
        self.pending.append(task)
        return True
    
    def dequeue(self) -> Optional[TaskRecord]:
        """取出下一个任务"""
        if not self.pending:
            return None
        self.current = self.pending.pop(0)
        return self.current
    
    def complete_current(self, status: TaskStatus):
        """完成当前任务"""
        if self.current:
            self.current.status = status
            self.completed.append(self.current)
            self.current = None
```

---

### 3.5 分析层 (Analyzer Layer)

**职责**: 从消息中提取结构化任务信息

**输出字段**:
- 摘要 (summary)
- 技术栈识别 (tech_stack)
- 核心功能点 (core_features)
- 复杂度评估 (estimated_complexity)

**数据结构**:
```python
@dataclass
class TaskRecord:
    task_id: str
    raw_message: str
    summary: str
    tech_stack: List[str]
    core_features: List[str]
    status: TaskStatus
    complexity: str  # simple / medium / complex
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

---

### 3.6 决策层 (Decision Layer)

**职责**: 推送确认卡片，接收用户决策

**交互方式**: 飞书卡片

**卡片设计**:
```
┌───────────────────────────────────────────────────┐
│ 📋 任务确认                                        │
│ ───────────────────────────────────────────────   │
│                                                    │
│ 📝 摘要                                            │
│ 开发用户登录功能，支持手机号/邮箱登录              │
│                                                    │
│ 🛠️ 技术栈                                          │
│ Python, FastAPI, JWT, PostgreSQL                  │
│                                                    │
│ ⚡ 功能点                                           │
│ • 用户登录/注册                                    │
│ • JWT认证                                         │
│ • 密码加密存储                                      │
│                                                    │
│ 📊 复杂度: 中等                                    │
│ 👤 来源: 张三 (产品群)                             │
│ 📅 时间: 2024-01-15 10:30                         │
│                                                    │
│ ───────────────────────────────────────────────   │
│ 📌 队列状态: 还有 2 个任务等待处理                  │
│ ⏱️ 请在 3 小时内确认，超时将自动取消                │
│                                                    │
│ ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│ │  ✅ 确认  │  │  ❌ 取消  │  │  ⏸️ 稍后  │          │
│ └──────────┘  └──────────┘  └──────────┘          │
└───────────────────────────────────────────────────┘
```

**决策类型**:
```python
class Decision(str, Enum):
    APPROVED = "approved"    # 确认执行
    REJECTED = "rejected"    # 取消任务
    LATER = "later"          # 稍后处理（放回队列尾部）
    TIMEOUT = "timeout"      # 超时自动取消
```

---

### 3.7 执行层 (Executor Layer)

**职责**: 代码生成与执行

**OpenCode 调用方式**: 混合模式（本地 CLI / 远程 API）

**配置**:
```yaml
opencode:
  mode: "remote"  # local / remote
  local:
    cli_path: "opencode"
    work_dir: "./workspace"
  remote:
    api_url: "${OPENCODE_API_URL}"
    api_key: "${OPENCODE_API_KEY}"
  interaction_timeout: 1800  # 交互超时 30分钟
  max_retries: 3             # 最大重试次数
```

**执行中交互处理**:

OpenCode 执行过程中可能需要用户交互：
1. 澄清需求 - 任务描述不清晰
2. 选择方案 - 多种技术方案选择
3. 确认操作 - 删除文件、修改配置等危险操作
4. 补充信息 - 缺少必要参数
5. 处理错误 - 遇到问题需要人工介入

**交互流程**:
```
OpenCode → 检测到提问 → 暂停执行 → 推送问题到飞书卡片
    → 用户响应 → 注入答案 → 继续执行
```

**交互类型**:
```python
class InteractionType(str, Enum):
    CONFIRMATION = "confirmation"      # 简单确认
    CHOICE = "choice"                  # 多选一
    INPUT = "input"                    # 文本输入
    FILE_SELECTION = "file_selection"  # 文件选择
    ERROR_HANDLING = "error_handling"  # 错误处理
```

**执行进度卡片**:
```
┌───────────────────────────────────────────────────┐
│ ⚙️ 执行中                                          │
│ ───────────────────────────────────────────────   │
│                                                    │
│ 📋 任务: 开发用户登录功能                          │
│                                                    │
│ 📊 执行步骤:                                       │
│ ✅ 1. 分析项目结构                                 │
│ ✅ 2. 创建文件骨架                                 │
│ 🔄 3. 实现登录逻辑  ← 当前                         │
│ ⬜ 4. 添加单元测试                                 │
│ ⬜ 5. 更新文档                                     │
│                                                    │
│ 📁 已创建文件:                                     │
│ • src/auth/login.py                               │
│ • src/auth/models.py                              │
│                                                    │
│ ⏱️ 已用时: 3分15秒                                 │
│                                                    │
│ [查看详情]  [暂停]  [取消]                         │
└───────────────────────────────────────────────────┘
```

---

### 3.8 记录层 (Recorder Layer)

**职责**: 结果持久化到飞书表格

**记录内容**:
- 任务ID
- 原始消息
- 分析结果
- 执行状态
- 代码仓库URL
- 错误信息
- 创建/更新时间

---

## 四、状态同步设计

### 任务状态机

```
PENDING → APPROVED → EXECUTING → COMPLETED
   │         │          │            │
   │         │          ├──────────▶ FAILED
   │         │          │
   │         │          └── WAITING_INPUT
   │         │                   │
   │         │                   └── (用户输入) → EXECUTING
   │         │
   │         └── REJECTED
   │
   └── TIMEOUT
```

### 飞书卡片实时更新

每个状态变更时更新飞书卡片，展示当前进度和结果。

---

## 五、日志与监控系统

### 5.1 日志架构

**应用层日志**:
- loguru → logs/app-{date}.log
- 结构化 JSON 格式
- 按天轮转，保留 30 天

**任务追踪日志**:
- 每个任务独立日志文件: logs/tasks/{task_id}.log
- 记录完整执行过程

### 5.2 监控指标

**Prometheus Metrics**:
| 指标名 | 说明 |
|--------|------|
| tasks_received_total | 收到的任务总数 |
| tasks_completed_total | 完成的任务总数 |
| tasks_failed_total | 失败的任务总数 |
| task_duration_seconds | 任务执行时长 |
| queue_size | 当前队列大小 |
| llm_inference_duration | LLM推理时长 |
| opencode_execution_duration | OpenCode执行时长 |

### 5.3 告警规则

**告警渠道**: 飞书机器人

| 告警 | 条件 | 消息 |
|------|------|------|
| 队列积压 | queue_size > 15 | ⚠️ 任务队列积压 |
| 连续失败 | 连续 3 个任务失败 | 🚨 连续任务失败 |
| LLM超时 | inference > 30s | ⏰ LLM 响应超时 |
| 资源紧张 | CPU/内存 > 90% | 💻 系统资源紧张 |
| 服务不可用 | OpenCode 连续 3 次连接失败 | 🔌 OpenCode 服务不可用 |

---

## 六、配置汇总

```yaml
# config.yaml 完整配置示例

wechat:
  listener_type: "uiautomation"
  platform: "wework"
  uiautomation:
    poll_interval: 0.5
    max_history: 100

workflow:
  max_queue_size: 20
  confirmation_timeout: 10800  # 3小时

opencode:
  mode: "remote"
  local:
    cli_path: "opencode"
    work_dir: "./workspace"
  remote:
    api_url: "${OPENCODE_API_URL}"
    api_key: "${OPENCODE_API_KEY}"
  interaction_timeout: 1800
  max_retries: 3

feishu:
  app_id: "${FEISHU_APP_ID}"
  app_secret: "${FEISHU_APP_SECRET}"
  table_id: "${FEISHU_TABLE_ID}"

monitoring:
  enabled: true
  prometheus_port: 9090
  log_retention_days: 30
  alert:
    feishu_webhook: "${FEISHU_ALERT_WEBHOOK}"
    queue_threshold: 15
    failure_threshold: 3

logging:
  dir: "logs"
  level: "INFO"
  retention: "30 days"
```

---

## 七、模块依赖关系

```
main.py
   │
   ├── ConfigManager
   │
   └── Application
          │
          ├── ListenerManager
          │      ├── NtWorkListener
          │      ├── WebhookListener
          │      └── UIAutomationListener
          │
          ├── MessageGateway
          │
          ├── TaskFilter (Qwen3-0.6B)
          │
          ├── TaskQueue
          │
          ├── TaskAnalyzer
          │
          ├── DecisionManager
          │      └── FeishuCardClient
          │
          ├── CodeExecutor
          │      └── OpenCodeClient
          │
          ├── FeishuRecorder
          │
          └── MonitoringService
                 ├── Logger
                 ├── Metrics
                 └── Alerter
```

---

## 八、异常处理体系

```
WeChatAutomationError (基类)
│
├── ListenerError
│   ├── ConnectionError
│   └── MessageError
│
├── GatewayError
│   ├── ValidationError
│   └── DuplicateError
│
├── FilterError
│   └── LLMError
│
├── QueueError
│   ├── QueueFullError
│   └── TimeoutError
│
├── AnalyzerError
│
├── DecisionError
│   └── ConfirmationTimeoutError
│
├── ExecutorError
│   ├── ExecutionError
│   ├── SecurityViolationError
│   └── InteractionTimeoutError
│
└── RecorderError
    └── FeishuAPIError
```

---

## 九、部署架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        生产环境部署                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│   │   Nginx     │────▶│  FastAPI    │────▶│   Redis     │       │
│   │  (反向代理) │     │  (API服务)  │     │  (队列缓存) │       │
│   └─────────────┘     └─────────────┘     └─────────────┘       │
│                              │                                   │
│                              ▼                                   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    核心服务                              │   │
│   │                                                          │   │
│   │   ┌───────────┐  ┌───────────┐  ┌───────────┐          │   │
│   │   │ Listener  │  │  Filter   │  │ Executor  │          │   │
│   │   │  Service  │  │  Service  │  │  Service  │          │   │
│   │   │ (Qwen)    │  │ (Qwen)    │  │(OpenCode) │          │   │
│   │   └───────────┘  └───────────┘  └───────────┘          │   │
│   │                                                          │   │
│   └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│   │  PostgreSQL │     │ Prometheus  │     │   Grafana   │       │
│   │  (持久化)   │     │  (指标)     │     │  (监控)     │       │
│   └─────────────┘     └─────────────┘     └─────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 十、开发计划

### Phase 1: 核心框架重构
- [ ] 重构监听层，实现 BaseListener 抽象
- [ ] 实现 MessageGateway 网关层
- [ ] 实现 TaskQueue 队列管理

### Phase 2: 过滤层实现
- [ ] 集成 Qwen3-0.6B 模型
- [ ] 实现任务分类功能
- [ ] 实现语义去重功能

### Phase 3: 决策层实现
- [ ] 实现飞书卡片推送
- [ ] 实现飞书回调接收
- [ ] 实现决策状态管理

### Phase 4: 执行层优化
- [ ] 实现 OpenCode 混合调用模式
- [ ] 实现执行中交互处理
- [ ] 实现进度实时同步

### Phase 5: 监控与日志
- [ ] 集成 Prometheus 指标
- [ ] 实现告警机制
- [ ] 完善 Grafana 面板

---

*文档版本: v1.0*
*更新时间: 2024-01-15*
