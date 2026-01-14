# Java API 调用层架构伪代码

## 概述

Java API 调用层负责将结构化的建模计划转换为 COMSOL Java API 调用，是整个系统的"执行引擎"。
本文件展示 Java API 层的设计思路和实现架构。

---

## 1. 核心设计理念

```
结构化 JSON → [API 映射] → Java API 调用 → [执行] → .mph 文件
```

### 1.1 API 调用层次结构

```
BaseModelBuilder (抽象基类)
    ├── GeometryBuilder (几何构建)
    ├── PhysicsBuilder (物理场构建)
    ├── MeshBuilder (网格构建)
    ├── StudyBuilder (研究构建)
    └── MaterialBuilder (材料构建)
```

---

## 2. BaseModelBuilder 伪代码

```java
/**
 * COMSOL 模型构建器基类
 * 
 * 职责：
 * 1. 管理模型生命周期
 * 2. 提供通用的模型操作方法
 * 3. 定义构建接口
 */
public abstract class BaseModelBuilder {
    protected Model model;
    protected String modelName;
    protected Map<String, Object> metadata;
    
    /**
     * 构造函数
     * 
     * 伪代码流程：
     * 1. 创建 COMSOL 模型对象
     * 2. 设置模型元数据
     * 3. 初始化构建器状态
     */
    public BaseModelBuilder(String modelName) {
        this.modelName = modelName;
        this.model = ModelUtil.create(modelName);
        this.metadata = new HashMap<>();
        
        // 设置默认元数据
        this.metadata.put("created_by", "COMSOL Agent");
        this.metadata.put("created_at", System.currentTimeMillis());
    }
    
    /**
     * 抽象构建方法
     * 子类必须实现具体的构建逻辑
     */
    public abstract void build();
    
    /**
     * 保存模型
     * 
     * 伪代码：
     * 1. 验证模型完整性
     * 2. 构建输出路径
     * 3. 保存模型文件
     * 4. 验证保存结果
     */
    public void save(String filePath) throws ModelException {
        // 验证模型
        if (!this.validateModel()) {
            throw new ModelException("模型验证失败，无法保存");
        }
        
        // 保存模型
        try {
            model.save(filePath);
            System.out.println("模型已保存到: " + filePath);
        } catch (Exception e) {
            throw new ModelException("保存模型失败: " + e.getMessage(), e);
        }
    }
    
    /**
     * 验证模型
     * 
     * 伪代码：
     * 1. 检查模型对象是否有效
     * 2. 检查必要的组件是否存在
     * 3. 检查参数是否合理
     */
    protected boolean validateModel() {
        if (model == null) {
            return false;
        }
        // 子类可以重写此方法添加特定验证
        return true;
    }
    
    /**
     * 获取模型对象
     */
    public Model getModel() {
        return model;
    }
}
```

---

## 3. GeometryBuilder 伪代码

