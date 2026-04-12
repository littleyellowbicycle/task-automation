# WeChat Task Automation System - 架构重构设计文档 v2.0

## 一、重构背景与动机

### 1.1 当前架构问题

**核心痛点：飞书回调的内网穿透问题**

当前架构中，飞书卡片按钮点击后的回调需要访问本地 HTTP 服务器（`CallbackServer` 在 `0.0.0.0:8080`），而飞书服务器在公网，无法直接访问内网地址。现有方案依赖 ngrok/cloudflare 等内网穿透工具，存在以下问题：

- ngrok 免费版每次重启 URL 变化，需要重新配置飞书应用
- 内网穿透稳定性差，连接断开导致决策回调丢失
- 安全风险：内网服务直接暴露到公网
- 运维复杂度高，需要额外维护穿透服务

**架构层面的耦合问题**：

1. **所有模块紧耦合在一个进程中**：`WorkflowOrchestrator` 把 Gateway、Filter、Queue、Analyzer、Decision、Executor、Feishu 全部耦合在一起，无法独立部署和扩展
2. **CallbackServer 和 FeishuServer 重复**：存在两套 HTTP 服务（`callback_server` 用 FastAPI，`feishu_recorder/server.py` 用标准库 HTTPServer），职责重叠
3. **消息流向混乱**：监听层→网关层→过滤层→队列层→分析层→决策层→执行层→记录层，全部在一个进程内同步/异步混合调用，难以调试和维护
4. **无法水平扩展**：单进程架构，Filter（GPU 推理）和 Executor（代码执行）资源需求差异大，无法独立伸缩

### 1.2 重构目标

1. **消除内网穿透依赖**：网关作为唯一公网入口，飞书回调直接打到网关，无需穿透
2. **模块解耦**：各业务模块通过网关 REST API 通信，可独立部署
3. **网关只做分发**：网关不执行具体业务逻辑，只负责消息校验、标准化、路由分发
4. **保留向后兼容**：支持单进程模式（开发/测试）和分布式模式（生产）

---

## 二、新架构总览

### 2.1 架构图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              外部系统                                        │
│                                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│   │  企业微信     │    │   飞书服务器   │    │  用户浏览器   │                  │
│   │  (群消息)     │    │  (卡片回调)   │    │  (管理界面)   │                  │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                  │
│          │                   │                   │                           │
└──────────┼───────────────────┼───────────────────┼───────────────────────────┘
           │                   │                   │
           ▼                   ▼                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                    ┌─────────────────────────────────┐                       │
│                    │      API Gateway (公网部署)       │                       │
│                    │      唯一对外入口，不做业务逻辑     │                       │
│                    │                                  │                       │
│                    │  ┌────────────────────────────┐  │                       │
│                    │  │     REST API Endpoints      │  │                       │
│                    │  │                             │  │                       │
│                    │  │ 对外接口 (公网可达):          │  │                       │
│                    │  │  POST /api/v1/listener/msg   │  │ ← 监听层推送         │
│                    │  │  POST /api/v1/feishu/callback│  │ ← 飞书卡片回调       │
│                    │  │  GET  /health                │  │                      │
│                    │  │                             │  │                       │
│                    │  │ 内部接口 (内网通信):          │  │                       │
│                    │  │  POST /api/v1/decisions      │  │ ← 决策层回调         │
│                    │  │  POST /api/v1/analysis/done  │  │ ← 分析层回调         │
│                    │  │  POST /api/v1/execution/done │  │ ← 执行层回调         │
│                    │  │  POST /api/v1/recording/done │  │ ← 记录层回调         │
│                    │  │  GET  /api/v1/tasks/{id}     │  │                      │
│                    │  │  GET  /api/v1/queue/status   │  │                      │
│                    │  └────────────────────────────┘  │                       │
│                    │                                  │                       │
│                    │  ┌────────────────────────────┐  │                       │
│                    │  │      内部核心能力             │  │                       │
│                    │  │  - 消息校验 & 标准化          │  │                       │
│                    │  │  - 消息去重                   │  │                       │
│                    │  │  - 任务状态管理 (内存+持久化)  │  │                       │
│                    │  │  - 消息路由 & 分发            │  │                       │
│                    │  │  - 队列管理                   │  │                       │
│                    │  └────────────────────────────┘  │                       │
│                    └─────────────────────────────────┘                       │
│                                      │                                       │
│              ┌───────────────────────┼───────────────────────┐               │
│              │                       │                       │               │
│              ▼                       ▼                       ▼               │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│   │  过滤 & 分析模块  │  │    决策模块       │  │    执行模块       │          │
│   │  (可独立部署)     │  │   (可独立部署)    │  │   (可独立部署)    │          │
│   │                   │  │                   │  │                   │          │
│   │  职责:            │  │  职责:            │  │  职责:            │          │
│   │  - 任务分类       │  │  - 发送审批卡片   │  │  - 代码生成执行   │          │
│   │  - 语义去重       │  │  - 接收用户决策   │  │  - 进度上报       │          │
│   │  - 复杂度评估     │  │  - 超时处理       │  │  - 交互处理       │          │
│   │  - 摘要提取       │  │                   │  │                   │          │
│   │                   │  │                   │  │                   │          │
│   │  回调网关:        │  │  回调网关:        │  │  回调网关:        │          │
│   │  POST /analysis/  │  │  POST /decisions  │  │  POST /execution/ │          │
│   │       done        │  │                   │  │       done        │          │
│   └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                      │                       │
│                                                      ▼                       │
│                                           ┌──────────────────┐               │
│                                           │    记录模块       │               │
│                                           │   (可独立部署)    │               │
│                                           │                   │               │
│                                           │  职责:            │               │
│                                           │  - 写入飞书表格   │               │
│                                           │  - 更新任务状态   │               │
│                                           │  - 发送通知卡片   │               │
│                                           │                   │               │
│                                           │  回调网关:        │               │
│                                           │  POST /recording/ │               │
│                                           │       done        │               │
│                                           └──────────────────┘               │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    监听层 (独立进程/机器)                              │   │
│   │                                                                      │   │
│   │   NtWorkListener / UIAutomationListener / WebhookListener            │   │
│   │   职责: 只负责消息捕获，通过 HTTP POST 推送到网关                     │   │
│   │   推送地址: POST /api/v1/listener/msg                                │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心设计原则

