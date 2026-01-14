#!/bin/bash
# COMSOL Java 代码运行脚本

# 检查 COMSOL JAR 路径
if [ -z "$COMSOL_JAR_PATH" ]; then
    echo "错误: 请设置 COMSOL_JAR_PATH 环境变量"
    exit 1
fi

# 运行
java -cp "$COMSOL_JAR_PATH:build" com.comsol.agent.Main
