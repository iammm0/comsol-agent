# Java API 调用层实现伪代码

## 概述

本文档展示 Java API 调用层的具体实现细节，包括 API 映射、代码生成、错误处理等核心流程。

---

## 1. JSON 到 Java API 的映射策略

### 1.1 映射器设计

```java
/**
 * JSON 计划到 Java API 的映射器
 * 
 * 核心思想：
 * 1. 解析 JSON 计划
 * 2. 识别需要创建的组件
 * 3. 生成对应的 API 调用序列
 * 4. 执行或生成代码
 */
public class PlanToAPIMapper {
    
    /**
     * 映射几何计划到 API 调用
     * 
     * 伪代码流程：
     * 1. 解析 JSON 计划
     * 2. 创建 GeometryBuilder
     * 3. 遍历形状并调用创建方法
     * 4. 处理形状关系
     * 5. 构建几何
     */
    public static GeometryBuilder mapGeometryPlan(String jsonPlan) {
        // 解析 JSON
        GeometryPlan plan = parseJSONPlan(jsonPlan);
        
        // 创建构建器
        GeometryBuilder builder = new GeometryBuilder(
            plan.getModelName(),
            plan.getDimension()
        );
        
        // 映射形状
        for (GeometryShape shape : plan.getShapes()) {
            mapShapeToAPI(builder, shape);
        }
        
        // 映射关系
        if (plan.hasRelations()) {
            mapRelationsToAPI(builder, plan.getRelations());
        }
        
        return builder;
    }
    
    /**
     * 映射单个形状到 API 调用
     * 
     * 伪代码：
     * 1. 根据形状类型选择映射方法
     * 2. 提取参数
     * 3. 调用对应的创建方法
     */
    private static void mapShapeToAPI(GeometryBuilder builder, GeometryShape shape) {
        String type = shape.getType();
        Map<String, Double> params = shape.getParameters();
        Position pos = shape.getPosition();
        
        switch (type) {
            case "rectangle":
                builder.addRectangle(
                    shape.getName(),
                    params.get("width"),
                    params.get("height"),
                    pos.getX(),
                    pos.getY()
                );
                break;
                
            case "circle":
                builder.addCircle(
                    shape.getName(),
                    params.get("radius"),
                    pos.getX(),
                    pos.getY()
                );
                break;
                
            case "ellipse":
                builder.addEllipse(
                    shape.getName(),
                    params.get("a"),
                    params.get("b"),
                    pos.getX(),
                    pos.getY()
                );
                break;
                
            default:
                throw new IllegalArgumentException("不支持的形状类型: " + type);
        }
    }
}
```

### 1.2 参数映射表

```java
/**
 * 参数映射表
 * 
 * 定义 JSON 参数名到 COMSOL API 参数名的映射
 */
public class ParameterMapping {
    private static final Map<String, Map<String, String>> SHAPE_PARAM_MAPPING;
    
    static {
        SHAPE_PARAM_MAPPING = new HashMap<>();
        
        // 矩形参数映射
        Map<String, String> rectangleMapping = new HashMap<>();
        rectangleMapping.put("width", "size[0]");
        rectangleMapping.put("height", "size[1]");
        rectangleMapping.put("x", "pos[0]");
        rectangleMapping.put("y", "pos[1]");
        SHAPE_PARAM_MAPPING.put("rectangle", rectangleMapping);
        
        // 圆形参数映射
        Map<String, String> circleMapping = new HashMap<>();
        circleMapping.put("radius", "r");
        circleMapping.put("x", "pos[0]");
        circleMapping.put("y", "pos[1]");
        SHAPE_PARAM_MAPPING.put("circle", circleMapping);
        
        // 椭圆参数映射
        Map<String, String> ellipseMapping = new HashMap<>();
        ellipseMapping.put("a", "a");
        ellipseMapping.put("b", "b");
        ellipseMapping.put("x", "pos[0]");
        ellipseMapping.put("y", "pos[1]");
        SHAPE_PARAM_MAPPING.put("ellipse", ellipseMapping);
    }
    
    /**
     * 获取参数映射
     */
    public static Map<String, String> getMapping(String shapeType) {
        return SHAPE_PARAM_MAPPING.getOrDefault(shapeType, new HashMap<>());
    }
    
    /**
     * 转换参数值
     * 
     * 伪代码：
     * 1. 获取映射表
     * 2. 转换参数名
     * 3. 转换参数值（如单位转换）
     */
    public static Map<String, Object> convertParameters(
        String shapeType,
        Map<String, Double> jsonParams
    ) {
        Map<String, String> mapping = getMapping(shapeType);
        Map<String, Object> apiParams = new HashMap<>();
        
        for (Map.Entry<String, Double> entry : jsonParams.entrySet()) {
            String jsonKey = entry.getKey();
            String apiKey = mapping.getOrDefault(jsonKey, jsonKey);
            Object apiValue = convertValue(jsonKey, entry.getValue());
            apiParams.put(apiKey, apiValue);
        }
        
        return apiParams;
    }
    
    /**
     * 转换参数值（单位转换等）
     */
    private static Object convertValue(String key, Double value) {
        // 单位转换（如果需要）
        // 例如：如果 key 是 "width" 且单位是 "cm"，转换为 "m"
        return value;
    }
}
```

