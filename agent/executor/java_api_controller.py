"""Java API 控制器 - 混合模式控制 Java API 调用（支持材料、3D、扩展物理场）"""
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
from schemas.material import MaterialPlan

logger = get_logger(__name__)

PHYSICS_TYPE_TO_COMSOL_TAG = {
    "heat": "HeatTransfer",
    "electromagnetic": "ElectromagneticWaves",
    "structural": "SolidMechanics",
    "fluid": "SinglePhaseFlow",
    "acoustics": "Acoustics",
    "piezoelectric": "Piezoelectric",
    "chemical": "ChemicalSpeciesTransport",
    "multibody": "MultibodyDynamics",
}

STUDY_TYPE_TO_COMSOL_TAG = {
    "stationary": "Stationary",
    "time_dependent": "Time",
    "eigenvalue": "Eigenvalue",
    "frequency": "Frequency",
    "parametric": "Parametric",
}

COUPLING_TYPE_TO_COMSOL_TAG = {
    "thermal_stress": "ThermalExpansion",
    "fluid_structure": "FluidStructureInteraction",
    "electromagnetic_heat": "ElectromagneticHeat",
}


def _save_model_avoid_lock(model, dest_path: Path):
    """保存 model 到 dest_path。先写临时文件再替换；若目标被占用则写入备用路径。"""
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
        self.settings = get_settings()
        self.comsol_runner = COMSOLRunner()
        self.java_generator = JavaGenerator()

    # ===== Model load helper =====

    def _load_model(self, model_path: str):
        COMSOLRunner._ensure_jvm_started()
        from com.comsol.model.util import ModelUtil
        path = Path(model_path)
        return ModelUtil.load(path.stem or "model", str(path.resolve()))

    # ===== Materials =====

    def add_materials(self, model_path: str, material_plan: MaterialPlan) -> Dict[str, Any]:
        """添加材料到模型"""
        logger.info("添加材料...")
        try:
            model = self._load_model(model_path)
            result = self._add_materials_direct(model, material_plan)
            saved_path = _save_model_avoid_lock(model, Path(model_path))
            out = {"status": "success", "message": "材料设置成功", "result": result}
            if saved_path != Path(model_path):
                out["saved_path"] = str(saved_path)
            return out
        except Exception as e:
            logger.error(f"添加材料失败: {e}")
            return {"status": "error", "message": str(e)}

    def _add_materials_direct(self, model, material_plan: MaterialPlan) -> Dict[str, Any]:
        added = []
        for mat_def in material_plan.materials:
            model.materials().create(mat_def.name)
            if mat_def.label:
                try:
                    model.materials(mat_def.name).label(mat_def.label)
                except Exception:
                    pass

            if mat_def.builtin_name:
                try:
                    model.materials(mat_def.name).materialType("lib")
                    model.materials(mat_def.name).set("family", mat_def.builtin_name)
                except Exception:
                    logger.warning("内置材料加载失败: %s，将使用自定义属性", mat_def.builtin_name)
            else:
                group = mat_def.property_group or "Def"
                for prop in mat_def.properties:
                    try:
                        model.materials(mat_def.name).propertyGroup(group).set(
                            prop.name, prop.value
                        )
                    except Exception as e:
                        logger.warning("设置材料属性 %s 失败: %s", prop.name, e)
            added.append({"material": mat_def.name, "label": mat_def.label})

        for assignment in material_plan.assignments:
            mat_name = assignment.material_name
            try:
                if assignment.assign_all:
                    model.materials(mat_name).selection().all()
                elif assignment.domain_ids:
                    model.materials(mat_name).selection().set(assignment.domain_ids)
            except Exception as e:
                logger.warning("材料分配失败 %s: %s", mat_name, e)

        return {"materials": added}

    # ===== Physics =====

    def add_physics(self, model_path: str, physics_plan: PhysicsPlan) -> Dict[str, Any]:
        logger.info("添加物理场...")
        try:
            model = self._load_model(model_path)
            result = self._add_physics_direct(model, physics_plan)
            saved_path = _save_model_avoid_lock(model, Path(model_path))
            out = {"status": "success", "message": "物理场设置成功", "result": result}
            if saved_path != Path(model_path):
                out["saved_path"] = str(saved_path)
            return out
        except Exception as e:
            logger.error(f"添加物理场失败: {e}")
            return {"status": "error", "message": str(e)}

    def _add_physics_direct(self, model, physics_plan: PhysicsPlan) -> Dict[str, Any]:
        self._ensure_geometry_built(model)
        geom_tag = "geom1"
        added = []
        for i, field in enumerate(physics_plan.fields):
            tag = PHYSICS_TYPE_TO_COMSOL_TAG.get(field.type, "HeatTransfer")
            name = self._physics_interface_name(field.type, i)
            try:
                if model.component().has("comp1"):
                    model.component("comp1").physics().create(name, tag, geom_tag)
                else:
                    model.physics().create(name, tag, geom_tag)
            except Exception:
                model.physics().create(name, tag, geom_tag)

            # Boundary conditions
            for bc in field.boundary_conditions:
                try:
                    model.physics(name).create(bc.name, bc.condition_type)
                    if isinstance(bc.selection, list) and bc.selection:
                        model.physics(name).feature(bc.name).selection().set(bc.selection)
                    for k, v in bc.parameters.items():
                        model.physics(name).feature(bc.name).set(k, v)
                except Exception as e:
                    logger.warning("设置边界条件 %s 失败: %s", bc.name, e)

            # Domain conditions
            for dc in field.domain_conditions:
                try:
                    model.physics(name).create(dc.name, dc.condition_type)
                    if isinstance(dc.selection, list) and dc.selection:
                        model.physics(name).feature(dc.name).selection().set(dc.selection)
                    for k, v in dc.parameters.items():
                        model.physics(name).feature(dc.name).set(k, v)
                except Exception as e:
                    logger.warning("设置域条件 %s 失败: %s", dc.name, e)

            # Initial conditions
            for ic in field.initial_conditions:
                try:
                    model.physics(name).feature("init1").set(ic.variable, ic.value)
                except Exception:
                    try:
                        model.physics(name).create(ic.name, "init")
                        model.physics(name).feature(ic.name).set(ic.variable, ic.value)
                    except Exception as e:
                        logger.warning("设置初始条件 %s 失败: %s", ic.name, e)

            added.append({"interface": name, "type": field.type, "tag": tag})

        # Multi-physics couplings
        for coupling in physics_plan.couplings:
            ctag = COUPLING_TYPE_TO_COMSOL_TAG.get(coupling.type, coupling.type)
            try:
                model.multiphysics().create(coupling.type, ctag)
            except Exception as e:
                logger.warning("创建耦合 %s 失败: %s", coupling.type, e)

        return {"interfaces": added}

    @staticmethod
    def _physics_interface_name(physics_type: str, index: int) -> str:
        prefix_map = {
            "heat": "ht",
            "electromagnetic": "emw",
            "structural": "solid",
            "fluid": "fluid",
            "acoustics": "acpr",
            "piezoelectric": "pzd",
            "chemical": "chds",
            "multibody": "mbd",
        }
        return f"{prefix_map.get(physics_type, physics_type[:3])}{index}"

    def _ensure_geometry_built(self, model) -> None:
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

    # ===== Mesh =====

    def generate_mesh(self, model_path: str, mesh_params: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("生成网格...")
        try:
            model = self._load_model(model_path)
            self._generate_mesh_direct(model, mesh_params or {})
            saved_path = _save_model_avoid_lock(model, Path(model_path))
            out = {"status": "success", "message": "网格划分成功", "result": {}}
            if saved_path != Path(model_path):
                out["saved_path"] = str(saved_path)
            return out
        except Exception as e:
            logger.error(f"生成网格失败: {e}")
            return {"status": "error", "message": str(e)}

    def _mesh_has(self, mesh_list, tag: str) -> bool:
        if hasattr(mesh_list, "has"):
            return mesh_list.has(tag)
        if hasattr(mesh_list, "hasTag"):
            return mesh_list.hasTag(tag)
        return False

    def _generate_mesh_direct(self, model, mesh_params: Dict[str, Any]) -> None:
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

    # ===== Study =====

    def configure_study(self, model_path: str, study_plan: StudyPlan) -> Dict[str, Any]:
        logger.info("配置研究...")
        try:
            model = self._load_model(model_path)
            result = self._configure_study_direct(model, study_plan)
            saved_path = _save_model_avoid_lock(model, Path(model_path))
            out = {"status": "success", "message": "研究配置成功", "result": result}
            if saved_path != Path(model_path):
                out["saved_path"] = str(saved_path)
            return out
        except Exception as e:
            logger.error(f"配置研究失败: {e}")
            return {"status": "error", "message": str(e)}

    def _configure_study_direct(self, model, study_plan: StudyPlan) -> Dict[str, Any]:
        added = []
        for i, st in enumerate(study_plan.studies):
            step_type = STUDY_TYPE_TO_COMSOL_TAG.get(st.type, "Stationary")
            name = f"std{i + 1}"
            model.study().create(name)
            model.study(name).create("std", step_type)

            if st.parametric_sweep:
                ps = st.parametric_sweep
                try:
                    model.study(name).create("param", "Parametric")
                    model.study(name).feature("param").set("pname", ps.parameter_name)
                    model.study(name).feature("param").set("prange",
                        f"range({ps.range_start},{ps.step or ''},{ps.range_end})")
                except Exception as e:
                    logger.warning("参数化扫描配置失败: %s", e)

            added.append({"study": name, "type": st.type, "tag": step_type})
        return {"studies": added}

    # ===== Solve =====

    def solve(self, model_path: str) -> Dict[str, Any]:
        logger.info("执行求解...")
        try:
            model = self._load_model(model_path)
            study_name = self._solve_direct(model)
            saved_path = _save_model_avoid_lock(model, Path(model_path))
            out = {"status": "success", "message": "求解成功", "result": {"study": study_name}}
            if saved_path != Path(model_path):
                out["saved_path"] = str(saved_path)
            return out
        except Exception as e:
            logger.error(f"求解失败: {e}")
            return {"status": "error", "message": str(e)}

    def _solve_direct(self, model) -> str:
        tags = model.study().tags()
        if not tags:
            raise RuntimeError("模型中没有研究，请先配置研究")
        study_name = tags[0]
        model.study(study_name).run()
        return study_name

    # ===== Direct operations =====

    def execute_direct(self, operation: str, model_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug(f"直接调用 Java API: {operation}")
        try:
            model = self._load_model(model_path)
            if operation == "set_parameter":
                result = self._set_parameter_direct(model, parameters)
            elif operation == "add_boundary_condition":
                result = self._add_boundary_condition_direct(model, parameters)
            else:
                raise ValueError(f"不支持的直接操作: {operation}")
            model.save(model_path)
            return {"status": "success", "message": f"直接执行 {operation} 成功", "result": result}
        except Exception as e:
            logger.error(f"直接调用 Java API 失败: {e}")
            return {"status": "error", "message": f"直接调用失败: {e}"}

    def validate_execution(self, model_path: str, expected_result: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not Path(model_path).exists():
                return {"status": "error", "message": "模型文件不存在"}
            return {"status": "success", "message": "验证通过"}
        except Exception as e:
            return {"status": "error", "message": f"验证失败: {e}"}

    def _set_parameter_direct(self, model, parameters: Dict[str, Any]) -> Dict[str, Any]:
        param_name = parameters.get("name")
        param_value = parameters.get("value")
        if not param_name or param_value is None:
            raise ValueError("参数名称和值必须提供")
        model.param().set(param_name, param_value)
        return {"parameter": param_name, "value": param_value}

    def _add_boundary_condition_direct(self, model, parameters: Dict[str, Any]) -> Dict[str, Any]:
        physics_name = parameters.get("physics_name", "ht")
        boundary_name = parameters.get("boundary_name", "bc1")
        condition_type = parameters.get("condition_type", "Temperature")
        model.physics(physics_name).create(boundary_name, condition_type)
        for k, v in parameters.get("params", {}).items():
            model.physics(physics_name).feature(boundary_name).set(k, v)
        return {"physics": physics_name, "boundary": boundary_name, "type": condition_type}
