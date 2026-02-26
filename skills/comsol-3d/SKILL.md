---
name: comsol-3d
description: COMSOL 3D 几何建模要点与经验
version: "1.0"
tags: [comsol, geometry, 3D, 三维, 建模, 立体]
triggers: [3D, 三维, 立方体, 长方体, block, 圆柱, cylinder, 球, sphere, 锥, cone, 圆环, torus, 拉伸, extrude, 旋转体, revolve, 工作面, 深度, depth]
---

## COMSOL 3D 几何建模要点

### 3D 基本体

- **Block（长方体）**：需 `width`、`height`、`depth`；位置 `(x, y, z)`，默认 (0,0,0)。
- **Cylinder（圆柱）**：需 `radius` 和 `height`；`r` 为底面半径，`h` 为高度。
- **Sphere（球）**：需 `radius`；位置为球心坐标。
- **Cone（锥体）**：需 `radius_bottom`、`radius_top`（可为 0，表示尖锥）、`height`。
- **Torus（圆环）**：需 `radius_major`（环的中心到圆环中心的距离）和 `radius_minor`（截面半径）。

### 3D 操作

- **Extrude（拉伸）**：将 2D 截面沿法线方向拉伸为 3D 实体。需指定 `distance`（拉伸距离）。
- **Revolve（旋转）**：将 2D 截面绕轴旋转生成旋转体。需指定 `angle`（旋转角度，度）。
- **WorkPlane（工作面）**：在 3D 几何中创建 2D 绘图平面，常用 `quickz` 指定 z 偏移。
- **Sweep（扫掠）**：沿路径拉伸截面。

### 维度 (dimension) 判断

- 用户提到 3D、三维、立方体/长方体(block)、圆柱(cylinder)、球(sphere)、锥(cone)、圆环(torus)、拉伸(extrude)、深度(depth) 等关键词时，`dimension` 设为 **3**。
- 否则默认为 **2**（2D）。
- 2D 和 3D 不能混用：3D 形状（Block/Cylinder/Sphere/Cone/Torus）不能出现在 2D 几何中。

### 布尔运算（2D/3D 通用）

- **Union（并集）**：合并多个形状。
- **Difference（差集）**：用一个形状从另一个中减去。常用于"挖孔"。
- **Intersection（交集）**：取多个形状的交叠部分。

### 位置与尺寸约定

- 3D 位置用 `(x, y, z)`；2D 位置用 `(x, y)`。
- COMSOL Block 的 size 参数顺序为 `[width, depth, height]`（x, y, z 方向）。
- 未指定位置时默认 (0, 0, 0)；未指定单位时默认"米 (m)"。
- rotation 可选，用 `rx`/`ry`/`rz` 指定各轴旋转角度（度）。

### 常见 3D 建模场景

- **散热器翅片**：Block（基板）+ 多个 Block（翅片），Union 合并。
- **管道**：Cylinder（外管）- Cylinder（内管），Difference 挖孔。
- **轴承**：Torus + Cylinder 组合。
- **旋转体零件**：先画 2D 截面（Polygon/Rectangle），再 Revolve 旋转。
