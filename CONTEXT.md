# 上下文管理使用指南

## 概述

COMSOL Agent 提供了上下文管理功能，可以：
- 记录每次对话的历史
- 自动生成上下文摘要
- 在后续对话中使用历史上下文信息
- 支持用户自定义命令别名

## 上下文功能

### 自动上下文记忆

每次运行 `run` 命令时，系统会自动：
1. 加载之前的对话历史
2. 提取用户偏好（常用单位、形状类型等）
3. 将上下文信息传递给 Planner Agent
4. 保存当前对话记录
5. 更新上下文摘要

### 查看上下文

```bash
# 查看上下文摘要（默认）
comsol-agent context

# 查看详细统计信息
comsol-agent context --stats

# 查看对话历史
comsol-agent context --history

# 查看最近 N 条历史
comsol-agent context --history --limit 20
```

### 清除上下文

```bash
# 清除所有对话历史
comsol-agent context --clear
```

### 禁用上下文

如果不想使用上下文记忆：

```bash
comsol-agent run --no-context "创建一个矩形"
```

## 上下文存储位置

上下文数据存储在安装目录下的 `.context` 文件夹：
- `history.json` - 对话历史记录
- `summary.json` - 上下文摘要

## 自定义命令别名

### Linux/Mac

在 `~/.bashrc` 或 `~/.zshrc` 中添加：

```bash
# 自定义别名
alias ca="comsol-agent"
alias comsol="comsol-agent"
alias cagent="comsol-agent"

# 常用命令的快捷方式
alias carun="comsol-agent run"
alias cap="comsol-agent plan"
alias cactx="comsol-agent context"
```

然后重新加载配置：
```bash
source ~/.bashrc  # 或 source ~/.zshrc
```

### Windows

在 PowerShell 配置文件中添加（`$PROFILE`）：

```powershell
# 自定义别名
Set-Alias ca comsol-agent
Set-Alias comsol comsol-agent
Set-Alias cagent comsol-agent

# 常用命令的快捷方式
function carun { comsol-agent run $args }
function cap { comsol-agent plan $args }
function cactx { comsol-agent context $args }
```

### 使用示例

配置别名后，可以使用：

```bash
# 使用自定义别名
ca run "创建一个矩形"
comsol plan "创建一个圆"
cagent context --stats

# 使用快捷命令
carun "创建一个矩形"
cap "创建一个圆" -o plan.json
cactx --history
```

## 上下文摘要内容

上下文摘要包含：
- 对话统计（总数、成功/失败次数）
- 最近使用的形状类型
- 用户偏好（常用单位等）
- 最近活动摘要

这些信息会在 Planner Agent 解析时自动使用，帮助更好地理解用户意图。

## 最佳实践

1. **定期查看上下文**：使用 `comsol-agent context --stats` 了解使用情况
2. **保持上下文清洁**：如果上下文过多，可以定期清除
3. **利用上下文**：让系统学习你的使用习惯，提高解析准确性
4. **自定义别名**：设置符合自己习惯的命令别名，提高效率