---

## 2. Java 代码生成策略

### 2.1 代码生成器设计

```java
/**
 * Java 代码生成器
 * 
 * 职责：将 API 调用转换为完整的 Java 源代码
 */
public class JavaCodeGenerator {
    
    /**
     * 生成完整的 Java 类
     * 
     * 伪代码：
     * 1. 生成包声明和导入
     * 2. 生成类声明
     * 3. 生成主方法
     * 4. 生成 API 调用代码
     * 5. 生成异常处理
     */
    public String generateClass(GeometryPlan plan) {
        CodeBuilder code = new CodeBuilder();
        
        // 1. 包声明和导入
        code.append("package com.comsol.agent;");
        code.appendEmptyLine();
        code.append("import com.comsol.model.*;");
        code.append("import com.comsol.model.util.*;");
        code.appendEmptyLine();
        
        // 2. 类声明
        code.append("public class GeneratedModel {");
        code.indent();
        
        // 3. 主方法
        code.append("public static void main(String[] args) {");
        code.indent();
        code.append("try {");
        code.indent();
        
        // 4. 创建模型
        code.append("// 创建模型");
        code.append("Model model = ModelUtil.create(\"" + plan.getModelName() + "\");");
        code.appendEmptyLine();
        
        // 5. 创建几何节点
        code.append("// 创建几何节点");
        code.append("model.geom().create(\"geom1\", " + plan.getDimension() + ");");
        code.appendEmptyLine();
        
        // 6. 生成形状创建代码
        for (GeometryShape shape : plan.getShapes()) {
            code.append(generateShapeCode(shape));
            code.appendEmptyLine();
        }
        
        // 7. 构建几何
        code.append("// 构建几何");
        code.append("model.geom(\"geom1\").run();");
        code.appendEmptyLine();
        
        // 8. 保存模型
        code.append("// 保存模型");
        code.append("model.save(\"output.mph\");");
        code.append("System.out.println(\"模型已保存\");");
        
        // 9. 异常处理
        code.deindent();
        code.append("} catch (Exception e) {");
        code.indent();
        code.append("System.err.println(\"错误: \" + e.getMessage());");
        code.append("e.printStackTrace();");
        code.append("System.exit(1);");
        code.deindent();
        code.append("}");
        
        code.deindent();
        code.append("}");
        
        code.deindent();
        code.append("}");
        
        return code.toString();
    }
    
    /**
     * 生成单个形状的代码
     */
    private String generateShapeCode(GeometryShape shape) {
        CodeBuilder code = new CodeBuilder();
        
        String name = shape.getName();
        String type = shape.getType();
        
        // 注释
        code.append("// 创建 " + type + ": " + name);
        
        // 创建形状
        code.append("model.geom(\"geom1\").create(\"" + name + "\", \"" + 
                   mapShapeTypeToCOMSOLType(type) + "\");");
        
        // 设置参数
        Map<String, Object> apiParams = ParameterMapping.convertParameters(
            type,
            shape.getParameters()
        );
        
        for (Map.Entry<String, Object> entry : apiParams.entrySet()) {
            String paramName = entry.getKey();
            Object paramValue = entry.getValue();
            
            // 根据参数类型生成不同的设置代码
            if (paramName.contains("[")) {
                // 数组参数（如 size[0], pos[0]）
                code.append(generateArrayParameterCode(name, paramName, paramValue));
            } else {
                // 标量参数
                code.append("model.geom(\"geom1\").feature(\"" + name + 
                           "\").set(\"" + paramName + "\", " + paramValue + ");");
            }
        }
        
        return code.toString();
    }
    
    /**
     * 生成数组参数代码
     * 
     * 例如：size[0] 和 size[1] 需要合并为一个数组
     */
    private String generateArrayParameterCode(
        String shapeName,
        String paramName,
        Object paramValue
    ) {
        // 提取数组名和索引
        // 例如：size[0] -> arrayName="size", index=0
        String arrayName = paramName.substring(0, paramName.indexOf('['));
        int index = Integer.parseInt(
            paramName.substring(paramName.indexOf('[') + 1, paramName.indexOf(']'))
        );
        
        // 这里简化处理，实际需要收集所有索引的值
        return "// TODO: 设置数组参数 " + arrayName + "[" + index + "] = " + paramValue;
    }
    
    /**
     * 映射形状类型到 COMSOL 类型
     */
    private String mapShapeTypeToCOMSOLType(String type) {
        Map<String, String> mapping = new HashMap<>();
        mapping.put("rectangle", "Rectangle");
        mapping.put("circle", "Circle");
        mapping.put("ellipse", "Ellipse");
        return mapping.getOrDefault(type, type);
    }
}
```

