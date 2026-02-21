"""COMSOL API 运行器"""
import os
import platform
import shutil
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import jpype
import jpype.imports

from agent.utils.config import get_settings, get_project_root
from agent.utils.java_runtime import ensure_bundled_java
from agent.utils.logger import get_logger
from schemas.geometry import GeometryPlan, GeometryShape

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def _resolve_comsol_native_path(settings) -> Optional[str]:
    """
    解析 COMSOL 本地库目录，供 -Djava.library.path 与 PATH 使用。
    官方要求：将 <安装目录>/lib/win64（或 glnxa64/darwin64）加入 PATH；com.comsol.nativeutil 等依赖 lib 下的 csjni.dll、csnutil.dll。
    返回多个路径时用分号（Windows）或冒号分隔，同时包含 lib 与 bin 以便 JVM 找到所有 JNI 库。
    """
    if getattr(settings, "comsol_native_path", None) and Path(settings.comsol_native_path).exists():
        return str(Path(settings.comsol_native_path).resolve())
    jar_path = Path(settings.comsol_jar_path)
    if not jar_path.exists():
        return None
    if jar_path.is_dir():
        base = jar_path.parent  # Multiphysics
    else:
        base = jar_path.parent.parent
    sep = ";" if os.name == "nt" else ":"
    if platform.system() == "Windows":
        lib_dir = base / "lib" / "win64"
        bin_dir = base / "bin" / "win64"
        license_dir = base / "license" / "win64"
        license_lmadmin = base / "license" / "win64" / "lmadmin"
    elif platform.system() == "Darwin":
        lib_dir = base / "lib" / "darwin64"
        bin_dir = base / "bin" / "darwin64"
        license_dir = license_lmadmin = None
    else:
        lib_dir = base / "lib" / "glnxa64"
        bin_dir = base / "bin" / "glnxa64"
        license_dir = license_lmadmin = None
    parts = []
    if lib_dir.exists():
        parts.append(str(lib_dir.resolve()))
    if bin_dir.exists() and str(bin_dir.resolve()) not in parts:
        parts.append(str(bin_dir.resolve()))
    # FlLicense (FlexNet) JNI 可能依赖 license/win64 下的 DLL
    if license_dir and license_dir.exists() and str(license_dir.resolve()) not in parts:
        parts.append(str(license_dir.resolve()))
    if license_lmadmin and license_lmadmin.exists() and str(license_lmadmin.resolve()) not in parts:
        parts.append(str(license_lmadmin.resolve()))
    if not parts:
        return None
    return sep.join(parts)


def _get_comsol_jvm_path(settings) -> Optional[str]:
    """若存在 COMSOL 自带的 JRE，返回 jvm.dll 路径，便于与官方 batch 一致加载本地库。"""
    jar_path = Path(settings.comsol_jar_path)
    if not jar_path.exists():
        return None
    base = jar_path.parent if jar_path.is_dir() else jar_path.parent.parent
    if platform.system() == "Windows":
        jvm_dll = base / "java" / "win64" / "jre" / "bin" / "server" / "jvm.dll"
    elif platform.system() == "Darwin":
        jvm_dll = base / "java" / "darwin64" / "jre" / "lib" / "server" / "libjvm.dylib"
    else:
        jvm_dll = base / "java" / "glnxa64" / "jre" / "lib" / "amd64" / "server" / "libjvm.so"
    if jvm_dll.exists():
        return str(jvm_dll.resolve())
    return None