| 原则 | 说明 |
|------|------|
| **网关无状态业务** | 网关不做任务分析、决策、执行等业务逻辑，只做消息校验、标准化、路由 |
| **回调即分发** | 所有模块完成工作后，通过回调网关 API 通知结果，网关再分发到下一环节 |
| **模块自治** | 每个模块独立管理自己的状态，通过网关 API 与其他模块交互 |
| **部署灵活** | 支持单进程模式（所有模块在同一进程）和分布式模式（模块独立部署） |

---

## 三、网关详细设计

### 3.1 网关职责边界

**网关做什么**：
- 消息校验（格式检查、必填字段验证）
- 消息标准化（统一为 `StandardMessage` 格式）
- 消息去重（基于 msg_id 的去重缓存）
- 任务状态管理（维护任务状态机）
- 队列管理（任务排队、优先级、超时）
- 消息路由分发（根据消息类型和任务状态，推送到对应模块）
- 飞书回调接收（URL 验证、事件解析、路由到决策模块）

**网关不做什么**：
- ❌ 不做任务分类（由过滤模块负责）
- ❌ 不做任务分析（由分析模块负责）
- ❌ 不做用户决策（由决策模块负责）
- ❌ 不做代码执行（由执行模块负责）
- ❌ 不做飞书 API 调用（由决策/记录模块负责）

### 3.2 API 接口设计

#### 对外接口（公网可达）

```yaml
# 监听层消息推送
POST /api/v1/listener/msg:
  description: 监听层推送捕获的原始消息
  request:
    msg_id: string          # 消息ID
    content: string         # 消息内容
    sender_id: string       # 发送者ID
    sender_name: string     # 发送者名称
    conversation_id: string # 会话ID
    conversation_type: string # private/group
    timestamp: string       # ISO8601时间戳
    msg_type: string        # text/image
    platform: string        # wework/wechat
    listener_type: string   # uiautomation/ntwork/webhook
  response:
    code: int
    message: string
    task_id: string | null  # 如果被识别为任务，返回任务ID

# 飞书卡片回调
POST /api/v1/feishu/callback:
  description: 接收飞书卡片按钮点击回调
  request:
    # 飞书标准回调格式
    type: string            # url_verification / event
    challenge: string       # URL验证时返回
    event:                  # 事件数据
      type: string          # card.action.trigger
      action:
        value:
          task_id: string
          action: string    # approve/reject/later
  response:
    # URL验证: {"challenge": "xxx"}
    # 事件回调: {"code": 0}

# 健康检查
GET /health:
  response:
    status: string
    timestamp: string
    components:
      queue: { size: int, max: int }
      tasks: { pending: int, processing: int }
```

#### 内部接口（模块间通信）

