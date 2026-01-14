"""COMSOL Java API 封装"""
import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import jpype
import jpype.imports
from loguru import logger

from src.comsol.config import comsol_config
from src.planner.schema import GeometryPlan, GeometryShape

if TYPE_CHECKING:
    from com.comsol.model import Model


class COMSOLWrapper:
    """COMSOL Java API 封装类"""
    
    _jvm_started = False
    
    def __init__(self):
        """初始化 COMSOL 包装器"""
        self._ensure_jvm_started()
    
    @classmethod
    def _ensure_jvm_started(cls):
        """确保 JVM 已启动"""
        if cls._jvm_started:
            return
        
        logger.info("启动 JVM...")
        
        # 验证配置
        is_valid, error = comsol_config.validate()
        if not is_valid:
            raise RuntimeError(f"COMSOL 配置无效: {error}")
        
        # 设置 Java 路径
        if comsol_config.java_home:
            java_path = comsol_config.get_java_path()
            if java_path:
                jpype.startJVM(
                    jpype.getDefaultJVMPath(),
                    f"-Djava.class.path={comsol_config.jar_path}",
                    f"-Djava.home={comsol_config.java_home}"
                )
            else:
                jpype.startJVM(
                    jpype.getDefaultJVMPath(),
                    f"-Djava.class.path={comsol_config.jar_path}"
                )
        else:
            jpype.startJVM(
                jpype.getDefaultJVMPath(),
                f"-Djava.class.path={comsol_config.jar_path}"
            )
        
        # 导入 COMSOL 类
        try:
            from com.comsol.model import Model
            from com.comsol.model.util import ModelUtil
            logger.info("JVM 启动成功，COMSOL API 已加载")
            cls._jvm_started = True
        except Exception as e:
            logger.error(f"加载 COMSOL API 失败: {e}")
            raise RuntimeError(f"无法加载 COMSOL API: {e}") from e
    
    def create_model(self, model_name: str):
        """
        创建 COMSOL 模型
        
        Args:
            model_name: 模型名称
        
        Returns:
            COMSOL Model 对象
        """
        from com.comsol.model import Model
        from com.comsol.model.util import ModelUtil
        
        logger.info(f"创建模型: {model_name}")
        model = ModelUtil.create(model_name)
        return model
    
    def create_rectangle(self, model, shape: GeometryShape, name: Optional[str] = None) -> None:
        """
        在模型中创建矩形
        
        Args:
            model: COMSOL 模型对象
            shape: 几何形状定义
            name: 形状名称
        """
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
        """
        在模型中创建圆形
        
        Args:
            model: COMSOL 模型对象
            shape: 几何形状定义
            name: 形状名称
        """
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
        """
        在模型中创建椭圆
        
        Args:
            model: COMSOL 模型对象
            shape: 几何形状定义
            name: 形状名称
        """
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
        """
        根据形状类型创建对应的几何形状
        
        Args:
            model: COMSOL 模型对象
            shape: 几何形状定义
            index: 形状索引（用于生成默认名称）
        """
        if shape.type == "rectangle":
            self.create_rectangle(model, shape)
        elif shape.type == "circle":
            self.create_circle(model, shape)
        elif shape.type == "ellipse":
            self.create_ellipse(model, shape)
        else:
            raise ValueError(f"不支持的形状类型: {shape.type}")
    
    def build_geometry(self, model, geom_name: str = "geom1") -> None:
        """
        构建几何
        
        Args:
            model: COMSOL 模型对象
            geom_name: 几何节点名称
        """
        logger.info(f"构建几何: {geom_name}")
        geom = model.geom(geom_name)
        geom.run()
    
    def save_model(self, model, output_path: Path) -> Path:
        """
        保存模型到文件
        
        Args:
            model: COMSOL 模型对象
            output_path: 输出文件路径
        
        Returns:
            保存的文件路径
        """
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
        """
        根据 GeometryPlan 创建并保存 COMSOL 模型
        
        Args:
            plan: 几何建模计划
            output_filename: 输出文件名（不含路径），如果为 None 则使用 plan.model_name
        
        Returns:
            保存的模型文件路径
        """
        logger.info(f"根据计划创建模型: {plan.model_name}")
        
        # 创建模型
        model = self.create_model(plan.model_name)
        
        # 创建几何节点（2D）
        geom = model.geom().create("geom1", 2)
        
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
        
        output_path = comsol_config.model_output_dir / output_filename
        
        # 保存模型
        return self.save_model(model, output_path)
    
    @classmethod
    def shutdown_jvm(cls):
        """关闭 JVM（通常不需要手动调用）"""
        if cls._jvm_started:
            jpype.shutdownJVM()
            cls._jvm_started = False
            logger.info("JVM 已关闭")