### 2.2 代码构建器辅助类

```java
/**
 * 代码构建器
 * 
 * 辅助类，用于方便地构建 Java 代码字符串
 */
public class CodeBuilder {
    private StringBuilder code;
    private int indentLevel;
    private static final String INDENT = "    ";
    
    public CodeBuilder() {
        this.code = new StringBuilder();
        this.indentLevel = 0;
    }
    
    public CodeBuilder append(String line) {
        for (int i = 0; i < indentLevel; i++) {
            code.append(INDENT);
        }
        code.append(line).append("\n");
        return this;
    }
    
    public CodeBuilder appendEmptyLine() {
        code.append("\n");
        return this;
    }
    
    public CodeBuilder indent() {
        indentLevel++;
        return this;
    }
    
    public CodeBuilder deindent() {
        if (indentLevel > 0) {
            indentLevel--;
        }
        return this;
    }
    
    @Override
    public String toString() {
        return code.toString();
    }
}
```

---

## 3. 直接 API 调用实现

### 3.1 COMSOLRunner 详细实现

```java
/**
 * COMSOL API 运行器（直接调用方式）
 * 
 * 与代码生成不同，这里直接调用 COMSOL Java API
 */
public class COMSOLRunner {
    private Model model;
    private boolean jvmStarted = false;
    
    /**
     * 从计划创建模型（直接 API 调用）
     * 
     * 伪代码：
     * 1. 确保 JVM 已启动
     * 2. 创建模型对象
     * 3. 创建几何节点
     * 4. 遍历形状并创建
     * 5. 构建几何
     * 6. 保存模型
     */
    public Path createModelFromPlan(GeometryPlan plan) throws ModelException {
        try {
            // 1. 确保 JVM 已启动
            ensureJVMStarted();
            
            // 2. 创建模型
            this.model = ModelUtil.create(plan.getModelName());
            
            // 3. 创建几何节点
            model.geom().create("geom1", plan.getDimension());
            
            // 4. 创建形状
            for (GeometryShape shape : plan.getShapes()) {
                createShape(shape);
            }
            
            // 5. 处理关系
            if (plan.hasRelations()) {
                processRelations(plan.getRelations());
            }
            
            // 6. 构建几何
            model.geom("geom1").run();
            
            // 7. 保存模型
            String outputPath = "output/" + plan.getModelName() + ".mph";
            model.save(outputPath);
            
            return Paths.get(outputPath);
            
        } catch (Exception e) {
            throw new ModelException("创建模型失败: " + e.getMessage(), e);
        }
    }
    
    /**
     * 创建单个形状（直接 API 调用）
     */
    private void createShape(GeometryShape shape) throws ModelException {
        String name = shape.getName();
        String type = shape.getType();
        
        try {
            // 创建形状对象
            model.geom("geom1").create(name, mapShapeTypeToCOMSOLType(type));
            
            // 获取形状特征对象
            Feature feature = model.geom("geom1").feature(name);
            
            // 设置参数
            Map<String, Object> apiParams = ParameterMapping.convertParameters(
                type,
                shape.getParameters()
            );
            
            for (Map.Entry<String, Object> entry : apiParams.entrySet()) {
                String paramName = entry.getKey();
                Object paramValue = entry.getValue();
                
                // 处理数组参数
                if (paramName.contains("[")) {
                    setArrayParameter(feature, paramName, paramValue);
                } else {
                    feature.set(paramName, paramValue);
                }
            }
            
            // 设置位置
            Position pos = shape.getPosition();
            feature.set("pos", new double[]{pos.getX(), pos.getY()});
            
        } catch (Exception e) {
            throw new ModelException(
                "创建形状 " + name + " 失败: " + e.getMessage(), e
            );
        }
    }
    
    /**
     * 设置数组参数
     * 
     * 伪代码：
     * 1. 解析参数名（如 size[0]）
     * 2. 获取或创建数组
     * 3. 设置数组元素
     * 4. 设置整个数组
     */
    private void setArrayParameter(Feature feature, String paramName, Object value) {
        // 提取数组名和索引
        String arrayName = paramName.substring(0, paramName.indexOf('['));
        int index = Integer.parseInt(
            paramName.substring(paramName.indexOf('[') + 1, paramName.indexOf(']'))
        );
        
        // 获取现有数组或创建新数组
        Object existingArray = feature.getStringArray(arrayName);
        double[] array;
        
        if (existingArray != null && existingArray instanceof double[]) {
            array = (double[]) existingArray;
        } else {
            // 创建默认大小的数组
            array = new double[2];  // 假设是 2D
        }
        
        // 设置数组元素
        if (value instanceof Number) {
            array[index] = ((Number) value).doubleValue();
        }
        
        // 设置整个数组
        feature.set(arrayName, array);
    }
    
    /**
     * 确保 JVM 已启动
     */
    private void ensureJVMStarted() {
        if (!jvmStarted) {
            // 启动 JVM
            String comsolJarPath = System.getProperty("comsol.jar.path");
            if (comsolJarPath == null) {
                throw new RuntimeException("COMSOL JAR 路径未设置");
            }
            
            // 启动 JVM（使用 JPype 或直接调用）
            // 这里简化，实际需要根据使用的 Java 互操作库来实现
            jvmStarted = true;
        }
    }
}
```