```yaml
# 决策层回调
POST /api/v1/decisions:
  description: 决策模块通知网关用户决策结果
  request:
    task_id: string
    action: string          # approve/reject/later/timeout
    user_id: string | null
    timestamp: string
  response:
    code: int
    message: string

# 分析层回调
POST /api/v1/analysis/done:
  description: 分析模块通知网关任务分析完成
  request:
    task_id: string
    summary: string
    tech_stack: string[]
    core_features: string[]
    complexity: string      # simple/medium/complex
    category: string | null
  response:
    code: int
    message: string

# 执行层回调
POST /api/v1/execution/done:
  description: 执行模块通知网关任务执行完成
  request:
    task_id: string
    success: boolean
    stdout: string
    stderr: string
    repo_url: string | null
    files_created: string[]
    files_modified: string[]
    duration: float
    error_message: string | null
  response:
    code: int
    message: string

# 执行层进度上报
POST /api/v1/execution/progress:
  description: 执行模块上报执行进度
  request:
    task_id: string
    progress: int           # 0-100
    current_step: string
    steps: Array<{name: string, status: string}>
  response:
    code: int
    message: string

# 记录层回调
POST /api/v1/recording/done:
  description: 记录模块通知网关记录完成
  request:
    task_id: string
    record_id: string       # 飞书记录ID
    success: boolean
  response:
    code: int
    message: string

# 任务查询
GET /api/v1/tasks/{task_id}:
  response:
    task_id: string
    status: string
    created_at: string
    updated_at: string
    summary: string | null
    decision: string | null
    execution_result: object | null

# 任务列表
GET /api/v1/tasks:
  query:
    status: string          # pending/analyzing/awaiting_confirmation/executing/completed/failed
    page: int
    page_size: int
  response:
    total: int
    items: Task[]

# 队列状态
GET /api/v1/queue/status:
  response:
    queue_size: int
    max_size: int
    current_task: string | null
    pending_count: int
    stats: object
```

### 3.3 消息路由逻辑

网关收到消息后，根据消息来源和任务当前状态，决定分发到哪个模块：

```
消息来源判断:
├── 监听层消息 (/api/v1/listener/msg)
│   └── 校验 → 标准化 → 去重 → 分发到过滤&分析模块
│
├── 飞书回调 (/api/v1/feishu/callback)
│   ├── URL验证 → 直接返回challenge
│   └── 卡片回调 → 解析action → 分发到决策模块
│
├── 分析完成 (/api/v1/analysis/done)
│   └── 更新任务状态 → 分发到决策模块（发送审批卡片）
│
├── 决策结果 (/api/v1/decisions)
│   ├── approve → 更新状态 → 分发到执行模块
│   ├── reject → 更新状态 → 分发到记录模块
│   ├── later → 更新状态 → 放回队列
│   └── timeout → 更新状态 → 分发到记录模块
│
├── 执行完成 (/api/v1/execution/done)
│   └── 更新任务状态 → 分发到记录模块
│
└── 记录完成 (/api/v1/recording/done)
    └── 更新任务状态 → 任务结束
```

### 3.4 任务状态管理

网关维护全局任务状态机：

```
RECEIVED → FILTERING → ANALYZING → AWAITING_CONFIRMATION → EXECUTING → RECORDING → COMPLETED
    │          │           │               │                    │           │
    │          │           │               ├──── REJECTED ──────┼───────────┤
    │          │           │               │                    │           │
    │          │           │               ├──── LATER ─────────┤           │
    │          │           │               │                    │           │
    │          │           │               └──── TIMEOUT ───────┼───────────┤
    │          │           │                                    │           │
    │          │           │                                    └── FAILED ─┤
    │          │           │                                                │
    └──────────┴───────────┴────────────────────────────────────────────────┘
                                                                              │
                                                                         CANCELLED
```

### 3.5 数据模型

```python
@dataclass
class TaskState:
    task_id: str
    status: TaskStatus
    raw_message: str
    standard_message: Optional[StandardMessage]
    analysis_result: Optional[AnalysisResult]
    decision: Optional[str]
    execution_result: Optional[ExecutionResult]
    recording_result: Optional[RecordingResult]
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str]
    retry_count: int
    metadata: Dict[str, Any]

class TaskStatus(str, Enum):
    RECEIVED = "received"
    FILTERING = "filtering"
    ANALYZING = "analyzing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTING_WAITING_INPUT = "executing_waiting_input"
    RECORDING = "recording"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    LATER = "later"
```

---

## 四、各模块详细设计

### 4.1 监听层 (Listener Layer)

**部署位置**: 内网（需要访问企业微信客户端）

**职责**: 只负责消息捕获，通过 HTTP POST 推送到网关

