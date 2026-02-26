package com.comsol.agent;

import com.comsol.model.*;

/**
 * 材料构建器：创建材料、设置属性、从内置库加载、分配到几何域。
 */
public class MaterialBuilder extends BaseModelBuilder {

    public static final String DEFAULT_GROUP = "Def";

    public MaterialBuilder(String modelName) {
        super(modelName);
    }

    public MaterialBuilder(Model model, String modelName) {
        super(model, modelName);
    }

    /** 创建空材料节点 */
    public void createMaterial(String materialName) {
        model.materials().create(materialName);
    }

    /** 设置材料显示标签 */
    public void setLabel(String materialName, String label) {
        model.materials(materialName).label(label);
    }

    /**
     * 从 COMSOL 内置材料库加载材料。
     * libraryName 为材料库名（如 "Built-In"），materialTag 为材料标识。
     * COMSOL API: model.materials(tag).materialType("lib");
     *             model.materials(tag).set("family", familyName);
     */
    public void loadFromLibrary(String materialName, String libraryMaterialName) {
        model.materials().create(materialName);
        try {
            model.materials(materialName).materialType("lib");
            model.materials(materialName).set("family", libraryMaterialName);
        } catch (Exception e) {
            // Fallback: 部分版本 API 不同，尝试 propertyGroup 方式
            try {
                model.materials(materialName).propertyGroup(DEFAULT_GROUP)
                    .set("family", libraryMaterialName);
            } catch (Exception ignored) {
                throw new ModelException(
                    "从材料库加载失败: " + libraryMaterialName + " - " + e.getMessage(), e);
            }
        }
    }

    /** 设置材料属性（指定属性组） */
    public void setMaterialProperty(String materialName, String groupName,
                                    String propertyName, Object value) {
        model.materials(materialName).propertyGroup(groupName).set(propertyName, value);
    }

    /** 设置材料属性（默认 Def 属性组） */
    public void setMaterialProperty(String materialName, String propertyName, Object value) {
        setMaterialProperty(materialName, DEFAULT_GROUP, propertyName, value);
    }

    /** 批量设置多个属性 */
    public void setMaterialProperties(String materialName, String groupName,
                                      java.util.Map<String, Object> properties) {
        for (java.util.Map.Entry<String, Object> entry : properties.entrySet()) {
            setMaterialProperty(materialName, groupName, entry.getKey(), entry.getValue());
        }
    }

    /** 将材料分配到指定域（域 ID 数组） */
    public void assignToDomains(String materialName, int[] domainIds) {
        model.materials(materialName).selection().set(domainIds);
    }

    /** 将材料分配到所有域 */
    public void assignToAll(String materialName) {
        model.materials(materialName).selection().all();
    }

    @Override
    public void build() {
        // 材料无需单独 build
    }
}
