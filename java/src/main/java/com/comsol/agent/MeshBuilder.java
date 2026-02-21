package com.comsol.agent;

import com.comsol.model.*;

import java.util.Map;

/**
 * 网格构建器：创建网格、设置尺寸（Size）、运行网格生成。
 * COMSOL 6.x 中网格在 component 下，默认使用 "comp1"。
 */
public class MeshBuilder extends BaseModelBuilder {

    public static final String DEFAULT_COMPONENT = "comp1";
    public static final String DEFAULT_SIZE_TAG = "size";

    private final String compName;

    public MeshBuilder(String modelName) {
        this(modelName, DEFAULT_COMPONENT);
    }

    /**
     * @param compName 组件名，网格在其下创建
     */
    public MeshBuilder(String modelName, String compName) {
        super(modelName);
        this.compName = compName;
    }

    public MeshBuilder(Model model, String modelName) {
        this(model, modelName, DEFAULT_COMPONENT);
    }

    public MeshBuilder(Model model, String modelName, String compName) {
        super(model, modelName);
        this.compName = compName;
    }

    /**
     * 创建网格节点。
     *
     * @param meshName 网格名称，如 "mesh1"
     */
    public void createMesh(String meshName) {
        model.component(compName).mesh().create(meshName);
    }

    /**
     * 设置全局尺寸：在 mesh 下创建或使用 "size" 特征，设置 hmax/hmin/hauto 等。
     *
     * @param meshName  网格名称
     * @param sizeName  尺寸特征名，通常 "size"
     * @param params    属性键值对，如 "hmax" -> 0.02, "hauto" -> 5
     */
    public void setMeshSize(String meshName, String sizeName, Map<String, Object> params) {
        if (!model.component(compName).mesh().has(meshName)) {
            createMesh(meshName);
        }
        try {
            model.component(compName).mesh(meshName).create(sizeName, "Size");
        } catch (Exception e) {
            // 已存在则忽略
        }
        if (params != null) {
            for (Map.Entry<String, Object> e : params.entrySet()) {
                model.component(compName).mesh(meshName).feature(sizeName).set(e.getKey(), e.getValue());
            }
        }
    }

    /**
     * 使用自动尺寸：hauto 1–9（5 为 Normal，1 最密，9 最粗）。
     */
    public void setMeshSizeAuto(String meshName, int hauto) {
        setMeshSize(meshName, DEFAULT_SIZE_TAG, Map.of("hauto", hauto));
    }

    /**
     * 运行网格生成。
     */
    public void runMesh(String meshName) {
        model.component(compName).mesh(meshName).run();
    }

    @Override
    public void build() {
        runMesh("mesh1");
    }
}