**变化点**:
- 原来：监听器通过回调函数把消息传给 `WorkflowOrchestrator`
- 现在：监听器通过 HTTP POST 把消息推送到网关 `/api/v1/listener/msg`

```python
class BaseListener(ABC):
    @abstractmethod
    async def start(self) -> None: ...
    
    @abstractmethod
    async def stop(self) -> None: ...
    
    @abstractmethod
    async def send(self, conversation_id: str, content: str) -> bool: ...

class ListenerPushClient:
    """将捕获的消息推送到网关"""
    
    def __init__(self, gateway_url: str):
        self.gateway_url = gateway_url
    
    async def push_message(self, raw_message: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.gateway_url}/api/v1/listener/msg",
                json=raw_message,
                timeout=10.0,
            )
            return resp.json()
```

### 4.2 过滤 & 分析模块 (Filter & Analysis Worker)

**部署位置**: 可与网关同机或独立部署（需要 GPU 资源运行 Qwen3-0.6B）

**职责**:
1. 从网关接收待分析消息（网关主动推送或模块轮询）
2. 执行任务分类（是否为任务）
3. 执行语义去重
4. 执行任务分析（摘要、技术栈、功能点、复杂度）
5. 将分析结果回调给网关

**通信方式**:

方案 A — 网关推送模式：
```
网关 → POST /worker/analyze → 分析模块
分析模块 → POST /api/v1/analysis/done → 网关
```

方案 B — 模块拉取模式：
```
分析模块 → GET /api/v1/tasks?status=received → 网关（轮询待分析任务）
分析模块 → POST /api/v1/analysis/done → 网关（回调分析结果）
```

**推荐方案 A**（网关推送），延迟更低。模块暴露一个 `/worker/analyze` 接口，网关收到新消息后主动推送。

```python
class FilterAnalysisWorker:
    def __init__(self, gateway_url: str, port: int = 8001):
        self.gateway_url = gateway_url
        self.port = port
        self.app = FastAPI(title="Filter & Analysis Worker")
        self.task_filter = TaskFilter()
        self.task_analyzer = TaskAnalyzer()
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.post("/worker/analyze")
        async def analyze_message(request: AnalyzeRequest):
            # 1. 任务分类
            filter_result, dedup_result = self.task_filter.filter(
                request.content, request.msg_id
            )
            
            if dedup_result.is_duplicate or not filter_result.is_task:
                # 回调网关：非任务或重复
                await self._callback_gateway(request.task_id, {
                    "is_task": False,
                    "reason": "duplicate" if dedup_result.is_duplicate else "not_task"
                })
                return {"code": 0, "action": "skipped"}
            
            # 2. 任务分析
            analysis = self.task_analyzer.analyze(request.content)
            
            # 3. 回调网关
            await self._callback_gateway(request.task_id, {
                "is_task": True,
                "summary": analysis["summary"],
                "tech_stack": analysis["tech_stack"],
                "core_features": analysis["core_features"],
                "complexity": analysis["estimated_complexity"],
            })
            
            return {"code": 0, "action": "analyzed"}
    
    async def _callback_gateway(self, task_id: str, data: dict):
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.gateway_url}/api/v1/analysis/done",
                json={"task_id": task_id, **data},
                timeout=10.0,
            )
```

### 4.3 决策模块 (Decision Module)

**部署位置**: 可与网关同机或独立部署

**职责**:
1. 接收网关的分析完成通知
2. 通过飞书 API 发送审批卡片
3. 接收飞书卡片回调（通过网关转发）
4. 管理确认超时
5. 将决策结果回调给网关

**关键变化 — 飞书回调不再直接到决策模块**：

```
旧流程: 飞书服务器 → (内网穿透) → 本地 CallbackServer → DecisionManager
新流程: 飞书服务器 → (公网) → 网关 /api/v1/feishu/callback → 决策模块 /worker/decision/callback
```

飞书卡片按钮的 URL 配置为网关地址：
- 确认: `{GATEWAY_PUBLIC_URL}/api/v1/feishu/callback`
- 不再需要配置内网穿透！

