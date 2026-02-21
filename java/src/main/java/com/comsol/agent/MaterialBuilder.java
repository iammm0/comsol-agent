package com.comsol.agent;

import com.comsol.model.*;

/**
 * 材料构建器：创建材料、设置属性、分配到几何选择（域）。
 */
public class MaterialBuilder extends BaseModelBuilder {

    public static final String DEFAULT_GROUP = "Def";

    public MaterialBuilder(String modelName) {
        super(modelName);
    }

    /**
     * 基于已有模型链式使用。
     */
    public MaterialBuilder(Model model, String modelName) {
        super(model, modelName);
    }

    /**
     * 创建材料节点。
     */
    public void createMaterial(String materialName) {
        model.materials().create(materialName);
    }

    /**
     * 设置材料属性。
     *
     * @param materialName  材料名称
     * @param groupName    属性组，常用 "Def"
     * @param propertyName  属性名，如 "thermalconductivity"、"density"
     * @param value        值（Number、String、double[] 等，以 API 为准）
     */
    public void setMaterialProperty(String materialName, String groupName, String propertyName, Object value) {
        model.materials(materialName).propertyGroup(groupName).set(propertyName, value);
    }

    /**
     * 使用默认属性组 "Def" 设置材料属性。
     */
    public void setMaterialProperty(String materialName, String propertyName, Object value) {
        setMaterialProperty(materialName, DEFAULT_GROUP, propertyName, value);
    }

    /**
     * 将材料分配到指定域（通过域 ID 数组）。
     *
     * @param materialName 材料名称
     * @param domainIds    域 ID 数组，如 new int[]{1}
     */
    public void assignToDomains(String materialName, int[] domainIds) {
        model.materials(materialName).selection().set(domainIds);
    }

    /**
     * 将材料分配到整个几何（所有域）。
     */
    public void assignToAll(String materialName) {
        model.materials(materialName).selection().all();
    }

    @Override
    public void build() {
        // 材料无需单独 build
    }
}
