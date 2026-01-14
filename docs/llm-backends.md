# LLM 后端配置指南

## 支持的后端类型

COMSOL Agent 支持以下 LLM 后端：

1. **dashscope** - Dashscope (Qwen) 官方 API
2. **openai** - OpenAI 官方 API
3. **openai-compatible** - 符合 OpenAI API 规范的第三方服务
4. **ollama** - Ollama 服务（本地或远程）

## 配置方式

### 1. Dashscope (Qwen) 后端

**环境变量配置：**
```bash
LLM_BACKEND=dashscope
DASHSCOPE_API_KEY=your_dashscope_api_key
```

**.env 文件配置：**
```env
LLM_BACKEND=dashscope
DASHSCOPE_API_KEY=your_dashscope_api_key
```

**命令行使用：**
```bash
comsol-agent run --backend dashscope --api-key your_key "创建一个矩形"
```

### 2. OpenAI 官方 API

**环境变量配置：**
```bash
LLM_BACKEND=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-3.5-turbo  # 可选，默认 gpt-3.5-turbo
```

**.env 文件配置：**
```env
LLM_BACKEND=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-3.5-turbo
# OPENAI_BASE_URL=https://api.openai.com/v1  # 可选，默认官方 API
```

**命令行使用：**
```bash
comsol-agent run --backend openai --api-key your_key "创建一个矩形"
comsol-agent run --backend openai --api-key your_key --model gpt-4 "创建一个矩形"
```

### 3. OpenAI 兼容 API（第三方服务）

支持任何符合 OpenAI API 规范的第三方服务，例如：
- LocalAI
- vLLM
- Together AI
- Anyscale
- 其他兼容服务

**环境变量配置：**
```bash
LLM_BACKEND=openai-compatible
OPENAI_COMPATIBLE_API_KEY=your_api_key
OPENAI_COMPATIBLE_BASE_URL=https://api.example.com/v1
OPENAI_COMPATIBLE_MODEL=your-model-name
```

**.env 文件配置：**
```env
LLM_BACKEND=openai-compatible
OPENAI_COMPATIBLE_API_KEY=your_api_key
OPENAI_COMPATIBLE_BASE_URL=https://api.example.com/v1
OPENAI_COMPATIBLE_MODEL=your-model-name
```

**命令行使用：**
```bash
comsol-agent run --backend openai-compatible \
  --api-key your_key \
  --base-url https://api.example.com/v1 \
  --model your-model-name \
  "创建一个矩形"
```

**示例：使用 LocalAI**
```env
LLM_BACKEND=openai-compatible
OPENAI_COMPATIBLE_API_KEY=not-needed
OPENAI_COMPATIBLE_BASE_URL=http://localhost:8080/v1
OPENAI_COMPATIBLE_MODEL=llama3
```

**示例：使用 Together AI**
```env
LLM_BACKEND=openai-compatible
OPENAI_COMPATIBLE_API_KEY=your_together_api_key
OPENAI_COMPATIBLE_BASE_URL=https://api.together.xyz/v1
OPENAI_COMPATIBLE_MODEL=togethercomputer/llama-2-70b-chat
```

### 4. Ollama 服务

**环境变量配置：**
```bash
LLM_BACKEND=ollama
OLLAMA_URL=http://localhost:11434  # 本地或远程地址
OLLAMA_MODEL=llama3
```

**.env 文件配置：**
```env
LLM_BACKEND=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

**命令行使用：**
```bash
# 本地 Ollama
comsol-agent run --backend ollama "创建一个矩形"

# 远程 Ollama
comsol-agent run --backend ollama --ollama-url http://192.168.1.100:11434 "创建一个矩形"
```

详细 Ollama 配置请参考 [ollama-setup.md](ollama-setup.md)

## 后端选择建议

### 开发环境
- **Ollama（本地）**：免费，无需 API Key，适合快速测试
- **Dashscope (Qwen)**：中文支持好，价格相对便宜

### 生产环境
- **OpenAI**：性能稳定，模型质量高
- **Dashscope (Qwen)**：中文场景推荐
- **OpenAI 兼容服务**：根据需求选择第三方服务

### 私有部署
- **Ollama（本地/远程）**：完全私有，数据安全
- **OpenAI 兼容服务（私有部署）**：如 LocalAI、vLLM 等

## 模型推荐

### Dashscope (Qwen)
- `qwen-turbo` - 快速响应
- `qwen-plus` - 平衡性能
- `qwen-max` - 最佳质量

### OpenAI
- `gpt-3.5-turbo` - 性价比高
- `gpt-4` - 最佳质量
- `gpt-4-turbo` - 平衡性能和质量

### Ollama
- `llama3` - 通用推荐
- `llama3.2` - 更新版本
- `qwen2.5` - 中文支持好
- `mistral` - 轻量快速

### OpenAI 兼容服务
根据服务提供商推荐的模型

## 故障排除

### 问题 1: API Key 错误

**解决方案**：
- 检查 API Key 是否正确
- 确认 API Key 是否有足够的权限和额度
- 对于第三方服务，确认 API Key 格式是否正确

### 问题 2: 无法连接到服务

**解决方案**：
- 检查网络连接
- 确认服务地址（base_url）是否正确
- 检查防火墙设置
- 对于第三方服务，确认 API 端点路径（通常需要 `/v1` 后缀）

### 问题 3: 模型不存在

**解决方案**：
- 检查模型名称是否正确
- 确认该模型在服务中可用
- 对于 Ollama，使用 `ollama list` 查看可用模型

### 问题 4: 响应格式不符合预期

**解决方案**：
- 某些模型可能需要调整 Prompt
- 尝试不同的模型
- 检查模型的输出格式是否符合 JSON 要求

## 性能对比

| 后端 | 响应速度 | 成本 | 中文支持 | 私有部署 |
|------|---------|------|---------|---------|
| Dashscope | 快 | 低 | 优秀 | 否 |
| OpenAI | 中等 | 中高 | 良好 | 否 |
| OpenAI 兼容 | 取决于服务 | 取决于服务 | 取决于模型 | 是 |
| Ollama | 取决于硬件 | 免费 | 取决于模型 | 是 |

## 最佳实践

1. **开发阶段**：使用 Ollama 本地服务，快速迭代
2. **测试阶段**：使用 Dashscope 或 OpenAI，验证功能
3. **生产环境**：根据需求选择合适后端，考虑成本、性能和隐私
4. **私有部署**：使用 Ollama 或私有 OpenAI 兼容服务