```python
class DecisionWorker:
    def __init__(self, gateway_url: str, port: int = 8002):
        self.gateway_url = gateway_url
        self.port = port
        self.app = FastAPI(title="Decision Worker")
        self.feishu_bridge = FeishuBridge()
        self._pending: Dict[str, PendingConfirmation] = {}
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.post("/worker/decision/request")
        async def request_decision(request: DecisionRequest):
            # 1. 发送飞书审批卡片
            # 卡片回调URL指向网关，而非本模块
            callback_url = f"{self.gateway_url}/api/v1/feishu/callback"
            self.feishu_bridge.send_approval_card(
                request.task_record, callback_url=callback_url
            )
            
            # 2. 记录待确认任务
            self._pending[request.task_id] = PendingConfirmation(
                task_id=request.task_id,
                created_at=time.time(),
                timeout=request.timeout,
            )
            
            # 3. 启动超时检查
            asyncio.create_task(self._check_timeout(request.task_id))
            
            return {"code": 0}
        
        @self.app.post("/worker/decision/callback")
        async def handle_decision_callback(request: DecisionCallback):
            # 网关转发的飞书回调
            task_id = request.task_id
            action = request.action
            
            # 回调网关
            await self._callback_gateway(task_id, action)
            
            return {"code": 0}
    
    async def _check_timeout(self, task_id: str):
        pending = self._pending.get(task_id)
        if not pending:
            return
        await asyncio.sleep(pending.timeout)
        if task_id in self._pending and not self._pending[task_id].confirmed:
            await self._callback_gateway(task_id, "timeout")
    
    async def _callback_gateway(self, task_id: str, action: str):
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.gateway_url}/api/v1/decisions",
                json={"task_id": task_id, "action": action},
                timeout=10.0,
            )
```

### 4.4 执行模块 (Execution Module)

**部署位置**: 可与网关同机或独立部署（需要访问 OpenCode 服务）

**职责**:
1. 接收网关的执行请求
2. 调用 OpenCode 执行代码生成
3. 上报执行进度
4. 处理执行中交互
5. 将执行结果回调给网关

```python
class ExecutionWorker:
    def __init__(self, gateway_url: str, port: int = 8003):
        self.gateway_url = gateway_url
        self.port = port
        self.app = FastAPI(title="Execution Worker")
        self.code_executor = CodeExecutor()
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.post("/worker/execution/request")
        async def execute_task(request: ExecutionRequest):
            # 1. 执行代码生成
            result = await self.code_executor.execute_async(
                instruction=f"创建代码: {request.summary}",
                task_id=request.task_id,
            )
            
            # 2. 回调网关
            await self._callback_gateway(request.task_id, {
                "success": result.success,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "repo_url": result.repo_url,
                "files_created": result.files_created,
                "files_modified": result.files_modified,
                "duration": result.duration,
                "error_message": result.error_message,
            })
            
            return {"code": 0}
        
        @self.app.post("/worker/execution/cancel")
        async def cancel_execution(request: CancelRequest):
            self.code_executor.cancel(request.task_id)
            return {"code": 0}
    
    async def _callback_gateway(self, task_id: str, data: dict):
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.gateway_url}/api/v1/execution/done",
                json={"task_id": task_id, **data},
                timeout=10.0,
            )
```

### 4.5 记录模块 (Recording Module)

**部署位置**: 可与网关同机或独立部署

**职责**:
1. 接收网关的记录请求
2. 写入飞书多维表格
3. 发送通知卡片
4. 将记录结果回调给网关

```python
class RecordingWorker:
    def __init__(self, gateway_url: str, port: int = 8004):
        self.gateway_url = gateway_url
        self.port = port
        self.app = FastAPI(title="Recording Worker")
        self.feishu_client = FeishuClient()
        self.feishu_bridge = FeishuBridge()
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.post("/worker/recording/request")
        async def record_task(request: RecordingRequest):
            # 1. 写入飞书表格
            self.feishu_client.create_record(request.task_record)
            
            # 2. 发送通知卡片
            message = f"任务已{'成功完成' if request.success else '失败'}"
            self.feishu_bridge.send_notification_card(request.task_record, message)
            
            # 3. 回调网关
            await self._callback_gateway(request.task_id, {
                "success": True,
                "record_id": request.task_record.task_id,
            })
            
            return {"code": 0}
    
    async def _callback_gateway(self, task_id: str, data: dict):
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.gateway_url}/api/v1/recording/done",
                json={"task_id": task_id, **data},
                timeout=10.0,
            )
```

---

## 五、完整消息流程

### 5.1 正常任务流程

