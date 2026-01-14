# Agent 层架构伪代码

## 概述

Agent 层负责将自然语言转换为结构化的 COMSOL 建模计划，是整个系统的"大脑"。
本文件展示 Agent 层的设计思路和实现架构。

---

## 1. Planner Agent 架构（自然语言转译层）

### 1.1 核心设计理念

```
自然语言输入 → [理解与解析] → 结构化 JSON → [验证与优化] → 建模计划
```

### 1.2 GeometryAgent 伪代码

```python
class GeometryAgent:
    """
    几何建模 Planner Agent
    
    职责：
    1. 理解用户的自然语言几何建模需求
    2. 提取关键信息（形状类型、参数、位置、关系）
    3. 转换为结构化的 GeometryPlan
    4. 处理上下文和记忆
    """
    
    def __init__(self, llm_client, context_manager=None):
        """
        初始化 Agent
        
        设计要点：
        - LLM 客户端：支持多种后端（Dashscope/OpenAI/Ollama）
        - 上下文管理器：维护对话历史和用户偏好
        - Prompt 加载器：动态加载和格式化 Prompt
        """
        self.llm = llm_client
        self.context = context_manager
        self.prompt_loader = PromptLoader()
        self.validator = PlanValidator()
        
    def parse(self, user_input: str, context: Optional[str] = None) -> GeometryPlan:
        """
        核心解析流程
        
        伪代码流程：
        1. 上下文增强：合并历史对话和用户偏好
        2. Prompt 构建：加载模板并注入上下文
        3. LLM 调用：使用低温度确保一致性
        4. JSON 提取：多种策略提取结构化数据
        5. 验证与修正：确保数据完整性和合理性
        6. 返回计划对象
        """
        
        # 步骤 1: 上下文增强
        enhanced_input = self._enhance_with_context(user_input, context)
        
        # 步骤 2: 构建 Prompt
        prompt = self.prompt_loader.format(
            template="geometry_planner",
            user_input=enhanced_input,
            examples=self._get_examples(),
            schema=self._get_schema_definition()
        )
        
        # 步骤 3: LLM 调用（带重试机制）
        response = self._call_llm_with_retry(
            prompt,
            temperature=0.1,  # 低温度确保一致性
            max_retries=3
        )
        
        # 步骤 4: JSON 提取（多策略）
        json_data = self._extract_json(response)
        
        # 步骤 5: 验证与修正
        plan = self._validate_and_fix(json_data)
        
        return plan
    
    def _enhance_with_context(self, input: str, context: str) -> str:
        """
        上下文增强策略
        
        伪代码：
        - 如果存在上下文，添加历史对话摘要
        - 添加用户偏好（如常用单位、默认参数）
        - 添加领域知识（如常见几何建模模式）
        """
        if not context:
            return input
        
        enhanced = f"""
        上下文信息：
        {context}
        
        用户当前需求：
        {input}
        """
        return enhanced
    
    def _extract_json(self, response: str) -> dict:
        """
        JSON 提取策略（多策略降级）
        
        策略优先级：
        1. 直接 JSON 解析
        2. 提取 ```json 代码块
        3. 提取第一个 { ... } 块
        4. 使用正则表达式提取
        5. 失败则请求 LLM 重新生成
        """
        strategies = [
            self._try_direct_parse,
            self._try_code_block_extract,
            self._try_brace_extract,
            self._try_regex_extract
        ]
        
        for strategy in strategies:
            try:
                result = strategy(response)
                if result:
                    return result
            except Exception:
                continue
        
        # 如果都失败，请求 LLM 重新生成
        return self._request_json_regeneration(response)
    
    def _validate_and_fix(self, json_data: dict) -> GeometryPlan:
        """
        验证与修正策略
        
        伪代码：
        1. 使用 Pydantic 进行基础验证
        2. 检查参数合理性（如尺寸不能为负）
        3. 检查形状关系（如重叠、包含）
        4. 自动修正常见错误（如单位转换）
        5. 如果无法修正，请求用户澄清
        """
        try:
            plan = GeometryPlan.from_dict(json_data)
        except ValidationError as e:
            # 尝试自动修正
            fixed_data = self._auto_fix_common_errors(json_data, e)
            plan = GeometryPlan.from_dict(fixed_data)
        
        # 业务逻辑验证
        self._validate_business_rules(plan)
        
        return plan
```

### 1.3 PhysicsAgent 伪代码（未来扩展）

```python
class PhysicsAgent:
    """
    物理场建模 Planner Agent
    
    职责：
    1. 理解物理场需求（如传热、流体、电磁）
    2. 识别边界条件和初始条件
    3. 识别材料属性
    4. 生成物理场配置计划
    """
    
    def parse(self, user_input: str) -> PhysicsPlan:
        """
        解析物理场需求
        
        伪代码流程：
        1. 识别物理场类型（传热/流体/电磁/结构等）
        2. 提取边界条件（温度/压力/电场等）
        3. 提取材料属性（导热系数/密度/介电常数等）
        4. 识别求解器设置（稳态/瞬态/频域等）
        5. 生成 PhysicsPlan
        """
        
        # 步骤 1: 物理场类型识别
        physics_type = self._identify_physics_type(user_input)
        
        # 步骤 2: 边界条件提取
        boundary_conditions = self._extract_boundary_conditions(
            user_input, 
            physics_type
        )
        
        # 步骤 3: 材料属性提取
        materials = self._extract_materials(user_input)
        
        # 步骤 4: 求解器设置
        solver_settings = self._extract_solver_settings(user_input)
        
        # 步骤 5: 生成计划
        return PhysicsPlan(
            physics_type=physics_type,
            boundary_conditions=boundary_conditions,
            materials=materials,
            solver_settings=solver_settings
        )
```

### 1.4 StudyAgent 伪代码（未来扩展）

```python
class StudyAgent:
    """
    研究类型 Planner Agent
    
    职责：
    1. 识别研究类型（参数化扫描/优化/灵敏度分析等）
    2. 提取参数范围
    3. 识别优化目标
    4. 生成研究计划
    """
    
    def parse(self, user_input: str) -> StudyPlan:
        """
        解析研究需求
        
        伪代码流程：
        1. 识别研究类型
        2. 提取参数和范围
        3. 识别优化目标（如最小化/最大化）
        4. 生成 StudyPlan
        """
        pass
```

### 1.5 多 Agent 协作流程

```python
class AgentOrchestrator:
    """
    Agent 编排器
    
    职责：协调多个 Agent 完成复杂任务
    """
    
    def process_complex_request(self, user_input: str) -> CompletePlan:
        """
        处理复杂请求（包含几何+物理场+研究）
        
        伪代码流程：
        1. 任务分解：识别需要哪些 Agent
        2. 顺序执行：几何 → 物理场 → 研究
        3. 结果合并：生成完整的建模计划
        4. 验证一致性：确保各部分兼容
        """
        
        # 步骤 1: 任务分解
        tasks = self._decompose_task(user_input)
        
        # 步骤 2: 顺序执行
        geometry_plan = None
        physics_plan = None
        study_plan = None
        
        if "geometry" in tasks:
            geometry_plan = self.geometry_agent.parse(user_input)
        
        if "physics" in tasks:
            # 物理场可能需要几何信息
            physics_input = self._enhance_with_geometry(user_input, geometry_plan)
            physics_plan = self.physics_agent.parse(physics_input)
        
        if "study" in tasks:
            study_plan = self.study_agent.parse(user_input)
        
        # 步骤 3: 结果合并
        complete_plan = CompletePlan(
            geometry=geometry_plan,
            physics=physics_plan,
            study=study_plan
        )
        
        # 步骤 4: 验证一致性
        self._validate_consistency(complete_plan)
        
        return complete_plan
```

---

## 2. Executor Agent 架构（执行层）

### 2.1 核心设计理念

```
结构化计划 → [代码生成/API 映射] → Java API 调用 → [执行与验证] → .mph 文件
```

### 2.2 JavaGenerator 伪代码

```python
class JavaGenerator:
    """
    Java 代码生成器
    
    职责：
    1. 将 GeometryPlan 转换为 Java 代码
    2. 处理代码模板和变量替换
    3. 优化代码结构
    """
    
    def generate_from_plan(self, plan: GeometryPlan) -> str:
        """
        生成 Java 代码
        
        伪代码流程：
        1. 加载代码模板
        2. 遍历计划中的形状
        3. 为每个形状生成对应的 Java API 调用
        4. 组装完整的 Java 类
        5. 代码优化（如去除冗余）
        """
        
        # 步骤 1: 生成导入语句
        imports = self._generate_imports()
        
        # 步骤 2: 生成类头
        class_header = self._generate_class_header(plan.model_name)
        
        # 步骤 3: 生成主方法
        main_method = self._generate_main_method(plan)
        
        # 步骤 4: 组装代码
        java_code = f"{imports}\n{class_header}\n{main_method}\n}}"
        
        # 步骤 5: 代码优化
        java_code = self._optimize_code(java_code)
        
        return java_code
    
    def _generate_main_method(self, plan: GeometryPlan) -> str:
        """
        生成主方法代码
        
        伪代码：
        1. 创建模型
        2. 创建几何节点
        3. 遍历形状并生成创建代码
        4. 构建几何
        5. 保存模型
        """
        code_parts = []
        
        # 创建模型
        code_parts.append('Model model = ModelUtil.create("{}");'.format(plan.model_name))
        code_parts.append('model.geom().create("geom1", 2);')
        
        # 遍历形状
        for i, shape in enumerate(plan.shapes, 1):
            shape_code = self._generate_shape_code(shape, i)
            code_parts.append(shape_code)
        
        # 构建几何
        code_parts.append('model.geom("geom1").run();')
        
        # 保存模型
        code_parts.append('model.save("output.mph");')
        
        return "\n".join(code_parts)
    
    def _generate_shape_code(self, shape: GeometryShape, index: int) -> str:
        """
        为单个形状生成 Java 代码
        
        伪代码：
        - 根据形状类型选择对应的生成方法
        - 处理参数映射（JSON → Java API）
        - 处理位置和变换
        """
        shape_generators = {
            "rectangle": self._generate_rectangle_code,
            "circle": self._generate_circle_code,
            "ellipse": self._generate_ellipse_code,
            # 未来扩展：多边形、样条曲线等
        }
        
        generator = shape_generators.get(shape.type)
        if not generator:
            raise ValueError(f"不支持的形状类型: {shape.type}")
        
        return generator(shape, index)
```

### 2.3 COMSOLRunner 伪代码

```python
class COMSOLRunner:
    """
    COMSOL API 运行器
    
    职责：
    1. 管理 JVM 生命周期
    2. 直接调用 COMSOL Java API
    3. 处理 API 调用错误
    4. 管理模型生命周期
    """
    
    def __init__(self):
        """
        初始化运行器
        
        伪代码：
        1. 检查 COMSOL JAR 路径
        2. 启动 JVM（单例模式）
        3. 加载 COMSOL 类
        4. 验证 API 可用性
        """
        self._ensure_jvm_started()
        self.model_registry = {}  # 管理多个模型实例
    
    def create_model_from_plan(self, plan: GeometryPlan) -> Path:
        """
        从计划创建模型
        
        伪代码流程：
        1. 创建 COMSOL 模型对象
        2. 创建几何节点
        3. 遍历形状并创建几何实体
        4. 构建几何
        5. 保存模型
        6. 验证保存结果
        """
        
        try:
            # 步骤 1: 创建模型
            model = self._create_model(plan.model_name)
            
            # 步骤 2: 创建几何节点
            geom = model.geom().create("geom1", 2)
            
            # 步骤 3: 创建形状
            for shape in plan.shapes:
                self._create_shape(model, shape)
            
            # 步骤 4: 构建几何
            geom.run()
            
            # 步骤 5: 保存模型
            output_path = self._save_model(model, plan.model_name)
            
            # 步骤 6: 验证
            self._validate_model(output_path)
            
            return output_path
            
        except Exception as e:
            self._handle_error(e, plan)
            raise
    
    def _create_shape(self, model, shape: GeometryShape):
        """
        创建单个形状
        
        伪代码：
        - 根据形状类型调用对应的创建方法
        - 处理参数映射
        - 处理错误和回滚
        """
        shape_creators = {
            "rectangle": self._create_rectangle,
            "circle": self._create_circle,
            "ellipse": self._create_ellipse,
        }
        
        creator = shape_creators.get(shape.type)
        if not creator:
            raise ValueError(f"不支持的形状类型: {shape.type}")
        
        creator(model, shape)
    
    def _create_rectangle(self, model, shape: GeometryShape):
        """
        创建矩形
        
        伪代码：
        1. 提取参数（宽、高、位置）
        2. 调用 COMSOL API
        3. 设置属性
        4. 验证创建结果
        """
        name = shape.name or "rect1"
        width = shape.parameters["width"]
        height = shape.parameters["height"]
        x = shape.position.get("x", 0.0)
        y = shape.position.get("y", 0.0)
        
        # COMSOL API 调用
        rect = model.geom().create(name, "Rectangle")
        rect.set("size", [width, height])
        rect.set("pos", [x, y])
        
        # 验证
        if not self._validate_shape_creation(rect):
            raise RuntimeError(f"矩形 {name} 创建失败")
```

---

## 3. 上下文管理与记忆机制

### 3.1 ContextManager 伪代码

```python
class ContextManager:
    """
    上下文管理器
    
    职责：
    1. 存储对话历史
    2. 生成上下文摘要
    3. 维护用户偏好
    4. 提供上下文查询接口
    """
    
    def get_context_for_planner(self) -> str:
        """
        为 Planner Agent 生成上下文
        
        伪代码：
        1. 加载最近的对话历史（如最近 10 条）
        2. 提取关键信息（常用参数、偏好设置）
        3. 生成摘要
        4. 返回格式化的上下文字符串
        """
        
        # 加载历史
        recent_conversations = self._load_recent_conversations(limit=10)
        
        # 提取关键信息
        user_preferences = self._extract_preferences(recent_conversations)
        common_patterns = self._extract_patterns(recent_conversations)
        
        # 生成摘要
        summary = self._generate_summary(
            preferences=user_preferences,
            patterns=common_patterns,
            recent_history=recent_conversations
        )
        
        return summary
    
    def add_conversation(self, user_input: str, plan: dict, success: bool):
        """
        添加对话记录
        
        伪代码：
        1. 创建对话记录对象
        2. 存储到数据库或文件
        3. 更新用户偏好统计
        4. 触发摘要更新（如果达到阈值）
        """
        conversation = ConversationRecord(
            user_input=user_input,
            plan=plan,
            success=success,
            timestamp=datetime.now()
        )
        
        self._save_conversation(conversation)
        self._update_preferences(conversation)
        
        # 如果达到阈值，更新摘要
        if self._should_update_summary():
            self._regenerate_summary()
```

---

## 4. 错误处理与重试机制

### 4.1 错误处理策略

```python
class ErrorHandler:
    """
    错误处理器
    
    职责：
    1. 分类错误类型
    2. 提供恢复策略
    3. 记录错误日志
    """
    
    def handle_llm_error(self, error: Exception, retry_count: int):
        """
        处理 LLM 调用错误
        
        伪代码：
        - 网络错误：重试
        - API 错误：检查配置
        - 超时错误：增加超时时间
        - 配额错误：提示用户
        """
        if isinstance(error, NetworkError):
            if retry_count < 3:
                return RetryStrategy.RETRY
            else:
                return RetryStrategy.FAIL
        
        if isinstance(error, APIQuotaError):
            return RetryStrategy.FAIL_WITH_MESSAGE
    
    def handle_validation_error(self, error: ValidationError, plan_data: dict):
        """
        处理验证错误
        
        伪代码：
        1. 分析错误原因
        2. 尝试自动修正
        3. 如果无法修正，请求用户澄清
        """
        if self._can_auto_fix(error, plan_data):
            fixed_data = self._auto_fix(error, plan_data)
            return fixed_data
        else:
            raise UserClarificationNeeded(error)
```

---

## 5. 扩展性设计

### 5.1 插件化 Agent 架构

```python
class AgentRegistry:
    """
    Agent 注册表
    
    支持动态注册新的 Agent 类型
    """
    
    def register_agent(self, agent_type: str, agent_class: type):
        """
        注册新的 Agent
        
        伪代码：
        - 验证 Agent 接口
        - 注册到注册表
        - 更新路由表
        """
        if not self._validate_agent_interface(agent_class):
            raise ValueError("Agent 必须实现 parse() 方法")
        
        self.agents[agent_type] = agent_class
        self._update_routing_table()
```

---

## 6. 性能优化策略

### 6.1 缓存机制

```python
class PlanCache:
    """
    计划缓存
    
    缓存常见的建模计划，避免重复 LLM 调用
    """
    
    def get_cached_plan(self, user_input: str) -> Optional[GeometryPlan]:
        """
        获取缓存的计划
        
        伪代码：
        1. 计算输入哈希
        2. 查询缓存
        3. 如果命中，返回缓存结果
        4. 如果未命中，返回 None
        """
        input_hash = self._hash_input(user_input)
        return self.cache.get(input_hash)
```

---

## 总结

Agent 层的核心设计原则：

1. **分层清晰**：Planner（理解） → Executor（执行）
2. **可扩展**：支持新的 Agent 类型和形状类型
3. **容错性强**：多策略降级、自动修正、重试机制
4. **上下文感知**：利用历史对话提升理解准确性
5. **性能优化**：缓存、批量处理、异步执行
