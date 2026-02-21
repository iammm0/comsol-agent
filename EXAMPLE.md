# COMSOL Agent 示例命令

本文档提供可直接复制的命令，用于测试 comsol-agent 各模块的建模能力。运行前请确保已配置 `.env`（如 `COMSOL_JAR_PATH`、LLM 后端等），并执行 `uv run comsol-agent doctor` 通过环境检查。

- **从源码运行**：使用 `uv run comsol-agent` 或 `uv run python main.py`
- **已安装分发包**：可直接使用 `comsol-agent` 或 `python main.py`

---

## 1. 环境与诊断

```bash
# 环境诊断（COMSOL、Java、LLM 等）
uv run comsol-agent doctor

# 查看解析能力演示（仅解析，不生成模型）
uv run comsol-agent demo
```

---

## 2. 几何建模（单形状）

以下命令会生成 `.mph` 模型并保存到项目 `models/` 目录（或 `-o` 指定文件名）。

### 2.1 矩形

```bash
uv run comsol-agent run "创建一个宽1米、高0.5米的矩形" -o rect.mph
```

```bash
uv run comsol-agent run "创建一个宽2米、高1米的矩形，放在原点" -o rect_2x1.mph
```

### 2.2 圆形

```bash
uv run comsol-agent run "在原点放置一个半径为0.3米的圆" -o circle.mph
```

```bash
uv run comsol-agent run "创建一个半径为0.5米的圆，中心在(0, 0)" -o circle_r05.mph
```

### 2.3 椭圆

```bash
uv run comsol-agent run "创建一个长轴1米、短轴0.6米的椭圆，中心在(0.5, 0.5)" -o ellipse.mph
```

```bash
uv run comsol-agent run "在(0.2, 0.2)处画一个长轴0.8米、短轴0.4米的椭圆" -o ellipse_2.mph
```

---

## 3. 几何建模（多形状与组合描述）

```bash
uv run comsol-agent run "创建一个矩形宽1高0.5，再在(0.5, 0.25)处加一个半径0.1的圆" -o rect_circle.mph
```

```bash
uv run comsol-agent run "创建两个矩形：一个1x0.5在原点，一个0.5x0.3在(1, 0)" -o two_rects.mph
```

---

## 4. 仅规划不执行（plan）

只做自然语言 → 结构化 JSON，不调用 COMSOL，用于检查解析结果。

```bash
uv run comsol-agent plan "创建一个宽1米、高0.5米的矩形"
```

```bash
uv run comsol-agent plan "在原点放一个半径0.3米的圆" -o plan_circle.json
```

```bash
uv run comsol-agent plan "创建一个长轴1米短轴0.6米的椭圆，中心在(0.5, 0.5)" -o plan_ellipse.json
```

---

## 5. 从 JSON 计划执行（exec）

先得到 JSON 计划（如用 `plan` 子命令带 `-o plan.json`），再根据 JSON 创建模型。

```bash
# 先生成计划文件
uv run comsol-agent plan "创建一个宽1米、高0.5米的矩形" -o my_plan.json

# 再根据计划创建模型
uv run comsol-agent exec my_plan.json -o from_plan.mph
```

仅生成 Java 代码、不调用 COMSOL：

```bash
uv run comsol-agent exec my_plan.json --code-only
```

---

## 6. ReAct 架构（完整流程）

ReAct 会按需规划几何 → 物理场 → 网格 → 研究 → 求解，适合“一句话建完整模型”的测试。

```bash
uv run comsol-agent run "创建一个传热模型，包含一个矩形域，设置温度边界条件，进行稳态求解" -o heat_steady.mph
```

```bash
uv run comsol-agent run "创建几何：宽1米高0.5米的矩形；并配置物理场与求解" -o full_flow.mph
```

```bash
# 增加迭代次数以便复杂需求有更多改进机会
uv run comsol-agent run "创建带矩形域的传热模型并求解" --max-iterations 15 -o heat_solve.mph
```