```
1. 监听层捕获消息
   Listener → POST /api/v1/listener/msg → Gateway

2. 网关处理
   Gateway: 校验 → 标准化 → 去重 → 创建 TaskState(RECEIVED)
   Gateway → POST /worker/analyze → FilterAnalysisWorker

3. 过滤 & 分析
   Worker: 分类 → 去重 → 分析
   Worker → POST /api/v1/analysis/done → Gateway

4. 网关更新状态
   Gateway: TaskState → ANALYZING → AWAITING_CONFIRMATION
   Gateway → POST /worker/decision/request → DecisionWorker

5. 决策模块发送审批卡片
   Worker: 构建卡片 → 飞书API发送（卡片回调URL指向网关）

6. 用户点击飞书卡片按钮
   飞书服务器 → POST /api/v1/feishu/callback → Gateway

7. 网关转发到决策模块
   Gateway → POST /worker/decision/callback → DecisionWorker

8. 决策模块回调网关
   Worker → POST /api/v1/decisions → Gateway

9. 网关根据决策分发
   Gateway: TaskState → APPROVED
   Gateway → POST /worker/execution/request → ExecutionWorker

10. 执行模块执行任务
    Worker: 调用OpenCode → 上报进度
    Worker → POST /api/v1/execution/progress → Gateway

11. 执行完成回调
    Worker → POST /api/v1/execution/done → Gateway

12. 网关分发到记录模块
    Gateway: TaskState → RECORDING
    Gateway → POST /worker/recording/request → RecordingWorker

13. 记录完成回调
    Worker → POST /api/v1/recording/done → Gateway

14. 任务完成
    Gateway: TaskState → COMPLETED
```

### 5.2 非任务消息流程

```
1. 监听层捕获消息 → Gateway
2. Gateway → FilterAnalysisWorker
3. Worker 判定为非任务 → POST /api/v1/analysis/done {is_task: false}
4. Gateway: TaskState → CANCELLED (或直接丢弃)
```

### 5.3 用户拒绝流程

```
1-8. 同正常流程
9. Gateway: TaskState → REJECTED
10. Gateway → POST /worker/recording/request → RecordingWorker (记录拒绝)
11. 记录完成 → Gateway → COMPLETED
```

---

## 六、部署架构

### 6.1 最小部署（单机模式）

所有模块在同一台机器上运行，通过 localhost 通信：

```
┌─────────────────────────────────────────────────┐
│                   单机部署                        │
│                                                   │
│   ┌───────────────────────────────────────────┐  │
│   │           API Gateway (:8000)              │  │
│   │     公网入口，飞书回调直接打到此处          │  │
│   └───────┬──────────┬──────────┬─────────────┘  │
│           │          │          │                  │
│           ▼          ▼          ▼                  │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│   │Analysis  │ │Decision  │ │Execution │         │
│   │Worker    │ │Worker    │ │Worker    │         │
│   │(:8001)   │ │(:8002)   │ │(:8003)   │         │
│   └──────────┘ └──────────┘ └──────────┘         │
│                          │                        │
│                          ▼                        │
│                   ┌──────────┐                    │
│                   │Recording │                    │
│                   │Worker    │                    │
│                   │(:8004)   │                    │
│                   └──────────┘                    │
│                                                   │
│   ┌───────────────────────────────────────────┐  │
│   │         WeChat Listener (独立进程)          │  │
│   │         需要访问企业微信客户端               │  │
│   └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

**优势**: 无需内网穿透！网关绑定公网 IP 或通过云服务器部署即可。

### 6.2 分布式部署

```
┌─────────────────────────────────────────────────────────────────┐
│                        云服务器 (公网)                           │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    API Gateway (:8000)                    │   │
│   │            公网IP/域名，飞书回调直接到达                   │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────────┬──────────────────────────────┘
                                   │ (内网通信)
           ┌───────────────────────┼───────────────────────┐
           ▼                       ▼                       ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  GPU 服务器       │  │  执行服务器       │  │  内网机器         │
│                   │  │                   │  │                   │
│  Analysis Worker  │  │  Execution Worker │  │  WeChat Listener  │
│  (Qwen3-0.6B)    │  │  (OpenCode)       │  │  (企业微信)       │
│                   │  │                   │  │                   │
│  Decision Worker  │  │  Recording Worker │  │                   │
│  (飞书API)        │  │  (飞书API)        │  │                   │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### 6.3 开发模式（单进程）

开发/测试时，所有模块在同一进程内运行，通过函数调用通信（无需启动多个 HTTP 服务）：

```python
class InProcessGateway:
    """开发模式：所有模块在同一进程内"""
    
    def __init__(self):
        self.filter_worker = FilterAnalysisWorker(gateway_url="in-process")
        self.decision_worker = DecisionWorker(gateway_url="in-process")
        self.execution_worker = ExecutionWorker(gateway_url="in-process")
        self.recording_worker = RecordingWorker(gateway_url="in-process")
    
    async def _dispatch_to_analysis(self, task_id: str, content: str):
        # 直接调用，不走HTTP
        result = await self.filter_worker.analyze(task_id, content)
        await self._handle_analysis_done(result)
```

---

