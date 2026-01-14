# COMSOL Java API 代码

本目录包含 COMSOL Java API 的示例代码和工具类。

## 结构

- `src/main/java/com/comsol/agent/` - Java 源代码
  - `BaseModelBuilder.java` - 模型构建器基类
  - `GeometryBuilder.java` - 几何构建器
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
