"""Java API 控制器 - 混合模式控制 Java API 调用（支持材料、3D、扩展物理场）"""
from pathlib import Path
from typing import Dict, Any, Optional, List
import base64
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

# COMSOL 线弹性/固体力学材料属性名：我们 schema 用 poissonsratio/youngsmodulus，API 用 nu/E
MATERIAL_PROPERTY_COMSOL_ALIAS = {
    "poissonsratio": "nu",
    "youngsmodulus": "E",
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

    @staticmethod
    def _materials_api(model):
        """获取材料的 API：COMSOL 部分版本为 model.material()（单数），部分为 model.materials()（复数）。
        若在 component 下，则用 model.component('comp1').material()。不支持时直接抛错并中断。"""
        try:
            if hasattr(model, "materials"):
                return model.materials()
            if hasattr(model, "material"):
                return model.material()
        except Exception as e:
            raise RuntimeError(f"COMSOL 材料 API 不可用: {e}") from e
        try:
            if model.component().has("comp1") and hasattr(model.component("comp1"), "material"):
                return model.component("comp1").material()
        except Exception as e:
            raise RuntimeError(f"COMSOL 材料 API 不可用（component.material）: {e}") from e
        raise RuntimeError(
            "当前 COMSOL 模型对象无 material()/materials() 接口，请确认 COMSOL 版本与 API。"
        )

    def _material_feature(self, model, name: str):
        """获取名为 name 的材料节点。先尝试 model 级，再尝试 component 级。"""
        try:
            if hasattr(model, "materials"):
                return model.materials(name)
            if hasattr(model, "material"):
                return model.material(name)
        except Exception as e:
            raise RuntimeError(f"获取材料节点 '{name}' 失败: {e}") from e
        try:
            if model.component().has("comp1"):
                return model.component("comp1").material(name)
        except Exception as e:
            raise RuntimeError(f"获取材料节点 '{name}' 失败: {e}") from e
        raise RuntimeError("当前 COMSOL 模型不支持材料节点访问")

    # ===== 材料节点：查询 / 删除 / 重命名 / 存在检查 / 更新属性 / 批量删除 =====

    def list_material_tags(self, model_path: str) -> Dict[str, Any]:
        """查询模型中现有材料节点名称列表。API: model.material().tags()。"""
        try:
            model = self._load_model(model_path)
            mat_seq = self._materials_api(model)
            tags = list(mat_seq.tags()) if hasattr(mat_seq, "tags") else []
            return {"status": "success", "tags": tags}
        except Exception as e:
            logger.warning("list_material_tags 失败: %s", e)
            return {"status": "error", "message": str(e), "tags": []}

    def remove_material(self, model_path: str, name: str) -> Dict[str, Any]:
        """删除指定名称的材料节点。API: model.material().remove(\"mat1\")."""
        try:
            model = self._load_model(model_path)
            mat_seq = self._materials_api(model)
            if hasattr(mat_seq, "remove"):
                mat_seq.remove(name)
            else:
                return {"status": "error", "message": "当前 COMSOL 版本不支持 materials().remove()"}
            _save_model_avoid_lock(model, Path(model_path))
            return {"status": "success", "message": f"已删除材料 {name}", "removed": name}
        except Exception as e:
            logger.warning("remove_material 失败: %s", e)
            return {"status": "error", "message": str(e)}

    def has_material(self, model_path: str, name: str) -> Dict[str, Any]:
        """检查材料节点是否存在。API: model.material().has(\"mat1\")."""
        try:
            model = self._load_model(model_path)
            mat_seq = self._materials_api(model)
            if hasattr(mat_seq, "has"):
                exists = mat_seq.has(name)
            else:
                exists = name in (list(mat_seq.tags()) if hasattr(mat_seq, "tags") else [])
            return {"status": "success", "exists": bool(exists)}
        except Exception as e:
            logger.warning("has_material 失败: %s", e)
            return {"status": "error", "message": str(e), "exists": False}

    def rename_material(self, model_path: str, old_name: str, new_name: str) -> Dict[str, Any]:
        """重命名材料节点。COMSOL 部分版本无直接 rename，采用“创建新名 + 复制属性 + 删除旧”实现。"""
        try:
            model = self._load_model(model_path)
            mat_seq = self._materials_api(model)
            if not (hasattr(mat_seq, "has") and mat_seq.has(old_name)):
                return {"status": "error", "message": f"材料节点不存在: {old_name}"}
            if hasattr(mat_seq, "has") and mat_seq.has(new_name):
                return {"status": "error", "message": f"目标名称已存在: {new_name}"}
            feat_old = self._material_feature(model, old_name)
            mat_seq.create(new_name)
            feat_new = self._material_feature(model, new_name)
            try:
                if hasattr(feat_old, "label"):
                    feat_new.label(feat_old.get("label") or new_name)
            except Exception:
                pass
            try:
                if hasattr(feat_old, "getString") and hasattr(feat_new, "set"):
                    for key in ("family", "materialType"):
                        try:
                            v = feat_old.getString(key)
                            if v:
                                feat_new.set(key, v)
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                if hasattr(feat_old, "propertyGroup"):
                    for g in ("Def", "SolidMechanics", "Thermal"):
                        try:
                            pg_old = feat_old.propertyGroup(g)
                            pg_new = feat_new.propertyGroup(g)
                            for prop in ("nu", "E", "density", "thermalconductivity", "specificheat", "youngsmodulus", "poissonsratio"):
                                try:
                                    val = pg_old.get(prop)
                                    if val is not None:
                                        pg_new.set(prop, val)
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                if hasattr(feat_old, "selection") and hasattr(feat_new, "selection"):
                    feat_new.selection().set(feat_old.selection().entities())
            except Exception:
                pass
            if hasattr(mat_seq, "remove"):
                mat_seq.remove(old_name)
            _save_model_avoid_lock(model, Path(model_path))
            return {"status": "success", "message": f"已重命名 {old_name} -> {new_name}", "old_name": old_name, "new_name": new_name}
        except Exception as e:
            logger.warning("rename_material 失败: %s", e)
            return {"status": "error", "message": str(e)}

    def update_material_properties(self, model_path: str, name: str, properties: Dict[str, Any], property_group: str = "Def") -> Dict[str, Any]:
        """更新现有材料属性（不重新创建节点）。优先使用 model.material(name).property(key, value)，否则 propertyGroup().set()。"""
        try:
            model = self._load_model(model_path)
            feat = self._material_feature(model, name)
            for k, v in properties.items():
                key = MATERIAL_PROPERTY_COMSOL_ALIAS.get(k, k)
                done = False
                if hasattr(feat, "property"):
                    try:
                        feat.property(key, v)
                        done = True
                    except Exception:
                        try:
                            feat.property(k, v)
                            done = True
                        except Exception:
                            pass
                if not done:
                    try:
                        group = feat.propertyGroup(property_group)
                        group.set(key, v)
                    except Exception as e1:
                        try:
                            group.set(k, v)
                        except Exception as e2:
                            logger.warning("设置属性 %s 失败: %s", k, e2)
            _save_model_avoid_lock(model, Path(model_path))
            return {"status": "success", "message": f"已更新材料 {name} 属性", "material": name}
        except Exception as e:
            logger.warning("update_material_properties 失败: %s", e)
            return {"status": "error", "message": str(e)}

    def remove_all_materials(self, model_path: str) -> Dict[str, Any]:
        """清除模型中所有材料节点（批量删除）。"""
        try:
            model = self._load_model(model_path)
            mat_seq = self._materials_api(model)
            tags = list(mat_seq.tags()) if hasattr(mat_seq, "tags") else []
            if not hasattr(mat_seq, "remove"):
                return {"status": "error", "message": "当前 COMSOL 版本不支持 materials().remove()", "removed": []}
            for tag in tags:
                try:
                    mat_seq.remove(tag)
                except Exception as e:
                    logger.warning("删除材料 %s 失败: %s", tag, e)
            _save_model_avoid_lock(model, Path(model_path))
            return {"status": "success", "message": f"已删除 {len(tags)} 个材料节点", "removed": tags}
        except Exception as e:
            logger.warning("remove_all_materials 失败: %s", e)
            return {"status": "error", "message": str(e), "removed": []}

    def list_model_tree(self, model_path: str) -> Dict[str, Any]:
        """获取模型树中主要节点信息（材料、物理场、研究、网格、几何）。"""
        out = {"materials": [], "physics": [], "studies": [], "meshes": [], "geometries": []}
        try:
            model = self._load_model(model_path)
            try:
                ms = self._materials_api(model)
                out["materials"] = list(ms.tags()) if hasattr(ms, "tags") else []
            except Exception:
                pass
            try:
                if hasattr(model, "physics"):
                    out["physics"] = list(model.physics().tags()) if hasattr(model.physics(), "tags") else []
            except Exception:
                pass
            try:
                if hasattr(model, "study"):
                    out["studies"] = list(model.study().tags()) if hasattr(model.study(), "tags") else []
            except Exception:
                pass
            try:
                if hasattr(model, "mesh"):
                    out["meshes"] = list(model.mesh().tags()) if hasattr(model.mesh(), "tags") else []
            except Exception:
                pass
            try:
                if model.component().has("comp1") and hasattr(model.component("comp1").geom(), "tags"):
                    out["geometries"] = list(model.component("comp1").geom().tags())
                elif hasattr(model, "geom"):
                    out["geometries"] = list(model.geom().tags()) if hasattr(model.geom(), "tags") else []
            except Exception:
                pass
            return {"status": "success", "tree": out}
        except Exception as e:
            logger.warning("list_model_tree 失败: %s", e)
            return {"status": "error", "message": str(e), "tree": out}

    # ===== 物理场节点：查询 / 删除 / 存在检查 =====

    def list_physics_tags(self, model_path: str) -> Dict[str, Any]:
        """获取所有物理场名称列表。API: model.physics().tags()."""
        try:
            model = self._load_model(model_path)
            tags = list(model.physics().tags()) if hasattr(model.physics(), "tags") else []
            return {"status": "success", "tags": tags}
        except Exception as e:
            return {"status": "error", "message": str(e), "tags": []}

    def remove_physics(self, model_path: str, name: str) -> Dict[str, Any]:
        """删除已存在的物理场节点。API: model.physics().remove(\"ht0\")."""
        try:
            model = self._load_model(model_path)
            if hasattr(model.physics(), "remove"):
                model.physics().remove(name)
            else:
                return {"status": "error", "message": "当前 COMSOL 版本不支持 physics().remove()"}
            _save_model_avoid_lock(model, Path(model_path))
            return {"status": "success", "message": f"已删除物理场 {name}", "removed": name}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def has_physics(self, model_path: str, name: str) -> Dict[str, Any]:
        """检查物理场节点是否存在。API: model.physics().has(\"ht0\")."""
        try:
            model = self._load_model(model_path)
            ph = model.physics()
            exists = ph.has(name) if hasattr(ph, "has") else (name in list(ph.tags()) if hasattr(ph, "tags") else [])
            return {"status": "success", "exists": bool(exists)}
        except Exception as e:
            return {"status": "error", "message": str(e), "exists": False}

    def rename_physics(self, model_path: str, old_name: str, new_name: str) -> Dict[str, Any]:
        """重命名物理场节点。API: model.physics(\"ht0\").name(\"newName\")."""
        try:
            model = self._load_model(model_path)
            ph = model.physics()
            if hasattr(ph, "has") and not ph.has(old_name):
                return {"status": "error", "message": f"物理场节点不存在: {old_name}"}
            if hasattr(ph, "has") and ph.has(new_name):
                return {"status": "error", "message": f"目标名称已存在: {new_name}"}
            feat = model.physics(old_name)
            if hasattr(feat, "name"):
                feat.name(new_name)
            else:
                return {"status": "error", "message": "当前 COMSOL 版本不支持 physics(tag).name(newName)"}
            _save_model_avoid_lock(model, Path(model_path))
            return {"status": "success", "message": f"已重命名物理场 {old_name} -> {new_name}", "old_name": old_name, "new_name": new_name}
        except Exception as e:
            logger.warning("rename_physics 失败: %s", e)
            return {"status": "error", "message": str(e)}

    def clear_physics(self, model_path: str) -> Dict[str, Any]:
        """清除所有物理场节点。API: model.physics().clear()."""
        try:
            model = self._load_model(model_path)
            ph = model.physics()
            if hasattr(ph, "clear"):
                ph.clear()
            else:
                tags = list(ph.tags()) if hasattr(ph, "tags") else []
                if hasattr(ph, "remove"):
                    for tag in tags:
                        try:
                            ph.remove(tag)
                        except Exception as e:
                            logger.warning("删除物理场 %s 失败: %s", tag, e)
                else:
                    return {"status": "error", "message": "当前 COMSOL 版本不支持 physics().clear() 或 remove()"}
            _save_model_avoid_lock(model, Path(model_path))
            return {"status": "success", "message": "已清除所有物理场节点"}
        except Exception as e:
            logger.warning("clear_physics 失败: %s", e)
            return {"status": "error", "message": str(e)}

    def physics_feature_is_active(self, model_path: str, physics_tag: str, feature_tag: str) -> Dict[str, Any]:
        """检查物理场下某特征是否已激活。API: model.physics(\"ht0\").feature(\"temp1\").isActive()."""
        try:
            model = self._load_model(model_path)
            feat = model.physics(physics_tag).feature(feature_tag)
            active = feat.isActive() if hasattr(feat, "isActive") else True
            return {"status": "success", "active": bool(active), "physics": physics_tag, "feature": feature_tag}
        except Exception as e:
            logger.warning("physics_feature_is_active 失败: %s", e)
            return {"status": "error", "message": str(e), "active": False}

    def set_physics_feature_param(self, model_path: str, physics_tag: str, feature_tag: str, key: str, value: Any) -> Dict[str, Any]:
        """修改已存在边界条件/特征参数。API: model.physics(\"ht0\").feature(\"temp1\").set(\"T0\", \"293.15\")."""
        try:
            model = self._load_model(model_path)
            feat = model.physics(physics_tag).feature(feature_tag)
            feat.set(key, value)
            _save_model_avoid_lock(model, Path(model_path))
            return {"status": "success", "message": f"已设置 {physics_tag}.{feature_tag}.{key}", "physics": physics_tag, "feature": feature_tag, "key": key}
        except Exception as e:
            logger.warning("set_physics_feature_param 失败: %s", e)
            return {"status": "error", "message": str(e)}

    # ===== 几何节点：查询 =====

    def list_geometry_tags(self, model_path: str) -> Dict[str, Any]:
        try:
            model = self._load_model(model_path)
            if model.component().has("comp1"):
                tags = list(model.component("comp1").geom().tags()) if hasattr(model.component("comp1").geom(), "tags") else []
            else:
                tags = list(model.geom().tags()) if hasattr(model.geom(), "tags") else []
            return {"status": "success", "tags": tags}
        except Exception as e:
            return {"status": "error", "message": str(e), "tags": []}

    def _find_unused_material_name(self, model, base: str) -> str:
        """在模型中找一个未使用的材料名称，如 mat1 -> mat2, mat3 ..."""
        mat_seq = self._materials_api(model)
        existing = set(mat_seq.tags()) if hasattr(mat_seq, "tags") else set()
        if base not in existing:
            return base
        for i in range(1, 100):
            candidate = f"{base}{i}" if base[-1].isdigit() else f"{base}_{i}"
            if candidate not in existing:
                return candidate
        return f"{base}_new"

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
        mat_seq = self._materials_api(model)
        added = []
        name_map = {}  # 请求名 -> 实际使用名（智能创建时可能不同）
        for mat_def in material_plan.materials:
            actual_name = self._find_unused_material_name(model, mat_def.name)
            name_map[mat_def.name] = actual_name
            mat_seq.create(actual_name)
            feat = self._material_feature(model, actual_name)
            if mat_def.label:
                try:
                    feat.label(mat_def.label)
                except Exception:
                    pass

            if mat_def.builtin_name:
                try:
                    feat.materialType("lib")
                    feat.set("family", mat_def.builtin_name)
                except Exception:
                    logger.warning("内置材料加载失败: %s，将使用自定义属性", mat_def.builtin_name)
            else:
                group = mat_def.property_group or "Def"
                for prop in mat_def.properties:
                    name_to_set = MATERIAL_PROPERTY_COMSOL_ALIAS.get(prop.name, prop.name)
                    try:
                        feat.propertyGroup(group).set(name_to_set, prop.value)
                    except Exception as e1:
                        try:
                            feat.propertyGroup(group).set(prop.name, prop.value)
                        except Exception as e2:
                            logger.warning("设置材料属性 %s（或 %s）失败: %s", prop.name, name_to_set, e2)
            added.append({"material": actual_name, "label": mat_def.label, "requested_name": mat_def.name})

        for assignment in material_plan.assignments:
            mat_name = name_map.get(assignment.material_name, assignment.material_name)
            try:
                feat = self._material_feature(model, mat_name)
                if assignment.assign_all:
                    feat.selection().all()
                elif assignment.domain_ids:
                    feat.selection().set(assignment.domain_ids)
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

    # ===== 模型预览（导出几何/结果图为 PNG，供桌面端显示）=====

    def export_model_preview(self, model_path: str, width: int = 640, height: int = 480) -> Dict[str, Any]:
        """加载 .mph 模型，导出几何或结果图为 PNG，返回 base64 编码供前端显示。"""
        path = Path(model_path)
        if not path.exists():
            return {"status": "error", "message": "模型文件不存在", "image_base64": None}
        try:
            model = self._load_model(model_path)
            fd, out_path = tempfile.mkstemp(suffix=".png", prefix="comsol_preview_")
            try:
                import os
                os.close(fd)
            except Exception:
                pass
            out_path = Path(out_path)
            try:
                geom = self._geom_for_export(model)
                if geom is not None:
                    img = geom.image()
                    img.set("pngfilename", str(out_path.resolve()))
                    img.set("width", str(width))
                    img.set("height", str(height))
                    img.export()
                else:
                    raise RuntimeError("无几何节点")
            except Exception as e1:
                logger.warning("几何导出失败: %s", e1)
                if out_path.exists():
                    out_path.unlink(missing_ok=True)
                return {"status": "error", "message": f"预览导出失败: {e1}", "image_base64": None}
            if not out_path.exists():
                return {"status": "error", "message": "未生成预览图", "image_base64": None}
            data = out_path.read_bytes()
            out_path.unlink(missing_ok=True)
            b64 = base64.b64encode(data).decode("ascii")
            return {"status": "success", "message": "预览已生成", "image_base64": b64}
        except Exception as e:
            logger.exception("export_model_preview 失败")
            return {"status": "error", "message": str(e), "image_base64": None}

    def _geom_for_export(self, model):
        """获取用于导出的几何对象。"""
        try:
            if model.component().has("comp1") and model.component("comp1").geom().has("geom1"):
                return model.component("comp1").geom("geom1")
        except Exception:
            pass
        try:
            if model.geom().has("geom1"):
                return model.geom("geom1")
        except Exception:
            pass
        return None

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