## 七、与旧架构的映射关系

| 旧模块 | 新架构位置 | 变化说明 |
|--------|-----------|---------|
| `MessageGateway` | `API Gateway` 核心逻辑 | 保留校验/标准化/去重，新增路由分发和任务状态管理 |
| `CallbackServer` | `API Gateway` 的 `/api/v1/feishu/callback` | 合并到网关，消除重复服务 |
| `FeishuServer` | 删除 | 被 API Gateway 统一替代 |
| `WorkflowOrchestrator` | `API Gateway` 路由逻辑 | 编排逻辑变为网关的路由分发 |
| `TaskFilter` | `FilterAnalysisWorker` | 独立为可部署的 Worker |
| `TaskAnalyzer` | `FilterAnalysisWorker` | 合并到过滤&分析 Worker |
| `DecisionManager` | `DecisionWorker` | 独立为可部署的 Worker |
| `CodeExecutor` | `ExecutionWorker` | 独立为可部署的 Worker |
| `FeishuBridge` | `DecisionWorker` + `RecordingWorker` | 拆分：审批卡片归决策，通知/记录归记录 |
| `FeishuClient` | `RecordingWorker` | 独立为可部署的 Worker |
| `TaskQueue` | `API Gateway` 内部 | 队列管理留在网关内 |
| `BaseListener` | `Listener Layer` | 新增 `ListenerPushClient` 推送到网关 |
| `Application` | `API Gateway` | 应用编排变为网关 |

---

## 八、项目结构变更

```
src/
├── gateway/                    # API Gateway (核心重构)
│   ├── __init__.py
│   ├── app.py                  # FastAPI 应用主入口
│   ├── routes/                 # 路由定义
│   │   ├── __init__.py
│   │   ├── listener.py         # /api/v1/listener/msg
│   │   ├── feishu_callback.py  # /api/v1/feishu/callback
│   │   ├── decisions.py        # /api/v1/decisions
│   │   ├── analysis.py         # /api/v1/analysis/done
│   │   ├── execution.py        # /api/v1/execution/done, /progress
│   │   ├── recording.py        # /api/v1/recording/done
│   │   ├── tasks.py            # /api/v1/tasks
│   │   └── queue.py            # /api/v1/queue/status
│   ├── core/                   # 网关核心逻辑
│   │   ├── __init__.py
│   │   ├── message_processor.py # 消息校验、标准化、去重 (原 MessageGateway)
│   │   ├── task_manager.py      # 任务状态管理
│   │   ├── router.py            # 消息路由分发
│   │   └── queue_manager.py     # 队列管理 (原 TaskQueue)
│   ├── models/                 # 数据模型
│   │   ├── __init__.py
│   │   ├── messages.py         # StandardMessage 等
│   │   ├── tasks.py            # TaskState, TaskStatus
│   │   └── requests.py         # API 请求/响应模型
│   └── dispatcher/             # 分发器
│       ├── __init__.py
│       ├── http_dispatcher.py  # HTTP 推送分发
│       └── inprocess_dispatcher.py # 进程内调用分发(开发模式)
│
├── workers/                    # 各业务 Worker
│   ├── __init__.py
│   ├── filter_analysis/        # 过滤 & 分析 Worker
│   │   ├── __init__.py
│   │   ├── app.py              # FastAPI Worker 入口
│   │   └── handler.py          # 业务处理逻辑
│   ├── decision/               # 决策 Worker
│   │   ├── __init__.py
│   │   ├── app.py
│   │   └── handler.py
│   ├── execution/              # 执行 Worker
│   │   ├── __init__.py
│   │   ├── app.py
│   │   └── handler.py
│   └── recording/              # 记录 Worker
│       ├── __init__.py
│       ├── app.py
│       └── handler.py
│
├── listener/                   # 监听层 (原 wechat_listener)
│   ├── __init__.py
│   ├── base.py
│   ├── factory.py
│   ├── models.py
│   ├── parser.py
│   ├── push_client.py          # 新增：推送到网关的客户端
│   └── listeners/
│       ├── __init__.py
│       ├── network_listener.py
│       ├── uiautomation_listener.py
│       └── webhook_listener.py
│
├── shared/                     # 共享模块
│   ├── __init__.py
│   ├── config/                 # 配置管理
│   ├── exceptions/             # 异常体系
│   ├── models/                 # 共享数据模型
│   └── utils/                  # 工具函数
│
├── callback_server/            # 保留，但标记为 deprecated
├── feishu_bot/                 # 保留，但标记为 deprecated
└── feishu_recorder/            # 保留，但标记为 deprecated
```

---

