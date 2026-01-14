#!/bin/bash
# COMSOL Java 代码编译脚本

# 检查 COMSOL JAR 路径
if [ -z "$COMSOL_JAR_PATH" ]; then
    echo "错误: 请设置 COMSOL_JAR_PATH 环境变量"
    exit 1
fi

# 创建构建目录
mkdir -p build

# 编译
javac -cp "$COMSOL_JAR_PATH" -d build src/main/java/com/comsol/agent/*.java

if [ $? -eq 0 ]; then
    echo "编译成功！"
else
    echo "编译失败！"
    exit 1
fi