---

## 4. 错误处理与验证

### 4.1 API 调用验证

```java
/**
 * API 调用验证器
 */
public class APICallValidator {
    
    /**
     * 验证几何参数
     */
    public static void validateGeometryParameters(GeometryShape shape) {
        Map<String, Double> params = shape.getParameters();
        
        // 验证参数是否为正数
        for (Map.Entry<String, Double> entry : params.entrySet()) {
            if (entry.getValue() <= 0) {
                throw new IllegalArgumentException(
                    "参数 " + entry.getKey() + " 必须大于 0，当前值: " + entry.getValue()
                );
            }
        }
        
        // 验证位置
        Position pos = shape.getPosition();
        if (Double.isNaN(pos.getX()) || Double.isNaN(pos.getY())) {
            throw new IllegalArgumentException("位置坐标无效");
        }
        
        // 类型特定验证
        switch (shape.getType()) {
            case "rectangle":
                validateRectangleParams(params);
                break;
            case "circle":
                validateCircleParams(params);
                break;
            case "ellipse":
                validateEllipseParams(params);
                break;
        }
    }
    
    /**
     * 验证矩形参数
     */
    private static void validateRectangleParams(Map<String, Double> params) {
        if (!params.containsKey("width") || !params.containsKey("height")) {
            throw new IllegalArgumentException("矩形需要 width 和 height 参数");
        }
        
        double width = params.get("width");
        double height = params.get("height");
        
        if (width <= 0 || height <= 0) {
            throw new IllegalArgumentException("矩形的宽高必须大于 0");
        }
        
        // 检查尺寸是否合理（如不超过某个上限）
        if (width > 1000 || height > 1000) {
            throw new IllegalArgumentException("矩形尺寸过大（最大 1000m）");
        }
    }
    
    /**
     * 验证 API 调用结果
     */
    public static void validateAPICallResult(Object result, String operation) {
        if (result == null) {
            throw new ModelException("API 调用 " + operation + " 返回 null");
        }
        
        // 可以添加更多验证逻辑
        // 例如：检查对象是否有效、属性是否设置成功等
    }
}
```