## 九、配置变更

### 9.1 新增配置项

```yaml
gateway:
  host: "0.0.0.0"
  port: 8000
  public_url: "https://your-domain.com"  # 公网访问地址，用于飞书回调URL
  workers:
    filter_analysis:
      url: "http://localhost:8001"        # 分析Worker地址
      timeout: 30
    decision:
      url: "http://localhost:8002"        # 决策Worker地址
      timeout: 10
    execution:
      url: "http://localhost:8003"        # 执行Worker地址
      timeout: 10
    recording:
      url: "http://localhost:8004"        # 记录Worker地址
      timeout: 10
  mode: "distributed"  # distributed | standalone
  # standalone: 所有Worker在同一进程内运行
  # distributed: Worker独立部署，通过HTTP通信

listener:
  gateway_url: "http://localhost:8000"    # 网关地址，监听层推送消息用
```

### 9.2 飞书应用配置变更

飞书应用的事件订阅 URL 配置：
```
旧: https://xxx.ngrok.io/feishu/callback  (需要内网穿透)
新: https://your-domain.com/api/v1/feishu/callback  (直接到网关)
```

---

## 十、迁移策略

### Phase 1: 网关重构 (优先)
1. 创建 `gateway/app.py` FastAPI 应用
2. 迁移 `MessageGateway` 的校验/标准化/去重逻辑到 `gateway/core/message_processor.py`
3. 实现任务状态管理 `gateway/core/task_manager.py`
4. 实现消息路由分发 `gateway/core/router.py`
5. 实现所有 REST API 路由
6. 实现 HTTP 分发器和进程内分发器

### Phase 2: Worker 实现
1. 实现 `FilterAnalysisWorker`（复用现有 `TaskFilter` + `TaskAnalyzer`）
2. 实现 `DecisionWorker`（复用现有 `DecisionManager` + `FeishuBridge`）
3. 实现 `ExecutionWorker`（复用现有 `CodeExecutor`）
4. 实现 `RecordingWorker`（复用现有 `FeishuClient`）

### Phase 3: 监听层适配
1. 实现 `ListenerPushClient`
2. 修改 `BaseListener` 支持推送到网关

### Phase 4: 集成测试
1. 单进程模式集成测试
2. 分布式模式集成测试
3. 飞书回调端到端测试

### Phase 5: 旧模块清理
1. 标记 `callback_server`, `feishu_recorder/server.py`, `workflow_orchestrator` 为 deprecated
2. 更新 `main.py` 使用新架构
3. 清理不再需要的内网穿透脚本

---

## 十一、ADR (Architecture Decision Records)

### ADR-001: 网关作为唯一对外入口

**状态**: 已批准

**背景**: 飞书卡片回调需要公网可达的 URL，当前依赖内网穿透工具，不稳定且不安全。

**决策**: 将 API Gateway 作为系统唯一对外入口，部署在公网可达的服务器上。所有外部回调（飞书、Webhook）统一打到网关，网关再路由到内部模块。

**影响**:
- (+) 消除内网穿透依赖
- (+) 统一入口，便于安全管控
- (+) 模块可独立部署
- (-) 增加一跳网络延迟（网关→Worker）
- (-) 网关成为单点，需要高可用保障

### ADR-002: 模块间通过 HTTP REST 通信

**状态**: 已批准

**背景**: 模块间需要通信机制。可选方案：HTTP REST、消息队列（Redis/RabbitMQ）、gRPC。

**决策**: 使用 HTTP REST 作为模块间通信协议。

**理由**:
- 实现简单，调试方便
- Python 生态 httpx/FastAPI 成熟
- 无需额外基础设施（消息队列）
- 对于当前规模（低频任务），HTTP 足够

**影响**:
- (+) 实现简单，依赖少
- (+) 可用 curl/Postman 调试
- (-) 不支持消息持久化（网关重启可能丢失进行中的任务）
- (-) 不支持发布/订阅模式

**未来考虑**: 如果任务量增大，可引入 Redis Stream 作为消息中间件，替换 HTTP 推送。

### ADR-003: 网关内保留队列管理

**状态**: 已批准

**背景**: 任务队列管理可以放在网关内，也可以独立为 Queue Service。

**决策**: 队列管理保留在网关内。

**理由**:
- 队列与任务状态管理紧密耦合
- 当前规模不需要独立队列服务
- 减少部署复杂度

**影响**:
- (+) 简化部署
- (-) 队列状态与网关进程绑定，网关重启需恢复队列

---

*文档版本: v2.0*
*更新时间: 2026-04-12*
*变更类型: 架构重构 — 网关中心化分发*
