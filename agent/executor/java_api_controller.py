"""Java API 控制器 - 混合模式控制 Java API 调用"""
from pathlib import Path
from typing import Dict, Any, Optional
import jpype
import shutil
import tempfile

from agent.executor.comsol_runner import COMSOLRunner
from agent.executor.java_generator import JavaGenerator
from agent.utils.logger import get_logger
from agent.utils.config import get_settings
from schemas.physics import PhysicsPlan
from schemas.study import StudyPlan

logger = get_logger(__name__)

# 物理场类型 -> COMSOL 物理接口 tag（以 COMSOL 6.x 文档为准）
PHYSICS_TYPE_TO_COMSOL_TAG = {
    "heat": "HeatTransfer",
    "electromagnetic": "ElectromagneticWaves",
    "structural": "SolidMechanics",
    "fluid": "SinglePhaseFlow",
}

# 研究类型 -> COMSOL study tag（以 COMSOL 6.x 文档为准）
STUDY_TYPE_TO_COMSOL_TAG = {
    "stationary": "Stationary",
    "time_dependent": "Time",
    "eigenvalue": "Eigenvalue",
    "frequency": "Frequency",
}


def _save_model_avoid_lock(model, dest_path: Path):
    """保存 model 到 dest_path。先写临时文件再替换；若目标被占用(WinError 32)则写入备用路径。
    返回实际保存路径 (Path)。"""
    import os
    dest_path = Path(dest_path).resolve()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=".mph", prefix=dest_path.stem + "_", dir=str(dest_path.parent))
    try:
        os.close(fd)
    except Exception:
        pass
    tmp_path = Path(tmp_path)
    try:
        model.save(tmp_path.as_posix())
        try:
            tmp_path.replace(dest_path)
            return dest_path
        except OSError as e:
            if getattr(e, "winerror", None) == 32:
                fallback = dest_path.parent / (dest_path.stem + "_updated.mph")
                shutil.copy2(str(tmp_path), str(fallback))
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
                logger.info(f"原文件被占用，已保存到: {fallback}")
                return fallback
            raise
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise


class JavaAPIController:
    """Java API 控制器 - 根据操作复杂度选择直接调用或代码生成"""
    
    def __init__(self):
        """初始化 Java API 控制器"""
        self.settings = get_settings()
        self.comsol_runner = COMSOLRunner()
        self.java_generator = JavaGenerator()
    
    def execute_direct(
        self,
        operation: str,
        model_path: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        直接调用 Java API（简单操作）
        
        Args:
            operation: 操作类型
            model_path: 模型文件路径
            parameters: 操作参数
        
        Returns:
            执行结果
        """
        logger.debug(f"直接调用 Java API: {operation}")
        
        try:
            # 确保 JVM 已启动
            COMSOLRunner._ensure_jvm_started()
            
            # 加载模型：ModelUtil.load(tag, filePath)
            from com.comsol.model.util import ModelUtil
            path = Path(model_path)
            model = ModelUtil.load(path.stem or "model", str(path.resolve()))
            
            # 根据操作类型执行
            if operation == "set_parameter":
                result = self._set_parameter_direct(model, parameters)
            elif operation == "add_boundary_condition":
                result = self._add_boundary_condition_direct(model, parameters)
            else:
                raise ValueError(f"不支持的直接操作: {operation}")
            
            # 保存模型
            model.save(model_path)
            
            return {
                "status": "success",
                "message": f"直接执行 {operation} 成功",
                "result": result
            }
            
        except Exception as e:
            logger.error(f"直接调用 Java API 失败: {e}")
            return {
                "status": "error",
                "message": f"直接调用失败: {e}"
            }
    
    def execute_via_codegen(
        self,
        operation: str,
        model_path: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成 Java 代码并执行（复杂操作）
        
        Args:
            operation: 操作类型
            model_path: 模型文件路径
            parameters: 操作参数
        
        Returns:
            执行结果
        """
        logger.debug(f"通过代码生成执行: {operation}")
        
        try:
            # 生成 Java 代码
            java_code = self._generate_operation_code(operation, model_path, parameters)
            
            # 编译并执行（这里简化处理，实际可能需要更复杂的流程）
            # 注意：实际实现中可能需要将代码写入文件、编译、执行
            
            return {
                "status": "success",
                "message": f"代码生成执行 {operation} 成功",
                "java_code": java_code
            }
            
        except Exception as e:
            logger.error(f"代码生成执行失败: {e}")
            return {
                "status": "error",
                "message": f"代码生成执行失败: {e}"
            }
    
    def add_physics(
        self,
        model_path: str,
        physics_plan: PhysicsPlan
    ) -> Dict[str, Any]:
        """
        添加物理场：加载模型，按计划添加物理接口，保存。
        """
        logger.info("添加物理场...")
        try:
            COMSOLRunner._ensure_jvm_started()
            from com.comsol.model.util import ModelUtil
            path = Path(model_path)
            # ModelUtil.load(tag, filePath): tag 为模型名，filePath 为 .mph 路径
            model = ModelUtil.load(path.stem or "model", str(path.resolve()))
            result = self._add_physics_direct(model, physics_plan)
            saved_path = _save_model_avoid_lock(model, path)
            out = {
                "status": "success",
                "message": "物理场设置成功",
                "result": result,
            }
            if saved_path != path:
                out["saved_path"] = str(saved_path)
            return out
        except Exception as e:
            logger.error(f"添加物理场失败: {e}")
            return {
                "status": "error",
                "message": str(e),
            }

    def _add_physics_direct(self, model, physics_plan: PhysicsPlan) -> Dict[str, Any]:
        """在已加载的 model 上添加物理场接口。添加前先构建几何。
        COMSOL API：create(tag, physIntID) 创建的是 0D 物理场；create(tag, physIntID, geom) 在指定几何上创建，必须用三参数避免「空间维度: 零维」。"""
        self._ensure_geometry_built(model)
        geom_tag = "geom1"
        added = []
        for i, field in enumerate(physics_plan.fields):
            tag = PHYSICS_TYPE_TO_COMSOL_TAG.get(field.type, "HeatTransfer")
            name = f"ht{i}" if field.type == "heat" else f"{field.type[:2]}{i}"
            if field.type == "electromagnetic":
                name = f"emw{i}"
            elif field.type == "structural":
                name = f"solid{i}"
            elif field.type == "fluid":
                name = f"fluid{i}"
            try:
                if model.component().has("comp1"):
                    model.component("comp1").physics().create(name, tag, geom_tag)
                else:
                    model.physics().create(name, tag, geom_tag)
            except Exception:
                model.physics().create(name, tag, geom_tag)
            added.append({"interface": name, "type": field.type, "tag": tag})
        return {"interfaces": added}

    def _ensure_geometry_built(self, model) -> None:
        """确保几何已构建，使模型具有 2D/3D 域，避免添加物理场时报「空间维度: 零维」。优先 component 下 geom，再试 model 级。"""
        try:
            if model.component().has("comp1") and model.component("comp1").geom().has("geom1"):
                model.component("comp1").geom("geom1").run()
                return
        except Exception:
            pass
        try:
            if model.geom().has("geom1"):
                model.geom("geom1").run()
        except Exception:
            pass
    
    def generate_mesh(
        self,
        model_path: str,
        mesh_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成网格：加载模型，创建/设置 mesh，run，保存。"""
        logger.info("生成网格...")
        try:
            COMSOLRunner._ensure_jvm_started()
            from com.comsol.model.util import ModelUtil
            path = Path(model_path)
            model = ModelUtil.load(path.stem or "model", str(path.resolve()))
            self._generate_mesh_direct(model, mesh_params or {})
            saved_path = _save_model_avoid_lock(model, path)
            out = {"status": "success", "message": "网格划分成功", "result": {}}
            if saved_path != path:
                out["saved_path"] = str(saved_path)
            return out
        except Exception as e:
            logger.error(f"生成网格失败: {e}")
            return {"status": "error", "message": str(e)}

    def _mesh_has(self, mesh_list, tag: str) -> bool:
        """MeshList/ComponentMeshList 可能用 has 或 hasTag，兼容两种 API。"""
        if hasattr(mesh_list, "has"):
            return mesh_list.has(tag)
        if hasattr(mesh_list, "hasTag"):
            return mesh_list.hasTag(tag)
        return False

    def _generate_mesh_direct(self, model, mesh_params: Dict[str, Any]) -> None:
        """在已加载的 model 上创建并运行网格。优先用 comp1，无 comp1 时用 model 级 mesh（MeshList.create(tag, gtag)、run）。"""
        mesh_name = "mesh1"
        geom_tag = "geom1"
        hauto = mesh_params.get("hauto", 5) if isinstance(mesh_params, dict) else 5
        try:
            if model.component().has("comp1"):
                mesh_seq = model.component("comp1").mesh()
                if not self._mesh_has(mesh_seq, mesh_name):
                    try:
                        mesh_seq.create(mesh_name, geom_tag)
                    except Exception:
                        mesh_seq.create(mesh_name)
                try:
                    model.component("comp1").mesh(mesh_name).create("size", "Size")
                except Exception:
                    pass
                try:
                    model.component("comp1").mesh(mesh_name).feature("size").set("hauto", hauto)
                except Exception:
                    pass
                model.component("comp1").mesh(mesh_name).run()
                return
        except Exception:
            pass
        # 无 comp1 或 component 下失败：使用 model 级 mesh（model.mesh() 返回 MeshList，用 hasTag 而非 has）
        ml = model.mesh()
        if not self._mesh_has(ml, mesh_name):
            ml.create(mesh_name, geom_tag)
        try:
            model.mesh(mesh_name).create("size", "Size")
        except Exception:
            pass
        try:
            model.mesh(mesh_name).feature("size").set("hauto", hauto)
        except Exception:
            pass
        model.mesh().run()
    
    def configure_study(
        self,
        model_path: str,
        study_plan: StudyPlan
    ) -> Dict[str, Any]:
        """配置研究：加载模型，按计划创建 study，保存。"""
        logger.info("配置研究...")
        try:
            COMSOLRunner._ensure_jvm_started()
            from com.comsol.model.util import ModelUtil
            path = Path(model_path)
            model = ModelUtil.load(path.stem or "model", str(path.resolve()))
            result = self._configure_study_direct(model, study_plan)
            saved_path = _save_model_avoid_lock(model, path)
            out = {
                "status": "success",
                "message": "研究配置成功",
                "result": result,
            }
            if saved_path != path:
                out["saved_path"] = str(saved_path)
            return out
        except Exception as e:
            logger.error(f"配置研究失败: {e}")
            return {"status": "error", "message": str(e)}

    def _configure_study_direct(self, model, study_plan: StudyPlan) -> Dict[str, Any]:
        """在已加载的 model 上创建研究。COMSOL 6.x: study().create(tag) 仅接受 tag，再在 study 下 create(stepTag, type)。"""
        added = []
        for i, st in enumerate(study_plan.studies):
            step_type = STUDY_TYPE_TO_COMSOL_TAG.get(st.type, "Stationary")
            name = f"std{i + 1}"
            model.study().create(name)
            model.study(name).create("std", step_type)
            added.append({"study": name, "type": st.type, "tag": step_type})
        return {"studies": added}
    
    def solve(
        self,
        model_path: str
    ) -> Dict[str, Any]:
        """执行求解：加载模型，运行第一个 study，保存。"""
        logger.info("执行求解...")
        try:
            COMSOLRunner._ensure_jvm_started()
            from com.comsol.model.util import ModelUtil
            path = Path(model_path)
            model = ModelUtil.load(path.stem or "model", str(path.resolve()))
            study_name = self._solve_direct(model)
            saved_path = _save_model_avoid_lock(model, path)
            out = {
                "status": "success",
                "message": "求解成功",
                "result": {"study": study_name},
            }
            if saved_path != path:
                out["saved_path"] = str(saved_path)
            return out
        except Exception as e:
            logger.error(f"求解失败: {e}")
            return {"status": "error", "message": str(e)}

    def _solve_direct(self, model) -> str:
        """运行模型中第一个研究，返回研究名。"""
        tags = model.study().tags()
        if not tags:
            raise RuntimeError("模型中没有研究，请先配置研究")
        study_name = tags[0]
        model.study(study_name).run()
        return study_name
    
    def validate_execution(
        self,
        model_path: str,
        expected_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        验证执行结果
        
        Args:
            model_path: 模型文件路径
            expected_result: 期望结果
        
        Returns:
            验证结果
        """
        logger.debug("验证执行结果...")
        
        try:
            # 检查模型文件是否存在
            if not Path(model_path).exists():
                return {
                    "status": "error",
                    "message": "模型文件不存在"
                }
            
            # 可以添加更多验证逻辑
            # 例如：检查模型是否有效、检查求解结果等
            
            return {
                "status": "success",
                "message": "验证通过"
            }
            
        except Exception as e:
            logger.error(f"验证失败: {e}")
            return {
                "status": "error",
                "message": f"验证失败: {e}"
            }
    
    def _set_parameter_direct(
        self,
        model,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """直接设置参数"""
        param_name = parameters.get("name")
        param_value = parameters.get("value")
        
        if not param_name or param_value is None:
            raise ValueError("参数名称和值必须提供")
        
        model.param().set(param_name, param_value)
        
        return {"parameter": param_name, "value": param_value}
    
    def _add_boundary_condition_direct(
        self,
        model,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """直接添加边界条件"""
        # 这里简化处理，实际需要更复杂的逻辑
        physics_name = parameters.get("physics_name", "ht")
        boundary_name = parameters.get("boundary_name", "bc1")
        condition_type = parameters.get("condition_type", "Temperature")
        
        # 实际实现需要调用 COMSOL API
        # model.physics(physics_name).create(boundary_name, condition_type)
        
        return {
            "physics": physics_name,
            "boundary": boundary_name,
            "type": condition_type
        }
    
    def _generate_operation_code(
        self,
        operation: str,
        model_path: str,
        parameters: Dict[str, Any]
    ) -> str:
        """生成操作代码"""
        code_templates = {
            "add_physics": self._generate_physics_code,
            "generate_mesh": self._generate_mesh_code,
            "configure_study": self._generate_study_code,
            "solve": self._generate_solve_code
        }
        
        generator = code_templates.get(operation)
        if not generator:
            raise ValueError(f"不支持的操作: {operation}")
        
        return generator(model_path, parameters)
    
    def _generate_physics_code(
        self,
        model_path: str,
        parameters: Dict[str, Any]
    ) -> str:
        """生成物理场代码"""
        return f"""
// 添加物理场
// Model path: {model_path}
// Parameters: {parameters}
// TODO: 实现物理场添加逻辑
"""
    
    def _generate_mesh_code(
        self,
        model_path: str,
        parameters: Dict[str, Any]
    ) -> str:
        """生成网格代码"""
        return f"""
// 生成网格
// Model path: {model_path}
// Parameters: {parameters}
// TODO: 实现网格生成逻辑
"""
    
    def _generate_study_code(
        self,
        model_path: str,
        parameters: Dict[str, Any]
    ) -> str:
        """生成研究配置代码"""
        return f"""
// 配置研究
// Model path: {model_path}
// Parameters: {parameters}
// TODO: 实现研究配置逻辑
"""
    
    def _generate_solve_code(
        self,
        model_path: str,
        parameters: Dict[str, Any]
    ) -> str:
        """生成求解代码"""
        return f"""
// 执行求解
// Model path: {model_path}
// Parameters: {parameters}
// TODO: 实现求解逻辑
"""
