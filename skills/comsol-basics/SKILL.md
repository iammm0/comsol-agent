---
name: comsol-basics
description: COMSOL 几何与建模基础概念与经验
version: "1.0"
tags: [comsol, geometry, 几何, 建模, 基础]
triggers: [矩形, 圆, 椭圆, 几何, 建模, 创建, 画, 放置]
---

## COMSOL 几何建模要点

- **矩形 (rectangle)**：需 `width`（宽度）、`height`（高度）；位置 `position` 为 `(x, y)`，默认 (0,0)。
- **圆 (circle)**：需 `radius`（半径）；中心由 `position` 指定。
- **椭圆 (ellipse)**：需长轴 `a`、短轴 `b`；中心由 `position` 指定。
- 长度单位默认**米 (m)**；在 plan 中可指定 `units`（如 "m", "mm"）。
- 模型名称在 plan 中用 `model_name` 指定，宜简短无空格（如 `geometry_model`）。

## 几何顺序与组合

- 先创建的实体在 COMSOL 中序号较小；多形状时按用户描述顺序放入 `shapes` 数组即可。
- 圆环、带孔板：先建外轮廓（大矩形或大圆），再建内轮廓（小圆等），后续在 COMSOL 中做布尔减（difference）或由用户说明“挖孔”。
- L 形、阶梯形：用多个矩形分别描述，位置衔接好即可。

## 命名与 JSON 规范

- 形状 `name` 可自动生成：rect1, circ1, ell1 等；多形状时保持唯一。
- 输出 JSON 中数值均为浮点数；未指定位置用 (0, 0)，未指定单位用 "m"。