```java
/**
 * 几何构建器
 * 
 * 职责：
 * 1. 创建几何节点
 * 2. 创建几何形状（矩形、圆形、椭圆等）
 * 3. 处理几何操作（布尔运算、变换等）
 * 4. 构建几何
 */
public class GeometryBuilder extends BaseModelBuilder {
    private String geomName;
    private int dimension;  // 2D 或 3D
    private List<GeometryShape> shapes;
    
    /**
     * 构造函数
     * 
     * 伪代码：
     * 1. 调用父类构造函数
     * 2. 创建几何节点
     * 3. 初始化形状列表
     */
    public GeometryBuilder(String modelName, int dimension) {
        super(modelName);
        this.dimension = dimension;
        this.geomName = "geom1";
        this.shapes = new ArrayList<>();
        
        // 创建几何节点
        model.geom().create(geomName, dimension);
    }
    
    /**
     * 从 JSON 计划构建几何
     * 
     * 伪代码流程：
     * 1. 解析 JSON 计划
     * 2. 遍历形状列表
     * 3. 为每个形状调用对应的创建方法
     * 4. 处理形状关系（如布尔运算）
     * 5. 构建几何
     */
    public void buildFromPlan(GeometryPlan plan) {
        // 遍历形状
        for (GeometryShape shape : plan.getShapes()) {
            this.addShape(shape);
        }
        
        // 处理形状关系（如并集、差集等）
        this.processShapeRelations(plan.getRelations());
        
        // 构建几何
        this.build();
    }
    
    /**
     * 添加形状（统一接口）
     * 
     * 伪代码：
     * 1. 根据形状类型路由到对应的创建方法
     * 2. 验证参数
     * 3. 创建形状
     * 4. 记录到形状列表
     */
    public void addShape(GeometryShape shape) {
        // 参数验证
        this.validateShapeParameters(shape);
        
        // 根据类型创建
        switch (shape.getType()) {
            case "rectangle":
                this.addRectangle(shape);
                break;
            case "circle":
                this.addCircle(shape);
                break;
            case "ellipse":
                this.addEllipse(shape);
                break;
            case "polygon":
                this.addPolygon(shape);
                break;
            default:
                throw new IllegalArgumentException("不支持的形状类型: " + shape.getType());
        }
        
        // 记录形状
        this.shapes.add(shape);
    }
    
    /**
     * 添加矩形
     * 
     * 伪代码：
     * 1. 提取参数（宽、高、位置）
     * 2. 创建矩形几何对象
     * 3. 设置尺寸和位置
     * 4. 处理旋转（如果有）
     */
    public void addRectangle(GeometryShape shape) {
        String name = shape.getName();
        double width = shape.getParameter("width");
        double height = shape.getParameter("height");
        double x = shape.getPosition().getX();
        double y = shape.getPosition().getY();
        
        // 创建矩形
        model.geom(geomName).create(name, "Rectangle");
        
        // 设置尺寸
        model.geom(geomName).feature(name).set("size", new double[]{width, height});
        
        // 设置位置
        model.geom(geomName).feature(name).set("pos", new double[]{x, y});
        
        // 处理旋转（如果有）
        if (shape.hasRotation()) {
            double angle = shape.getRotation();
            model.geom(geomName).feature(name).set("rot", angle);
        }
    }
    
    /**
     * 添加圆形
     * 
     * 伪代码：
     * 1. 提取参数（半径、位置）
     * 2. 创建圆形几何对象
     * 3. 设置半径和位置
     */
    public void addCircle(GeometryShape shape) {
        String name = shape.getName();
        double radius = shape.getParameter("radius");
        double x = shape.getPosition().getX();
        double y = shape.getPosition().getY();
        
        // 创建圆形
        model.geom(geomName).create(name, "Circle");
        
        // 设置半径
        model.geom(geomName).feature(name).set("r", radius);
        
        // 设置位置
        model.geom(geomName).feature(name).set("pos", new double[]{x, y});
    }
    
    /**
     * 添加椭圆
     * 
     * 伪代码：
     * 1. 提取参数（长轴、短轴、位置）
     * 2. 创建椭圆几何对象
     * 3. 设置参数
     */
    public void addEllipse(GeometryShape shape) {
        String name = shape.getName();
        double a = shape.getParameter("a");  // 长轴
        double b = shape.getParameter("b");  // 短轴
        double x = shape.getPosition().getX();
        double y = shape.getPosition().getY();
        
        // 创建椭圆
        model.geom(geomName).create(name, "Ellipse");
        
        // 设置参数
        model.geom(geomName).feature(name).set("a", a);
        model.geom(geomName).feature(name).set("b", b);
        model.geom(geomName).feature(name).set("pos", new double[]{x, y});
    }
    
    /**
     * 处理形状关系（布尔运算）
     * 
     * 伪代码：
     * 1. 遍历关系列表
     * 2. 根据关系类型执行对应的布尔运算
     * 3. 更新形状列表
     */
    private void processShapeRelations(List<ShapeRelation> relations) {
        for (ShapeRelation relation : relations) {
            switch (relation.getType()) {
                case "union":
                    this.union(relation.getShapes());
                    break;
                case "difference":
                    this.difference(relation.getShapes());
                    break;
                case "intersection":
                    this.intersection(relation.getShapes());
                    break;
            }
        }
    }
    
    /**
     * 并集操作
     * 
     * 伪代码：
     * 1. 创建并集特征
     * 2. 设置输入对象
     * 3. 执行并集
     */
    private void union(List<String> shapeNames) {
        String unionName = "union1";
        model.geom(geomName).create(unionName, "Union");
        
        // 设置输入对象
        model.geom(geomName).feature(unionName)
            .set("input", shapeNames.toArray(new String[0]));
        
        // 执行并集
        model.geom(geomName).feature(unionName).set("keep", true);
    }
    
    /**
     * 构建几何
     * 
     * 伪代码：
     * 1. 验证几何完整性
     * 2. 执行构建操作
     * 3. 检查构建结果
     */
    @Override
    public void build() {
        try {
            // 构建几何
            model.geom(geomName).run();
            
            // 验证构建结果
            if (!this.validateGeometry()) {
                throw new ModelException("几何构建失败");
            }
            
            System.out.println("几何构建成功");
        } catch (Exception e) {
            throw new ModelException("构建几何时出错: " + e.getMessage(), e);
        }
    }
    
    /**
     * 验证几何
     * 
     * 伪代码：
     * 1. 检查几何节点是否存在
     * 2. 检查是否有有效的几何实体
     * 3. 检查几何是否可构建
     */
    private boolean validateGeometry() {
        try {
            // 检查几何节点
            if (!model.geom().has(geomName)) {
                return false;
            }
            
            // 检查是否有实体
            int numEntities = model.geom(geomName).getNDomains();
            return numEntities > 0;
        } catch (Exception e) {
            return false;
        }
    }
}
```

