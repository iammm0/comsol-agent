# Planner Agent 实现伪代码

## 概述

本文档展示 Planner Agent 的具体实现细节，包括自然语言理解、JSON 提取、验证修正等核心流程。

---

## 1. 自然语言理解流程

### 1.1 输入预处理

```python
def preprocess_user_input(user_input: str) -> str:
    """
    预处理用户输入
    
    伪代码：
    1. 清理空白字符
    2. 标准化单位（如 "cm" → "m"）
    3. 识别并替换同义词
    4. 提取数值和单位
    """
    # 清理空白
    cleaned = user_input.strip()
    
    # 单位标准化
    cleaned = standardize_units(cleaned)
    
    # 同义词替换
    cleaned = replace_synonyms(cleaned, {
        "矩形": "rectangle",
        "圆形": "circle",
        "椭圆": "ellipse",
        "宽": "width",
        "高": "height",
        "半径": "radius"
    })
    
    return cleaned
```

### 1.2 Prompt 构建策略

```python
def build_geometry_prompt(user_input: str, context: str = None) -> str:
    """
    构建几何建模 Prompt
    
    伪代码：
    1. 加载基础模板
    2. 注入上下文信息
    3. 添加示例
    4. 添加 Schema 定义
    5. 格式化最终 Prompt
    """
    template = """
    你是一个专业的 COMSOL 几何建模助手。
    
    ## 任务
    将用户的自然语言描述转换为结构化的 JSON 格式。
    
    ## 上下文信息
    {context}
    
    ## 用户需求
    {user_input}
    
    ## 输出格式
    请严格按照以下 JSON Schema 输出：
    {schema}
    
    ## 示例
    {examples}
    
    ## 注意事项
    1. 所有数值必须为正数
    2. 位置坐标默认为 (0, 0)
    3. 单位统一使用米 (m)
    4. 形状名称自动生成（如果未指定）
    """
    
    return template.format(
        context=context or "无上下文信息",
        user_input=user_input,
        schema=get_geometry_schema_definition(),
        examples=get_examples()
    )
```

### 1.3 LLM 调用与重试

```python
def call_llm_with_retry(prompt: str, max_retries: int = 3) -> str:
    """
    LLM 调用（带重试机制）
    
    伪代码：
    1. 尝试调用 LLM
    2. 如果失败，分析错误类型
    3. 根据错误类型决定是否重试
    4. 重试时调整策略（如降低温度、简化 Prompt）
    """
    for attempt in range(max_retries):
        try:
            response = llm.call(
                prompt,
                temperature=0.1,  # 低温度确保一致性
                max_tokens=2000
            )
            return response
            
        except NetworkError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避
                time.sleep(wait_time)
                continue
            raise
            
        except APIError as e:
            if "quota" in str(e).lower():
                raise QuotaExceededError("API 配额已用完")
            if attempt < max_retries - 1:
                # 简化 Prompt 重试
                prompt = simplify_prompt(prompt)
                continue
            raise
            
        except TimeoutError:
            if attempt < max_retries - 1:
                # 增加超时时间
                continue
            raise
    
    raise MaxRetriesExceededError("达到最大重试次数")
```

---

## 2. JSON 提取策略

### 2.1 多策略提取

