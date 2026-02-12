# CLI 入口与依赖注入范式

极简 CLI 入口、按需实例化与单例/Depends 的通用做法。

## 1. 极简 CLI 入口

- **单命令入口**：安装后一个主命令（如 `mybot`）直接进入交互模式，无子命令，降低心智负担。若需要子命令，可后续用 `click`/`ty` 等增加 `mybot run`、`mybot config` 等。
- **入口函数**：CLI 入口函数只做两件事：组装依赖（get_agent、audit、console 等），调用「运行交互」的单一函数（如 `run_interactive_ui(...)`），不在入口里写业务逻辑。
- **全局实例**：轻量对象（如 Console、DB 连接管理器）可在模块级初始化；重型对象（Agent、记忆管理器）用懒加载，在首次使用时创建并缓存。

## 2. 按需实例化与缓存

- **模式**：维护一个 `agents: dict = {}` 或类似缓存，通过 `get_agent(agent_type)` 获取。若 `agent_type` 不在缓存中，则创建实例并写入缓存再返回；否则直接返回。
- **好处**：避免进程内重复创建大模型客户端或重型依赖；同一类型 Agent 共享状态（如记忆）时也更一致。
- **类型校验**：get_agent 内校验 agent_type 是否在允许枚举内，非法则打印错误并 `raise SystemExit(1)`，便于脚本与 CI 获得明确退出码。

## 3. 单例容器（用于 API/服务端）

- **场景**：Web API 或长驻进程需要与 CLI 共用同一套「DB、审计、Agent、Planner、QA」等实例时，可抽象一个「单例容器」类（如 `_Singletons`），用类方法 + 私有类变量做懒加载。
- **示例**：`_Singletons.db_manager()` 首次调用时 `_db_manager = DatabaseManager()` 并返回，之后均返回同一实例。Agent 等依赖 audit、db 的，在单例内部按依赖顺序初始化（先 db_manager，再 audit_trail，再 agents）。
- **会话 ID**：服务端可在进程启动时生成一个 `_session_id = str(uuid.uuid4())`，整个进程内复用，便于日志与审计关联。

## 4. FastAPI Depends 与 CLI 对齐

- **目标**：API 层通过 `Depends(get_xxx)` 拿到与 CLI 相同的逻辑（同一套单例），避免两套初始化逻辑分叉。
- **做法**：将「创建/获取实例」的逻辑放在 `dependencies` 模块（如 `get_db_manager()`、`get_agent(agent_type)`），CLI 与 API 都从同一处导入并调用；API 中 `def get_agent(agent_type: str) -> Agent` 可依赖 `get_agents()` 并做类型校验，非法时 `raise HTTPException` 或 `raise ValueError`，由框架处理。

## 5. 可复用要点小结

- CLI 入口：单命令、只做依赖组装 + 调用一个 run_xxx。
- 重型依赖：懒加载 + 缓存（dict 或单例类），通过 get_xxx() 统一获取。
- 单例容器：类方法 + 私有类变量，按依赖顺序初始化，便于 API 与 CLI 共用。
- 依赖模块：get_xxx 函数集中放在 dependencies，CLI 与 FastAPI Depends 共用，保证行为一致。
