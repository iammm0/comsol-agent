"""COMSOL API 运行器"""
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import jpype
import jpype.imports

from agent.utils.config import get_settings
from agent.utils.logger import get_logger
from schemas.geometry import GeometryPlan, GeometryShape

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class COMSOLRunner:
    """COMSOL Java API 运行器"""
    
    _jvm_started = False
    
    def __init__(self):
        """初始化 COMSOL 运行器"""
        self._ensure_jvm_started()
        self.settings = get_settings()
    
    @classmethod
    def _ensure_jvm_started(cls):
        """确保 JVM 已启动"""
        if cls._jvm_started:
            return
        
        logger.info("启动 JVM...")
        
        settings = get_settings()
        
        # 验证配置
        if not settings.comsol_jar_path:
            raise RuntimeError("COMSOL JAR 路径未配置")
        
        if not Path(settings.comsol_jar_path).exists():
            raise RuntimeError(f"COMSOL JAR 文件不存在: {settings.comsol_jar_path}")
        
        # 启动 JVM
        jvm_args = [f"-Djava.class.path={settings.comsol_jar_path}"]
        
        if settings.java_home:
            jvm_args.append(f"-Djava.home={settings.java_home}")
        
        try:
            jpype.startJVM(jpype.getDefaultJVMPath(), *jvm_args)
            
            # 导入 COMSOL 类
            from com.comsol.model import Model
            from com.comsol.model.util import ModelUtil
            
            logger.info("JVM 启动成功，COMSOL API 已加载")
            cls._jvm_started = True
        except Exception as e:
            logger.error(f"加载 COMSOL API 失败: {e}")
            raise RuntimeError(f"无法加载 COMSOL API: {e}") from e
    
    def create_model(self, model_name: str):
        """创建 COMSOL 模型"""
        from com.comsol.model.util import ModelUtil
        
        logger.info(f"创建模型: {model_name}")
        return ModelUtil.create(model_name)
    
    def create_rectangle(self, model, shape: GeometryShape, name: Optional[str] = None) -> None:
        """在模型中创建矩形"""
        name = name or shape.name or "rect1"
        width = shape.parameters["width"]
        height = shape.parameters["height"]
        x = shape.position.get("x", 0.0)
        y = shape.position.get("y", 0.0)
        
        logger.debug(f"创建矩形 {name}: 宽={width}, 高={height}, 位置=({x}, {y})")
        
        geom = model.geom()
        rect = geom.create(name, "Rectangle")
        rect.set("size", [width, height])
        rect.set("pos", [x, y])
    
    def create_circle(self, model, shape: GeometryShape, name: Optional[str] = None) -> None:
        """在模型中创建圆形"""
        name = name or shape.name or "circ1"
        radius = shape.parameters["radius"]
        x = shape.position.get("x", 0.0)
        y = shape.position.get("y", 0.0)
        
        logger.debug(f"创建圆形 {name}: 半径={radius}, 位置=({x}, {y})")
        
        geom = model.geom()
        circle = geom.create(name, "Circle")
        circle.set("r", radius)
        circle.set("pos", [x, y])
    
    def create_ellipse(self, model, shape: GeometryShape, name: Optional[str] = None) -> None:
        """在模型中创建椭圆"""
        name = name or shape.name or "ell1"
        a = shape.parameters["a"]
        b = shape.parameters["b"]
        x = shape.position.get("x", 0.0)
        y = shape.position.get("y", 0.0)
        
        logger.debug(f"创建椭圆 {name}: 长轴={a}, 短轴={b}, 位置=({x}, {y})")
        
        geom = model.geom()
        ellipse = geom.create(name, "Ellipse")
        ellipse.set("a", a)
        ellipse.set("b", b)
        ellipse.set("pos", [x, y])
    
    def create_shape(self, model, shape: GeometryShape, index: int = 1) -> None:
        """根据形状类型创建对应的几何形状"""
        if shape.type == "rectangle":
            self.create_rectangle(model, shape)
        elif shape.type == "circle":
            self.create_circle(model, shape)
        elif shape.type == "ellipse":
            self.create_ellipse(model, shape)
        else:
            raise ValueError(f"不支持的形状类型: {shape.type}")
    
    def build_geometry(self, model, geom_name: str = "geom1") -> None:
        """构建几何"""
        logger.info(f"构建几何: {geom_name}")
        geom = model.geom(geom_name)
        geom.run()
    
    def save_model(self, model, output_path: Path) -> Path:
        """保存模型到文件"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"保存模型到: {output_path}")
        model.save(str(output_path))
        
        if output_path.exists():
            logger.info(f"模型已成功保存: {output_path}")
            return output_path
        else:
            raise RuntimeError(f"模型保存失败: {output_path}")
    
    def create_model_from_plan(self, plan: GeometryPlan, output_filename: Optional[str] = None) -> Path:
        """根据 GeometryPlan 创建并保存 COMSOL 模型"""
        logger.info(f"根据计划创建模型: {plan.model_name}")
        
        # 创建模型
        model = self.create_model(plan.model_name)
        
        # 创建几何节点（2D）
        model.geom().create("geom1", 2)
        
        # 创建所有形状
        for i, shape in enumerate(plan.shapes, 1):
            if not shape.name:
                shape.name = f"{shape.type}{i}"
            self.create_shape(model, shape, i)
        
        # 构建几何
        self.build_geometry(model, "geom1")
        
        # 确定输出路径
        if output_filename is None:
            output_filename = f"{plan.model_name}.mph"
        
        output_path = Path(self.settings.model_output_dir) / output_filename
        
        # 保存模型
        return self.save_model(model, output_path)
    
    @classmethod
    def shutdown_jvm(cls):
        """关闭 JVM"""
        if cls._jvm_started:
            jpype.shutdownJVM()
            cls._jvm_started = False
            logger.info("JVM 已关闭")