### 4.2 异常处理策略

```java
/**
 * 模型异常类
 */
public class ModelException extends Exception {
    private String errorCode;
    private Map<String, Object> context;
    
    public ModelException(String message) {
        super(message);
        this.context = new HashMap<>();
    }
    
    public ModelException(String message, Throwable cause) {
        super(message, cause);
        this.context = new HashMap<>();
    }
    
    public ModelException withErrorCode(String code) {
        this.errorCode = code;
        return this;
    }
    
    public ModelException withContext(String key, Object value) {
        this.context.put(key, value);
        return this;
    }
}

/**
 * 错误恢复策略
 */
public class ErrorRecovery {
    
    /**
     * 尝试恢复错误
     * 
     * 伪代码：
     * 1. 分析错误类型
     * 2. 应用恢复策略
     * 3. 重试操作
     */
    public static boolean tryRecover(Exception error, Runnable operation) {
        if (error instanceof IllegalArgumentException) {
            // 参数错误，无法自动恢复
            return false;
        }
        
        if (error instanceof ModelException) {
            ModelException me = (ModelException) error;
            
            // 根据错误代码应用不同的恢复策略
            switch (me.getErrorCode()) {
                case "GEOMETRY_BUILD_FAILED":
                    // 几何构建失败，尝试简化几何
                    return trySimplifyGeometry(operation);
                    
                case "SAVE_FAILED":
                    // 保存失败，尝试使用不同的路径
                    return tryAlternativeSavePath(operation);
                    
                default:
                    return false;
            }
        }
        
        return false;
    }
}
```

---

## 5. 最佳实践总结

### 5.1 API 调用模式

```java
/**
 * 推荐的 API 调用模式
 */
public class BestPractices {
    
    /**
     * 模式 1: 创建 → 配置 → 构建
     */
    public void pattern1_CreateConfigureBuild() {
        // 1. 创建对象
        model.geom("geom1").create("rect1", "Rectangle");
        
        // 2. 配置参数
        Feature rect = model.geom("geom1").feature("rect1");
        rect.set("size", new double[]{1.0, 0.5});
        rect.set("pos", new double[]{0.0, 0.0});
        
        // 3. 构建
        model.geom("geom1").run();
    }
    
    /**
     * 模式 2: 批量操作
     */
    public void pattern2_BatchOperations() {
        // 批量创建
        String[] names = {"rect1", "rect2", "rect3"};
        for (String name : names) {
            model.geom("geom1").create(name, "Rectangle");
        }
        
        // 批量配置
        for (String name : names) {
            Feature feature = model.geom("geom1").feature(name);
            feature.set("size", new double[]{1.0, 0.5});
        }
        
        // 一次性构建
        model.geom("geom1").run();
    }
    
    /**
     * 模式 3: 错误处理
     */
    public void pattern3_ErrorHandling() {
        try {
            model.geom("geom1").create("rect1", "Rectangle");
            model.geom("geom1").feature("rect1").set("size", new double[]{1.0, 0.5});
            model.geom("geom1").run();
        } catch (Exception e) {
            // 记录错误
            logger.error("创建几何失败: " + e.getMessage(), e);
            
            // 清理资源
            if (model.geom().has("geom1")) {
                try {
                    model.geom().remove("geom1");
                } catch (Exception cleanupError) {
                    logger.warn("清理几何失败: " + cleanupError.getMessage());
                }
            }
            
            throw new ModelException("几何创建失败", e);
        }
    }
}
```

---

## 总结

Java API 调用层的实现要点：

1. **映射清晰**：JSON 参数到 API 参数的映射表
2. **代码生成**：支持生成可执行的 Java 源代码
3. **直接调用**：支持直接调用 COMSOL Java API
4. **错误处理**：完善的验证和异常处理机制
5. **最佳实践**：遵循 COMSOL API 的推荐使用模式