---

## 7. 传统架构（仅几何）

不使用 ReAct，仅做“自然语言 → 几何计划 → COMSOL 几何”，适合快速验证几何解析与 API。

```bash
uv run comsol-agent run "创建一个宽1米、高0.5米的矩形" --no-react -o rect_no_react.mph
```

```bash
uv run comsol-agent run "在原点放置一个半径为0.3米的圆" --no-react -o circle_no_react.mph
```

---

## 8. 使用 main.py 的等价命令

与 `comsol-agent run` 对应，便于在 IDE 或脚本中调试。

```bash
# ReAct（默认）
uv run python main.py --react "创建一个宽1米、高0.5米的矩形" -o test_rect.mph

# 仅几何
uv run python main.py --no-react "创建一个矩形" -o test_rect2.mph

# 指定输出
uv run python main.py "创建矩形几何" -o my_model.mph
```

---

## 9. 交互模式与演示

```bash
# 进入全终端交互（TUI），在输入框直接输入建模需求
uv run comsol-agent
```

在 TUI 中可输入例如：

- `创建一个宽1米、高0.5米的矩形`
- `在原点放一个半径0.3米的圆`
- `/demo` 运行内置演示
- `/plan` 切换为仅规划模式，下一句只解析为 JSON
- `/output 默认名.mph` 设置默认输出文件名

---

## 10. 最小脚本（无 LLM，仅几何）

不依赖 LLM，直接用内置几何计划调用 COMSOL Java API 生成 `.mph`，用于验证 COMSOL 环境与 API。

```bash
uv run python scripts/py_to_mph_minimal.py
```

该脚本会在项目 `models/` 下生成 `minimal_model.mph`（一个 1m×0.5m 矩形）。确保 `.env` 中已配置 `COMSOL_JAR_PATH`。

---

## 11. 可选参数速查

| 选项 | 说明 |
|------|------|
| `-o`, `--output <文件名>` | 输出 .mph 文件名（不含路径，落在配置的模型输出目录或项目 models/） |
| `--react` / `--no-react` | 使用 ReAct 完整流程 / 仅几何（默认 `--react`） |
| `--max-iterations N` | ReAct 最大迭代次数（默认 10） |
| `-v`, `--verbose` | 详细日志 |
| `--skip-check` | 跳过运行前环境检查 |
| `--backend <名称>` | 覆盖 LLM 后端（如 deepseek / kimi / ollama） |
| `--model <名称>` | 覆盖模型名称 |

示例：

```bash
uv run comsol-agent run "创建一个矩形" -o out.mph -v --max-iterations 12
uv run comsol-agent run "创建椭圆" --no-react --backend ollama
```

---

## 12. 按模块能力对照

| 能力 | 推荐命令示例 |
|------|----------------|
| **几何 - 矩形** | `run "创建一个宽1米、高0.5米的矩形" -o rect.mph` |
| **几何 - 圆** | `run "在原点放置一个半径为0.3米的圆" -o circle.mph` |
| **几何 - 椭圆** | `run "创建长轴1米短轴0.6米的椭圆，中心(0.5,0.5)" -o ellipse.mph` |
| **几何 - 多形状** | `run "一个1x0.5矩形和(0.5,0.25)处半径0.1的圆" -o multi.mph` |
| **仅解析** | `plan "创建一个矩形"` 或 `plan "..." -o plan.json` |
| **从 JSON 执行** | `exec plan.json -o model.mph` 或 `exec plan.json --code-only` |
| **ReAct 全流程** | `run "创建传热模型，矩形域，温度边界，稳态求解" -o heat.mph` |
| **传统仅几何** | `run "创建一个矩形" --no-react -o rect.mph` |
| **环境诊断** | `doctor` |
| **演示解析** | `demo` |
| **无 LLM 几何** | `uv run python scripts/py_to_mph_minimal.py` |

以上命令均可直接复制到终端执行（将 `uv run` 替换为本地安装方式即可）。