```python
def extract_json_from_response(response: str) -> dict:
    """
    从 LLM 响应中提取 JSON
    
    策略优先级：
    1. 直接 JSON 解析
    2. 提取 ```json 代码块
    3. 提取第一个 { ... } 块
    4. 使用正则表达式提取
    5. 请求 LLM 重新生成
    """
    strategies = [
        try_direct_json_parse,
        try_extract_json_code_block,
        try_extract_json_brace_block,
        try_regex_extract_json,
        request_json_regeneration
    ]
    
    for strategy in strategies:
        try:
            result = strategy(response)
            if result and validate_json_structure(result):
                return result
        except Exception as e:
            logger.debug(f"策略 {strategy.__name__} 失败: {e}")
            continue
    
    raise JSONExtractionError("无法从响应中提取有效的 JSON")
```

### 2.2 具体提取方法

```python
def try_direct_json_parse(response: str) -> Optional[dict]:
    """尝试直接解析 JSON"""
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return None

def try_extract_json_code_block(response: str) -> Optional[dict]:
    """提取 ```json 代码块"""
    pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    match = re.search(pattern, response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None

def try_extract_json_brace_block(response: str) -> Optional[dict]:
    """提取第一个 { ... } 块"""
    # 找到第一个 {
    start_idx = response.find('{')
    if start_idx == -1:
        return None
    
    # 找到匹配的 }
    brace_count = 0
    for i in range(start_idx, len(response)):
        if response[i] == '{':
            brace_count += 1
        elif response[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                json_str = response[start_idx:i+1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
                break
    return None

def request_json_regeneration(response: str) -> dict:
    """请求 LLM 重新生成 JSON"""
    regeneration_prompt = f"""
    请将以下内容转换为标准的 JSON 格式：
    
    {response}
    
    只输出 JSON，不要包含任何其他文字。
    """
    
    new_response = llm.call(regeneration_prompt, temperature=0.0)
    return json.loads(new_response)
```

---

## 3. 验证与修正

### 3.1 数据验证

```python
def validate_geometry_plan(json_data: dict) -> Tuple[bool, List[str]]:
    """
    验证几何计划
    
    返回：(是否有效, 错误列表)
    """
    errors = []
    
    # 1. Schema 验证（使用 Pydantic）
    try:
        plan = GeometryPlan.from_dict(json_data)
    except ValidationError as e:
        errors.extend([f"Schema 验证失败: {err}" for err in e.errors()])
        return False, errors
    
    # 2. 业务逻辑验证
    if not plan.shapes:
        errors.append("至少需要一个几何形状")
    
    for i, shape in enumerate(plan.shapes):
        shape_errors = validate_shape(shape, i)
        errors.extend(shape_errors)
    
    # 3. 关系验证（如重叠检查）
    overlap_errors = check_shape_overlaps(plan.shapes)
    errors.extend(overlap_errors)
    
    return len(errors) == 0, errors

def validate_shape(shape: GeometryShape, index: int) -> List[str]:
    """验证单个形状"""
    errors = []
    
    # 参数验证
    if shape.type == "rectangle":
        if shape.parameters.get("width", 0) <= 0:
            errors.append(f"形状 {index}: 宽度必须大于 0")
        if shape.parameters.get("height", 0) <= 0:
            errors.append(f"形状 {index}: 高度必须大于 0")
    
    elif shape.type == "circle":
        if shape.parameters.get("radius", 0) <= 0:
            errors.append(f"形状 {index}: 半径必须大于 0")
    
    # 位置验证
    x = shape.position.get("x", 0)
    y = shape.position.get("y", 0)
    if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
        errors.append(f"形状 {index}: 位置坐标无效")
    
    return errors
```

### 3.2 自动修正

```python
def auto_fix_common_errors(json_data: dict, validation_errors: List[str]) -> dict:
    """
    自动修正常见错误
    
    伪代码：
    1. 分析错误类型
    2. 应用修正规则
    3. 返回修正后的数据
    """
    fixed_data = json_data.copy()
    
    for error in validation_errors:
        # 修正缺失的字段
        if "missing" in error.lower():
            fixed_data = fix_missing_fields(fixed_data, error)
        
        # 修正类型错误
        if "type" in error.lower():
            fixed_data = fix_type_errors(fixed_data, error)
        
        # 修正数值错误
        if "must be greater" in error.lower():
            fixed_data = fix_negative_values(fixed_data, error)
        
        # 修正单位错误
        if "unit" in error.lower():
            fixed_data = fix_unit_errors(fixed_data, error)
    
    return fixed_data

def fix_missing_fields(data: dict, error: str) -> dict:
    """修正缺失的字段"""
    # 如果缺少 model_name，使用默认值
    if "model_name" not in data:
        data["model_name"] = "geometry_model"
    
    # 如果缺少 units，使用默认值
    if "units" not in data:
        data["units"] = "m"
    
    # 为每个形状添加默认位置
    for shape in data.get("shapes", []):
        if "position" not in shape:
            shape["position"] = {"x": 0.0, "y": 0.0}
    
    return data

def fix_negative_values(data: dict, error: str) -> dict:
    """修正负数值"""
    for shape in data.get("shapes", []):
        for key, value in shape.get("parameters", {}).items():
            if isinstance(value, (int, float)) and value < 0:
                # 取绝对值
                shape["parameters"][key] = abs(value)
                logger.warning(f"自动修正负数值: {key} = {value} → {abs(value)}")
    
    return data
```

