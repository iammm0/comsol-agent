# COMSOL Java API 使用笔记

## 基本使用

### 1. 创建模型

```java
import com.comsol.model.*;
import com.comsol.model.util.*;

Model model = ModelUtil.create("model_name");
```

### 2. 创建几何节点

```java
// 2D 几何
model.geom().create("geom1", 2);

// 3D 几何
model.geom().create("geom1", 3);
```

### 3. 创建几何形状

**重要**：矩形、圆、椭圆等是**几何节点（geom1）下的 feature**，不是单独的几何节点。应使用 `model.geom(geomName).create(featureName, type)` 创建，再用 `model.geom(geomName).feature(featureName).set(...)` 设置属性。

#### 矩形

```java
model.geom("geom1").create("rect1", "Rectangle");
model.geom("geom1").feature("rect1").set("size", new double[]{width, height});
model.geom("geom1").feature("rect1").set("pos", new double[]{x, y});
```

#### 圆形

```java
model.geom("geom1").create("circ1", "Circle");
model.geom("geom1").feature("circ1").set("r", radius);
model.geom("geom1").feature("circ1").set("pos", new double[]{x, y});
```

#### 椭圆

```java
model.geom("geom1").create("ell1", "Ellipse");
model.geom("geom1").feature("ell1").set("a", a);  // 长轴
model.geom("geom1").feature("ell1").set("b", b);  // 短轴
model.geom("geom1").feature("ell1").set("pos", new double[]{x, y});
```

### 4. 构建几何

```java
model.geom("geom1").run();
```

### 5. 保存模型

```java
model.save("output.mph");
```

## 完整示例

```java
import com.comsol.model.*;
import com.comsol.model.util.*;

public class Example {
    public static void main(String[] args) {
        try {
            // 创建模型
            Model model = ModelUtil.create("my_model");
            
            // 创建 2D 几何节点
            model.geom().create("geom1", 2);
            
            // 创建矩形（在 geom1 下创建 feature）
            model.geom("geom1").create("rect1", "Rectangle");
            model.geom("geom1").feature("rect1").set("size", new double[]{1.0, 0.5});
            model.geom("geom1").feature("rect1").set("pos", new double[]{0.0, 0.0});
            
            // 构建几何
            model.geom("geom1").run();
            
            // 保存模型
            model.save("output.mph");
            
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```

## 常见问题

### Q: `UnsatisfiedLinkError: FlLicense.initWS0(...)` 从哪来？

**来源**：COMSOL 的 Java API 里部分功能（如许可证初始化 `FlLicense.initWS0`）通过 **JNI 调用本地库**（.dll / .so）实现。JVM 只在 **java.library.path** 和系统 PATH 里查找这些库；若未配置 COMSOL 的本地库目录，就会报 `UnsatisfiedLinkError`。

**处理**：

1. 为 JVM 设置 **java.library.path**，指向 COMSOL 安装目录下的 **bin 子目录**（如 Windows 下 `Multiphysics\bin\win64`）。本仓库在启动 JVM 时会根据 `COMSOL_JAR_PATH` 自动推导该路径（如 `.../plugins` → `.../bin/win64`）；若推导不对，可在 `.env` 中设置 **COMSOL_NATIVE_PATH** 为实际 bin 目录。
2. 或将 COMSOL 的 bin 目录加入系统 **PATH**，使 JVM 能加载到对应 .dll/.so。
3. 确认 COMSOL 许可证在无头/批处理模式下可用（若仅桌面授权，可能仍需在 GUI 环境下运行）。

### Q: 如何设置单位？
A: 默认单位为米（m），可通过模型设置更改。

### Q: 如何创建组合几何？
A: 使用布尔运算（Union, Difference, Intersection）。

### Q: 如何添加物理场？
A: 使用 `model.physics().create()` 方法。

### Q: 如何配置研究与求解？
A: 研究配置与求解通过 `model.study().create(studyName, studyType)` 创建研究、`model.study(studyName).run()` 运行求解，与 Java 层 StudyBuilder 一致。

## 本仓库 Java 封装层

`java/src/main/java/com/comsol/agent/` 下提供可直接调用的 Builder 与工具类，与上述 API 对应：

| 类 | 用途 |
|----|------|
| `GeometryBuilder` | 几何：矩形/圆/椭圆/多边形、布尔运算（Union/Difference/Intersection）、2D/3D |
| `PhysicsBuilder` | 物理场接口、边界条件 |
| `MaterialBuilder` | 材料创建、属性设置、分配到域 |
| `MeshBuilder` | 网格创建、Size（hmax/hauto 等）、run |
| `StudyBuilder` | 研究创建、求解器、runStudy |
| `ComsolModelHelper` | 静态方法：create/load/save、setParam、setVariable |
| `BaseModelBuilder` | 基类：getModel、save、setParam、setVariable、validateModel |
| `ModelException` | 模型相关异常 |

详见 [java/API_ARCHITECTURE_PSEUDOCODE.md](../java/API_ARCHITECTURE_PSEUDOCODE.md) 与 [java/README.md](../java/README.md)。

## 参考资源

- **官方文档链接**：完整地址与版本说明见 [comsol-api-links.md](comsol-api-links.md)。
- COMSOL Multiphysics 用户指南