def _build_classpath(jar_path: str) -> str:
    """根据 COMSOL_JAR_PATH 构建 Java classpath。支持目录（自动包含所有 *.jar）或单个 jar 文件。"""
    path = Path(jar_path)
    if not path.exists():
        raise RuntimeError(f"COMSOL JAR 路径不存在: {jar_path}")
    sep = ";" if os.name == "nt" else ":"
    if path.is_dir():
        jars = sorted(path.glob("*.jar"))
        if not jars:
            raise RuntimeError(f"目录中未找到任何 .jar 文件: {jar_path}")
        return sep.join(str(p) for p in jars)
    return str(path)


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
            raise RuntimeError("COMSOL JAR 路径未配置，请设置 COMSOL_JAR_PATH")
        
        classpath = _build_classpath(settings.comsol_jar_path)
        # 优先使用 COMSOL 自带 JRE，与官方 batch 一致，便于正确加载 FlLicense 等本地库
        comsol_jvm = _get_comsol_jvm_path(settings)
        if comsol_jvm:
            java_home = str(Path(comsol_jvm).resolve().parent.parent.parent)  # jre
            logger.info("使用 COMSOL 自带 JRE: %s", java_home)
        else:
            java_home = ensure_bundled_java()
        os.environ["JAVA_HOME"] = java_home
        jvm_args = [f"-Djava.class.path={classpath}", f"-Djava.home={java_home}"]

        # COMSOL 需加载本地 JNI 库（如 FlLicense.initWS0），须设置 java.library.path 并将目录加入 PATH
        native_path = _resolve_comsol_native_path(settings)
        path_sep = ";" if os.name == "nt" else ":"
        if native_path:
            jvm_args.append(f"-Djava.library.path={native_path}")
            old_path = os.environ.get("PATH", "")
            if native_path not in old_path:
                os.environ["PATH"] = native_path + path_sep + old_path
            logger.info("COMSOL 本地库路径: %s", native_path)
        # 使用 COMSOL JRE 时将其 bin 加入 PATH，便于加载 jvm 依赖的 DLL
        if comsol_jvm:
            jre_bin = Path(comsol_jvm).resolve().parent.parent   # jre/bin
            if jre_bin.exists():
                prepend = str(jre_bin) + path_sep + os.environ.get("PATH", "")
                os.environ["PATH"] = prepend

        try:
            jvm_path = comsol_jvm if comsol_jvm else jpype.getDefaultJVMPath()
            jpype.startJVM(jvm_path, *jvm_args)
            
            # 导入 COMSOL 类并初始化独立客户端（必须，否则 FlLicense.initWS0 等会报 UnsatisfiedLinkError）
            from com.comsol.model import Model
            from com.comsol.model.util import ModelUtil
            ModelUtil.initStandalone(False)
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
        
        geom = self._geom(model, "geom1")
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
        
        geom = self._geom(model, "geom1")
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
        
        geom = self._geom(model, "geom1")
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
    
    def _geom(self, model, geom_name: str = "geom1"):
        """取几何序列：优先 component 下，兼容 model 级。"""
        try:
            if model.component().has("comp1") and model.component("comp1").geom().has(geom_name):
                return model.component("comp1").geom(geom_name)
        except Exception:
            pass
        return model.geom(geom_name)

    def build_geometry(self, model, geom_name: str = "geom1") -> None:
        """构建几何"""
        logger.info(f"构建几何: {geom_name}")
        geom = self._geom(model, geom_name)
        geom.run()
    
    def save_model(self, model, output_path: Path) -> Path:
        """保存模型到文件，并同步保存到 comsol-agent 项目目录下的 models 文件夹。"""
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # 使用绝对路径 + 正斜杠，避免 Java 在 Windows 下误解析反斜杠或内部使用带空格的模型名
        save_path_str = output_path.as_posix()
        logger.info(f"保存模型到: {output_path}")
        model.save(save_path_str)

        if not output_path.exists():
            raise RuntimeError(f"模型保存失败: {output_path}")

        # 同步保存到当前项目根目录下的 models（不含虚拟环境内的路径）
        project_models = get_project_root() / "models"
        project_copy = project_models / output_path.name
        if project_copy.resolve() != output_path.resolve():
            project_models.mkdir(parents=True, exist_ok=True)
            shutil.copy2(output_path, project_copy)
            logger.info(f"已同步保存到项目目录: {project_copy}")

        logger.info(f"模型已成功保存: {output_path}")
        return output_path
    
    def create_model_from_plan(self, plan: GeometryPlan, output_filename: Optional[str] = None) -> Path:
        """根据 GeometryPlan 创建并保存 COMSOL 模型"""
        # 模型名去掉空格，避免 COMSOL 内部使用带空格文件名导致保存失败或锁定
        safe_name = (plan.model_name or "model").replace(" ", "_").strip() or "model"
        logger.info(f"根据计划创建模型: {safe_name}")
        
        # 创建模型
        model = self.create_model(safe_name)
        # 创建组件与几何（COMSOL 6.x 要求物理/网格在 component 下，否则会报「空间维度: 零维」）
        model.component().create("comp1")
        model.component("comp1").geom().create("geom1", 2)
        
        # 创建所有形状
        for i, shape in enumerate(plan.shapes, 1):
            if not shape.name:
                shape.name = f"{shape.type}{i}"
            self.create_shape(model, shape, i)
        
        # 构建几何
        self.build_geometry(model, "geom1")
        
        # 确定输出路径
        if output_filename is None:
            output_filename = f"{safe_name}.mph"
        
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
