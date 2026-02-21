# LLM 后端配置指南

## 支持的后端类型

当前**仅支持**以下四种 LLM 后端：

1. **deepseek** - DeepSeek API
2. **kimi** - Kimi（Moonshot）API
3. **ollama** - Ollama 服务（本地或远程）
4. **openai-compatible** - 符合 OpenAI API 规范的中转 API

## 配置方式

### 1. DeepSeek

**环境变量 / .env：**
```env
LLM_BACKEND=deepseek
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_MODEL=deepseek-chat
```

**命令行：**
```bash
comsol-agent run --backend deepseek --api-key your_key "创建一个矩形"
```

### 2. Kimi（Moonshot）

**环境变量 / .env：**
```env
LLM_BACKEND=kimi
KIMI_API_KEY=your_api_key
KIMI_MODEL=moonshot-v1-8k
```

**命令行：**
```bash
comsol-agent run --backend kimi --api-key your_key "创建一个矩形"
```

### 3. 符合 OpenAI 规范的中转 API

支持任意符合 OpenAI Chat Completions 规范的中转服务（需提供 base_url 与 api_key）。

**环境变量 / .env：**
```env
LLM_BACKEND=openai-compatible
OPENAI_COMPATIBLE_API_KEY=your_api_key
OPENAI_COMPATIBLE_BASE_URL=https://api.example.com/v1
OPENAI_COMPATIBLE_MODEL=your-model-name
```

**命令行：**
```bash
comsol-agent run --backend openai-compatible --api-key your_key --base-url https://api.example.com/v1 "创建一个矩形"
```

### 4. Ollama

**环境变量 / .env：**
```env
LLM_BACKEND=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

**命令行：**
```bash
comsol-agent run --backend ollama "创建一个矩形"
comsol-agent run --backend ollama --ollama-url http://192.168.1.100:11434 "创建一个矩形"
```

详细 Ollama 配置请参考 [ollama-setup.md](ollama-setup.md)。

## 后端选择建议

- **本地开发/测试**：Ollama，无需 API Key
- **中文与推理**：DeepSeek 或 Kimi
- **自建或第三方中转**：openai-compatible，填写对应 base_url 与 api_key

## 依赖说明

- deepseek、kimi、openai-compatible 均通过 `openai` Python 包调用（`pip install openai`）
- ollama 使用 HTTP 请求，需 `requests` 可用
