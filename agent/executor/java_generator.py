"""Java 代码生成器"""
import json
from pathlib import Path
from typing import Optional

from agent.utils.prompt_loader import prompt_loader
from agent.utils.logger import get_logger
from agent.utils.config import get_settings
from schemas.geometry import GeometryPlan, GeometryShape

logger = get_logger(__name__)


class JavaGenerator:
    """Java 代码生成器"""
    
    def __init__(self):
        """初始化 Java 代码生成器"""
        self.settings = get_settings()
    
    def generate_from_plan(self, plan: GeometryPlan, output_filename: Optional[str] = None) -> str:
        """
        根据 GeometryPlan 生成 Java 代码
        
        Args:
            plan: 几何建模计划
            output_filename: 输出文件名
        
        Returns:
            Java 代码字符串
        """
        logger.info(f"生成 Java 代码，模型: {plan.model_name}")
        
        # 确定输出路径
        if output_filename is None:
            output_filename = f"{plan.model_name}.mph"
        
        output_path = str(Path(self.settings.model_output_dir) / output_filename)
        
        # 使用模板生成代码
        plan_json = json.dumps(plan.to_dict(), ensure_ascii=False, indent=2)
        
        java_code = prompt_loader.format(
            "executor",
            "java_codegen",
            plan_json=plan_json
        )
        
        # 如果使用模板生成失败，使用直接代码生成
        if not java_code or "import" not in java_code:
            java_code = self._generate_direct_code(plan, output_path)
        
        logger.debug(f"生成的 Java 代码长度: {len(java_code)} 字符")
        return java_code
    
    def _generate_direct_code(self, plan: GeometryPlan, output_path: str) -> str:
        """直接生成 Java 代码（备用方法）"""
        imports = """
import com.comsol.model.*;
import com.comsol.model.util.*;

"""
        
        main_start = f"""
public class COMSOLModelGenerator {{
    public static void main(String[] args) {{
        try {{
            // 创建模型
            Model model = ModelUtil.create("{plan.model_name}");
            
            // 创建几何节点（2D）
            model.geom().create("geom1", 2);
"""
        
        # 生成形状代码
        shapes_code = ""
        for i, shape in enumerate(plan.shapes, 1):
            shapes_code += self._generate_shape_code(shape, i)
        
        build_geom = """
            // 构建几何
            model.geom("geom1").run();
"""
        
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
        
        return imports + main_start + shapes_code + build_geom + save_model
    
    def _generate_shape_code(self, shape: GeometryShape, index: int) -> str:
        """生成单个形状的 Java 代码"""
        name = shape.name or f"{shape.type}{index}"
        x = shape.position.get("x", 0.0)
        y = shape.position.get("y", 0.0)
        
        if shape.type == "rectangle":
            width = shape.parameters["width"]
            height = shape.parameters["height"]
            return f"""
            // 创建矩形: {name}
            model.geom().create("{name}", "Rectangle");
            model.geom("{name}").set("size", new double[]{{{width}, {height}}});
            model.geom("{name}").set("pos", new double[]{{{x}, {y}}});
"""
        
        elif shape.type == "circle":
            radius = shape.parameters["radius"]
            return f"""
            // 创建圆形: {name}
            model.geom().create("{name}", "Circle");
            model.geom("{name}").set("r", {radius});
            model.geom("{name}").set("pos", new double[]{{{x}, {y}}});
"""
        
        elif shape.type == "ellipse":
            a = shape.parameters["a"]
            b = shape.parameters["b"]
            return f"""
            // 创建椭圆: {name}
            model.geom().create("{name}", "Ellipse");
            model.geom("{name}").set("a", {a});
            model.geom("{name}").set("b", {b});
            model.geom("{name}").set("pos", new double[]{{{x}, {y}}});
"""
        
        else:
            raise ValueError(f"不支持的形状类型: {shape.type}")
