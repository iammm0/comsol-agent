"""COMSOL Java API 代码模板"""
from typing import Dict, Any

from src.planner.schema import GeometryShape


class COMSOLTemplate:
    """COMSOL Java API 代码模板生成器"""
    
    @staticmethod
    def generate_rectangle_code(shape: GeometryShape, index: int) -> str:
        """
        生成矩形的 Java 代码
        
        Args:
            shape: 几何形状对象
            index: 形状索引
        
        Returns:
            Java 代码字符串
        """
        name = shape.name or f"rect{index}"
        width = shape.parameters["width"]
        height = shape.parameters["height"]
        x = shape.position.get("x", 0.0)
        y = shape.position.get("y", 0.0)
        
        code = f"""
        // 创建矩形: {name}
        model.geom().create("{name}", "Rectangle");
        model.geom("{name}").set("size", new double[]{{{width}, {height}}});
        model.geom("{name}").set("pos", new double[]{{{x}, {y}}});
"""
        return code
    
    @staticmethod
    def generate_circle_code(shape: GeometryShape, index: int) -> str:
        """
        生成圆形的 Java 代码
        
        Args:
            shape: 几何形状对象
            index: 形状索引
        
        Returns:
            Java 代码字符串
        """
        name = shape.name or f"circ{index}"
        radius = shape.parameters["radius"]
        x = shape.position.get("x", 0.0)
        y = shape.position.get("y", 0.0)
        
        code = f"""
        // 创建圆形: {name}
        model.geom().create("{name}", "Circle");
        model.geom("{name}").set("r", {radius});
        model.geom("{name}").set("pos", new double[]{{{x}, {y}}});
"""
        return code
    
    @staticmethod
    def generate_ellipse_code(shape: GeometryShape, index: int) -> str:
        """
        生成椭圆的 Java 代码
        
        Args:
            shape: 几何形状对象
            index: 形状索引
        
        Returns:
            Java 代码字符串
        """
        name = shape.name or f"ell{index}"
        a = shape.parameters["a"]  # 长轴
        b = shape.parameters["b"]  # 短轴
        x = shape.position.get("x", 0.0)
        y = shape.position.get("y", 0.0)
        
        code = f"""
        // 创建椭圆: {name}
        model.geom().create("{name}", "Ellipse");
        model.geom("{name}").set("a", {a});
        model.geom("{name}").set("b", {b});
        model.geom("{name}").set("pos", new double[]{{{x}, {y}}});
"""
        return code
    
    @staticmethod
    def generate_shape_code(shape: GeometryShape, index: int) -> str:
        """
        根据形状类型生成对应的 Java 代码
        
        Args:
            shape: 几何形状对象
            index: 形状索引
        
        Returns:
            Java 代码字符串
        """
        if shape.type == "rectangle":
            return COMSOLTemplate.generate_rectangle_code(shape, index)
        elif shape.type == "circle":
            return COMSOLTemplate.generate_circle_code(shape, index)
        elif shape.type == "ellipse":
            return COMSOLTemplate.generate_ellipse_code(shape, index)
        else:
            raise ValueError(f"不支持的形状类型: {shape.type}")
    
    @staticmethod
    def generate_full_code(shapes: list, model_name: str, output_path: str) -> str:
        """
        生成完整的 COMSOL Java API 代码
        
        Args:
            shapes: 几何形状列表
            model_name: 模型名称
            output_path: 输出文件路径
        
        Returns:
            完整的 Java 代码字符串
        """
        # 导入语句
        imports = """
import com.comsol.model.*;
import com.comsol.model.util.*;
"""
        
        # 主方法开始
        main_start = f"""
public class COMSOLModelGenerator {{
    public static void main(String[] args) {{
        try {{
            // 创建模型
            Model model = ModelUtil.create("{model_name}");
            
            // 创建几何节点
            model.geom().create("geom1", 2);  // 2D 几何
"""
        
        # 生成形状代码
        shapes_code = ""
        for i, shape in enumerate(shapes, 1):
            shapes_code += COMSOLTemplate.generate_shape_code(shape, i)
        
        # 构建几何
        build_geom = """
            // 构建几何
            model.geom("geom1").run();
"""
        
        # 保存模型
        save_model = f"""
            // 保存模型
            model.save("{output_path}");
            System.out.println("模型已保存到: {output_path}");
            
        }} catch (Exception e) {{
            System.err.println("错误: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }}
    }}
}}
"""
        
        # 组合完整代码
        full_code = imports + main_start + shapes_code + build_geom + save_model
        return full_code