---

## 4. PhysicsBuilder 伪代码（未来扩展）

```java
/**
 * 物理场构建器
 * 
 * 职责：
 * 1. 添加物理场接口（传热、流体、电磁等）
 * 2. 设置边界条件
 * 3. 设置材料属性
 * 4. 配置求解器
 */
public class PhysicsBuilder extends BaseModelBuilder {
    private List<PhysicsInterface> physicsInterfaces;
    
    /**
     * 添加物理场接口
     * 
     * 伪代码：
     * 1. 根据物理场类型创建接口
     * 2. 设置默认参数
     * 3. 添加到接口列表
     */
    public void addPhysicsInterface(String physicsType) {
        // 创建物理场接口
        String interfaceName = this.generateInterfaceName(physicsType);
        model.physics().create(interfaceName, physicsType);
        
        // 设置默认参数
        this.setDefaultPhysicsParameters(interfaceName, physicsType);
        
        // 记录接口
        PhysicsInterface physics = new PhysicsInterface(interfaceName, physicsType);
        this.physicsInterfaces.add(physics);
    }
    
    /**
     * 设置边界条件
     * 
     * 伪代码：
     * 1. 选择边界
     * 2. 设置边界条件类型
     * 3. 设置参数值
     */
    public void setBoundaryCondition(
        String interfaceName,
        String boundaryName,
        String conditionType,
        Map<String, Object> parameters
    ) {
        // 创建边界条件
        model.physics(interfaceName).create(boundaryName, conditionType);
        
        // 设置参数
        for (Map.Entry<String, Object> entry : parameters.entrySet()) {
            model.physics(interfaceName)
                .feature(boundaryName)
                .set(entry.getKey(), entry.getValue());
        }
    }
    
    /**
     * 设置材料属性
     * 
     * 伪代码：
     * 1. 选择材料域
     * 2. 设置材料属性（如导热系数、密度等）
     */
    public void setMaterialProperties(
        String materialName,
        String domain,
        Map<String, Object> properties
    ) {
        // 创建材料
        model.materials().create(materialName);
        
        // 设置属性
        for (Map.Entry<String, Object> entry : properties.entrySet()) {
            model.materials(materialName)
                .propertyGroup("Def")
                .set(entry.getKey(), entry.getValue());
        }
        
        // 应用到域
        model.materials(materialName).selection().set(domain);
    }
}
```

---

## 5. API 映射层伪代码

```java
/**
 * API 映射器
 * 
 * 职责：将 JSON 计划映射到 Java API 调用
 */
public class APIMapper {
    /**
     * 映射几何计划到 API 调用
     * 
     * 伪代码：
     * 1. 解析 JSON 计划
     * 2. 创建 GeometryBuilder
     * 3. 调用构建方法
     * 4. 返回构建器实例
     */
    public static GeometryBuilder mapGeometryPlan(GeometryPlan plan) {
        // 创建构建器
        GeometryBuilder builder = new GeometryBuilder(
            plan.getModelName(),
            plan.getDimension()
        );
        
        // 构建几何
        builder.buildFromPlan(plan);
        
        return builder;
    }
    
    /**
     * 映射物理场计划到 API 调用
     * 
     * 伪代码：
     * 1. 解析物理场计划
     * 2. 创建 PhysicsBuilder
     * 3. 添加物理场接口
     * 4. 设置边界条件和材料
     */
    public static PhysicsBuilder mapPhysicsPlan(PhysicsPlan plan, Model model) {
        PhysicsBuilder builder = new PhysicsBuilder(model);
        
        // 添加物理场接口
        for (PhysicsInterfaceConfig config : plan.getInterfaces()) {
            builder.addPhysicsInterface(config.getType());
            
            // 设置边界条件
            for (BoundaryCondition bc : config.getBoundaryConditions()) {
                builder.setBoundaryCondition(
                    config.getName(),
                    bc.getName(),
                    bc.getType(),
                    bc.getParameters()
                );
            }
        }
        
        // 设置材料
        for (MaterialConfig material : plan.getMaterials()) {
            builder.setMaterialProperties(
                material.getName(),
                material.getDomain(),
                material.getProperties()
            );
        }
        
        return builder;
    }
}
```

---

## 6. 错误处理与验证

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
}

/**
 * API 调用验证器
 */
