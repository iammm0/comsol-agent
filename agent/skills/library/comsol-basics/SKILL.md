---
name: comsol-basics
description: COMSOL 几何与建模基础概念与经验（2D/3D）
version: "2.0"
tags: [comsol, geometry, 几何, 建模, 基础, 2D, 3D]
triggers: [矩形, 圆, 椭圆, 几何, 建模, 创建, 画, 放置, 立方体, 圆柱, 球, 锥, 圆环, 多边形]
---

## COMSOL 几何建模要点

### 2D 形状
- **矩形 (rectangle)**：需 `width`（宽度）、`height`（高度）；位置 `position` 为 `(x, y)`，默认 (0,0)。
- **圆 (circle)**：需 `radius`（半径）；中心由 `position` 指定。
- **椭圆 (ellipse)**：需长轴 `a`、短轴 `b`；中心由 `position` 指定。
- **多边形 (polygon)**：需顶点坐标数组 `x` 和 `y`，至少 3 个顶点。

### 3D 形状
- **长方体 (block)**：需 `width`、`height`、`depth`；位置 `(x, y, z)`，默认 (0,0,0)。
- **圆柱 (cylinder)**：需 `radius`、`height`；位置为底面中心。
- **球 (sphere)**：需 `radius`；位置为球心。
- **锥体 (cone)**：需 `radius_bottom`、`radius_top`（可为 0）、`height`。
- **圆环 (torus)**：需 `radius_major`、`radius_minor`。

### 维度与单位
- `dimension` 为 2 或 3，含 3D 形状时必须设为 3。
- 长度单位默认**米 (m)**；在 plan 中可指定 `units`（如 "m", "mm"）。
- 模型名称在 plan 中用 `model_name` 指定，宜简短无空格。

## 几何顺序与组合

- 先创建的实体在 COMSOL 中序号较小；多形状时按用户描述顺序放入 `shapes` 数组。
- 圆环、带孔板：先建外轮廓（大矩形或大圆），再建内轮廓（小圆等），用布尔 Difference 挖孔。
- L 形、阶梯形：用多个矩形分别描述，位置衔接好即可。
- 3D 旋转体：先画 2D 截面，再用 Revolve 操作。

## 命名与 JSON 规范

- 形状 `name` 可自动生成：rect1, circ1, ell1, blk1, cyl1, sph1, cone1, tor1 等。
- 操作 `name` 也可自动生成：uni1, dif1, ext1, rev1 等。
- 输出 JSON 中数值均为浮点数；未指定位置用默认值，未指定单位用 "m"。
