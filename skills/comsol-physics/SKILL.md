---
name: comsol-physics
description: COMSOL 物理场建模常用概念与经验
version: "1.0"
tags: [comsol, physics, 物理场, 传热, 电磁, 结构, 流体]
triggers: [传热, 热, 温度, 电磁, 电场, 磁场, 结构, 力学, 流体, 物理场, 边界条件]
---

## 物理场类型与 COMSOL 对应

- **heat（传热）**：Heat Transfer 模块；常用边界条件：温度、热流、对流、辐射。
- **electromagnetic（电磁）**：电磁波/AC-DC 等；边界：完美导体、阻抗、散射等。
- **structural（结构力学）**：Solid Mechanics；边界：固定、载荷、压力、位移。
- **fluid（流体）**：单相流等；边界：入口/出口速度或压力、壁面无滑移。

## 常用概念

- **稳态 vs 瞬态**：稳态只求空间分布；瞬态需时间范围与步长。
- **边界条件**：先几何再物理场；边界条件施加在几何边界上（边或面）。
- **材料属性**：传热常用导热系数、密度、比热；结构常用杨氏模量、泊松比；流体常用密度、粘度。
- **多物理场**：若用户提到“热-结构耦合”“流固耦合”等，需在 required_steps 中同时包含相应物理场与求解顺序。

## 规划输出约定

- 物理场计划 JSON 中 `fields` 为数组，每项含 `type` 与 `parameters`。
- `parameters` 中可包含 `boundary_conditions`、`material_properties`、`solver_settings` 等子对象。
- 用户只说“加物理场”且未指定类型时，默认使用 **heat（传热）**。