public class APICallValidator {
    /**
     * 验证几何参数
     * 
     * 伪代码：
     * 1. 检查参数是否为正数
     * 2. 检查参数是否在合理范围内
     * 3. 检查位置是否有效
     */
    public static void validateGeometryParameters(GeometryShape shape) {
        // 验证参数
        Map<String, Double> params = shape.getParameters();
        
        for (Map.Entry<String, Double> entry : params.entrySet()) {
            if (entry.getValue() <= 0) {
                throw new IllegalArgumentException(
                    "参数 " + entry.getKey() + " 必须大于 0"
                );
            }
        }
        
        // 验证位置
        Position pos = shape.getPosition();
        if (Double.isNaN(pos.getX()) || Double.isNaN(pos.getY())) {
            throw new IllegalArgumentException("位置坐标无效");
        }
    }
    
    /**
     * 验证 API 调用结果
     * 
     * 伪代码：
     * 1. 检查对象是否创建成功
     * 2. 检查属性是否设置成功
     * 3. 检查是否有错误信息
     */
    public static void validateAPICallResult(Object result) {
        if (result == null) {
            throw new ModelException("API 调用返回 null");
        }
        
        // 可以添加更多验证逻辑
    }
}
```

---

## 7. 代码生成策略

```java
/**
 * Java 代码生成器（用于生成可执行的 Java 文件）
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
        StringBuilder code = new StringBuilder();
        
        // 包声明和导入
        code.append("package com.comsol.agent;\n\n");
        code.append("import com.comsol.model.*;\n");
        code.append("import com.comsol.model.util.*;\n\n");
        
        // 类声明
        code.append("public class GeneratedModel {\n");
        code.append("    public static void main(String[] args) {\n");
        code.append("        try {\n");
        
        // 创建模型
        code.append("            Model model = ModelUtil.create(\"");
        code.append(plan.getModelName());
        code.append("\");\n");
        
        // 创建几何
        code.append("            model.geom().create(\"geom1\", 2);\n");
        
        // 生成形状创建代码
        for (GeometryShape shape : plan.getShapes()) {
            code.append(this.generateShapeCode(shape));
        }
        
        // 构建几何
        code.append("            model.geom(\"geom1\").run();\n");
        
        // 保存模型
        code.append("            model.save(\"output.mph\");\n");
        
        // 异常处理
        code.append("        } catch (Exception e) {\n");
        code.append("            System.err.println(\"错误: \" + e.getMessage());\n");
        code.append("            e.printStackTrace();\n");
        code.append("            System.exit(1);\n");
        code.append("        }\n");
        code.append("    }\n");
        code.append("}\n");
        
        return code.toString();
    }
    
    /**
     * 生成单个形状的代码
     */
    private String generateShapeCode(GeometryShape shape) {
        StringBuilder code = new StringBuilder();
        
        String name = shape.getName();
        String type = shape.getType();
        
        code.append("            // 创建 ").append(type).append(": ").append(name).append("\n");
        code.append("            model.geom(\"geom1\").create(\"").append(name).append("\", \"");
        code.append(this.mapShapeTypeToCOMSOLType(type)).append("\");\n");
        
        // 设置参数
        for (Map.Entry<String, Double> entry : shape.getParameters().entrySet()) {
            code.append("            model.geom(\"geom1\").feature(\"").append(name);
            code.append("\").set(\"").append(entry.getKey()).append("\", ");
            code.append(entry.getValue()).append(");\n");
        }
        
        // 设置位置
        Position pos = shape.getPosition();
        code.append("            model.geom(\"geom1\").feature(\"").append(name);
        code.append("\").set(\"pos\", new double[]{");
        code.append(pos.getX()).append(", ").append(pos.getY()).append("});\n");
        
        return code.toString();
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

---

## 8. 最佳实践

### 8.1 API 调用模式

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
        model.geom("geom1").feature("rect1").set("size", new double[]{1.0, 0.5});
        model.geom("geom1").feature("rect1").set("pos", new double[]{0.0, 0.0});
        
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
            model.geom("geom1").feature(name).set("size", new double[]{1.0, 0.5});
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
            System.err.println("创建几何失败: " + e.getMessage());
            
            // 清理资源
            if (model.geom().has("geom1")) {
                model.geom().remove("geom1");
            }
            
            throw new ModelException("几何创建失败", e);
        }
    }
}
```

---

## 总结

Java API 调用层的核心设计原则：

1. **分层清晰**：BaseModelBuilder → 具体构建器 → API 映射器
2. **可扩展**：支持新的构建器类型和形状类型
3. **容错性强**：参数验证、错误处理、资源清理
4. **代码生成**：支持生成可执行的 Java 源代码
5. **最佳实践**：遵循 COMSOL API 的推荐使用模式