---

## 4. 上下文管理

### 4.1 上下文生成

```python
def generate_context_summary(conversations: List[ConversationRecord]) -> str:
    """
    生成上下文摘要
    
    伪代码：
    1. 分析最近的对话
    2. 提取用户偏好
    3. 提取常用模式
    4. 生成摘要文本
    """
    if not conversations:
        return "无历史对话记录"
    
    # 提取用户偏好
    preferences = extract_user_preferences(conversations)
    
    # 提取常用模式
    patterns = extract_common_patterns(conversations)
    
    # 生成摘要
    summary = f"""
    用户偏好：
    - 常用单位: {preferences.get('units', 'm')}
    - 常用尺寸范围: {preferences.get('size_range', '未知')}
    - 常用形状类型: {', '.join(preferences.get('shape_types', []))}
    
    常用模式：
    {format_patterns(patterns)}
    
    最近对话摘要：
    {format_recent_conversations(conversations[-5:])}
    """
    
    return summary

def extract_user_preferences(conversations: List[ConversationRecord]) -> dict:
    """提取用户偏好"""
    preferences = {
        "units": [],
        "size_range": [],
        "shape_types": []
    }
    
    for conv in conversations:
        if conv.plan:
            # 提取单位
            units = conv.plan.get("units", "m")
            preferences["units"].append(units)
            
            # 提取形状类型
            for shape in conv.plan.get("shapes", []):
                shape_type = shape.get("type")
                if shape_type:
                    preferences["shape_types"].append(shape_type)
    
    # 统计最常用的
    return {
        "units": most_common(preferences["units"]) or "m",
        "shape_types": list(set(preferences["shape_types"]))
    }
```

---

## 5. 完整解析流程

```python
class GeometryAgent:
    """完整的几何 Agent 实现"""
    
    def parse(self, user_input: str, context: Optional[str] = None) -> GeometryPlan:
        """
        完整的解析流程
        
        伪代码：
        1. 预处理输入
        2. 构建 Prompt
        3. 调用 LLM
        4. 提取 JSON
        5. 验证数据
        6. 自动修正（如果需要）
        7. 返回计划对象
        """
        logger.info(f"开始解析用户输入: {user_input[:50]}...")
        
        # 步骤 1: 预处理
        processed_input = preprocess_user_input(user_input)
        
        # 步骤 2: 构建 Prompt
        prompt = build_geometry_prompt(processed_input, context)
        
        # 步骤 3: 调用 LLM
        response = call_llm_with_retry(prompt, max_retries=3)
        
        # 步骤 4: 提取 JSON
        json_data = extract_json_from_response(response)
        
        # 步骤 5: 验证
        is_valid, errors = validate_geometry_plan(json_data)
        
        if not is_valid:
            # 步骤 6: 尝试自动修正
            logger.warning(f"验证失败，尝试自动修正: {errors}")
            json_data = auto_fix_common_errors(json_data, errors)
            
            # 重新验证
            is_valid, errors = validate_geometry_plan(json_data)
            
            if not is_valid:
                raise ValidationError(f"无法修正验证错误: {errors}")
        
        # 步骤 7: 创建计划对象
        plan = GeometryPlan.from_dict(json_data)
        
        logger.info(f"解析成功: {len(plan.shapes)} 个形状")
        return plan
```

---

## 总结

Planner Agent 的实现要点：

1. **多策略降级**：JSON 提取使用多种策略，确保成功率
2. **自动修正**：常见错误自动修正，减少用户干预
3. **上下文感知**：利用历史对话提升理解准确性
4. **容错性强**：重试机制、错误处理、验证修正
5. **可扩展**：支持新的形状类型和验证规则
