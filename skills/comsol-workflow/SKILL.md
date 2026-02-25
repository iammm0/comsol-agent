---
name: comsol-workflow
description: COMSOL 研究、网格与求解流程的经验
version: "1.0"
tags: [comsol, 研究, 网格, 求解, 稳态, 瞬态, 频域]
triggers: [求解, 稳态, 瞬态, 网格, 研究, 频域, 特征值, 仿真]
---

## 建模步骤顺序（必须遵守）

1. **几何 (create_geometry)** — 先建几何。
2. **物理场 (add_physics)** — 在几何上添加物理场与边界条件。
3. **网格 (generate_mesh)** — 划分网格（可选，部分研究可自动）。
4. **研究 (configure_study)** — 选择研究类型（稳态/瞬态/频域/特征值等）。
5. **求解 (solve)** — 运行求解器。

几何必须在物理场和网格之前；物理场通常在研究配置之前。

## 研究类型选择

- **stationary（稳态）**：温度场、静力学、直流电磁等不随时间变化的问题；最常用。
- **time_dependent（瞬态）**：随时间变化；需参数如时间范围、步长。
- **eigenvalue（特征值）**：模态、稳定性分析等。
- **frequency（频域）**：谐波、频响；需频率范围等参数。
- 用户未明确说“瞬态”“频域”时，默认 **stationary**。

## 任务类型与步骤规划

- **task_type: geometry** — 仅几何，required_steps 至少含 `create_geometry`。
- **task_type: physics** — 几何 + 物理场，含 `create_geometry`, `add_physics`。
- **task_type: study** — 几何 + 物理场 + 研究配置，含 `configure_study`。
- **task_type: full** — 完整仿真：`create_geometry` → `add_physics` → `generate_mesh` → `configure_study` → `solve`。
- 若用户说“传热模型并求解”“完整仿真”，应规划为 **full** 并给出上述五步。

## 经验要点

- 先解析用户意图再定 task_type 与 required_steps，避免漏步骤或顺序错。
- 网格步可省略或由求解器默认处理时，仍建议在 full 流程中保留 generate_mesh 占位以便扩展。
- 错误处理：几何失败时不必继续物理场；上一步失败可重试或跳过再继续。
