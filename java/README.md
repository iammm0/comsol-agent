# COMSOL Java API 代码

本目录包含 COMSOL Java API 的示例代码和工具类。

## 结构

- `src/main/java/com/comsol/agent/` - Java 源代码
  - `BaseModelBuilder.java` - 模型构建器基类（save、setParam、setVariable、validateModel）
  - `GeometryBuilder.java` - 几何构建器（矩形/圆/椭圆/多边形、布尔运算、2D/3D）
  - `PhysicsBuilder.java` - 物理场构建器（添加物理场、边界条件）
  - `MaterialBuilder.java` - 材料构建器（创建材料、属性、分配到域）
  - `MeshBuilder.java` - 网格构建器（创建网格、Size、run）
  - `StudyBuilder.java` - 研究/求解构建器（创建研究、求解器、runStudy）
  - `ComsolModelHelper.java` - 静态工具（create/load/save、setParam、setVariable）
  - `ModelException.java` - 模型相关异常
  - `Main.java` - 示例主类

## 编译

```bash
# 设置 COMSOL JAR 路径
export COMSOL_JAR_PATH=/path/to/comsol.jar

# 编译
javac -cp "$COMSOL_JAR_PATH" -d build src/main/java/com/comsol/agent/*.java
```

## 运行

```bash
java -cp "$COMSOL_JAR_PATH:build" com.comsol.agent.Main
```

## 使用脚本

提供了便捷的编译和运行脚本：

```bash
# Linux/Mac
./compile.sh
./run.sh

# Windows
compile.bat
run.bat
```
