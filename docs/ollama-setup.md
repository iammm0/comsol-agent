# Ollama 配置指南

## 概述

COMSOL Agent 支持使用 Ollama 作为 LLM 后端，可以配置本地或远程的 Ollama 服务。

## 安装 Ollama

### Linux/Mac

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows

从 [Ollama 官网](https://ollama.com/download) 下载安装程序。

## 启动 Ollama 服务

### 本地服务（默认）

```bash
# 启动 Ollama 服务（默认端口 11434）
ollama serve
```

### 远程服务

在远程服务器上启动 Ollama：

```bash
# 设置监听地址（允许远程访问）
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

## 下载模型

```bash
# 下载推荐的模型（llama3）
ollama pull llama3

# 或其他模型
ollama pull llama3.2
ollama pull qwen2.5
ollama pull mistral
```

## 配置 COMSOL Agent

### 方式一：环境变量

```bash
# Linux/Mac
export LLM_BACKEND=ollama
export OLLAMA_URL=http://localhost:11434
export OLLAMA_MODEL=llama3

# Windows
set LLM_BACKEND=ollama
set OLLAMA_URL=http://localhost:11434
set OLLAMA_MODEL=llama3
```

### 方式二：.env 文件

在项目根目录或用户主目录创建 `.env` 文件：

```env
# 使用 Ollama 后端
LLM_BACKEND=ollama

# 本地 Ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# 远程 Ollama
# OLLAMA_URL=http://192.168.1.100:11434
# OLLAMA_MODEL=llama3
```

### 方式三：命令行参数

```bash
# 使用 Ollama 后端
comsol-agent run --backend ollama "创建一个矩形"

# 指定远程 Ollama 服务
comsol-agent run --backend ollama --ollama-url http://192.168.1.100:11434 "创建一个矩形"

# 指定模型
comsol-agent run --backend ollama --model llama3.2 "创建一个矩形"
```

## 验证配置

运行诊断命令检查 Ollama 配置：

```bash
comsol-agent doctor
```

如果配置正确，会显示：
- Ollama 服务可访问
- 可用模型列表

## 推荐模型

- **llama3** - 通用推荐，平衡性能和准确性
- **llama3.2** - 更新的版本，更好的性能
- **qwen2.5** - 中文支持更好
- **mistral** - 轻量级，速度快

## 性能优化

### 本地部署

1. **使用 GPU**：Ollama 会自动使用 GPU（如果可用）
2. **模型选择**：较小的模型（如 mistral）速度更快
3. **并发控制**：避免同时运行多个请求

### 远程部署

1. **网络延迟**：确保网络连接稳定
2. **超时设置**：远程服务可能需要更长的超时时间
3. **安全考虑**：使用 HTTPS 或 VPN 保护远程连接

## 故障排除

### 问题 1: 无法连接到 Ollama 服务

**解决方案**：
- 检查 Ollama 服务是否运行：`ollama list`
- 检查服务地址是否正确
- 检查防火墙设置

### 问题 2: 模型未找到

**解决方案**：
- 检查模型是否已下载：`ollama list`
- 下载模型：`ollama pull <model_name>`
- 检查模型名称是否正确

### 问题 3: 响应速度慢

**解决方案**：
- 使用较小的模型
- 确保使用 GPU（如果可用）
- 检查网络连接（远程服务）

## 切换后端

### 从 Dashscope 切换到 Ollama

```bash
# 在 .env 文件中设置
LLM_BACKEND=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

### 从 Ollama 切换回 Dashscope

```bash
# 在 .env 文件中设置
LLM_BACKEND=deepseek
DEEPSEEK_API_KEY=your_api_key
```

## 示例配置

### 本地开发

```env
LLM_BACKEND=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

### 远程服务器

```env
LLM_BACKEND=ollama
OLLAMA_URL=http://192.168.1.100:11434
OLLAMA_MODEL=llama3.2
```

### 生产环境（Dashscope）

```env
LLM_BACKEND=deepseek
DEEPSEEK_API_KEY=your_api_key
```
