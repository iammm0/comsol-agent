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

#### 矩形

```java
model.geom().create("rect1", "Rectangle");
model.geom("rect1").set("size", new double[]{width, height});
model.geom("rect1").set("pos", new double[]{x, y});
```

#### 圆形

```java
model.geom().create("circ1", "Circle");
model.geom("circ1").set("r", radius);
model.geom("circ1").set("pos", new double[]{x, y});
```

#### 椭圆

```java
model.geom().create("ell1", "Ellipse");
model.geom("ell1").set("a", a);  // 长轴
model.geom("ell1").set("b", b);  // 短轴
model.geom("ell1").set("pos", new double[]{x, y});
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
            
            // 创建矩形
            model.geom().create("rect1", "Rectangle");
            model.geom("rect1").set("size", new double[]{1.0, 0.5});
            model.geom("rect1").set("pos", new double[]{0.0, 0.0});
            
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

### Q: 如何设置单位？
A: 默认单位为米（m），可通过模型设置更改。

### Q: 如何创建组合几何？
A: 使用布尔运算（Union, Difference, Intersection）。

### Q: 如何添加物理场？
A: 使用 `model.physics().create()` 方法。

## 参考资源

- COMSOL Java API 文档
- COMSOL Multiphysics 用户指南
