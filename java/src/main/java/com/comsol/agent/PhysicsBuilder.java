package com.comsol.agent;

import com.comsol.model.*;

import java.util.Map;

/**
 * 物理场构建器：添加物理场接口与边界条件。
 * 可基于已有 Model 构造，便于在 GeometryBuilder 之后链式使用。
 */
public class PhysicsBuilder extends BaseModelBuilder {

    public PhysicsBuilder(String modelName) {
        super(modelName);
    }

    /**
     * 基于已有模型（例如从 GeometryBuilder.getModel() 取得）
     */
    public PhysicsBuilder(Model model, String modelName) {
        super(model, modelName);
    }

    /**
     * 添加物理场接口。
     *
     * @param interfaceName 接口名称，如 "ht"
     * @param physicsType   COMSOL 物理场类型 tag，如 "HeatTransfer"、"GeneralHeatTransfer"、"Acoustic" 等（以官方文档为准）
     */
    public void addPhysics(String interfaceName, String physicsType) {
        model.physics().create(interfaceName, physicsType);
    }

    /**
     * 在指定物理场下创建边界条件并设置参数。
     *
     * @param physicsName   物理场接口名
     * @param boundaryName  边界条件名称
     * @param conditionType 条件类型 tag，如 "Temperature"、"HeatFlux" 等
     * @param params        键值对，会调用 feature(boundaryName).set(key, value)
     */
    public void setBoundaryCondition(
            String physicsName,
            String boundaryName,
            String conditionType,
            Map<String, Object> params) {
        model.physics(physicsName).create(boundaryName, conditionType);
        if (params != null) {
            for (Map.Entry<String, Object> e : params.entrySet()) {
                model.physics(physicsName).feature(boundaryName).set(e.getKey(), e.getValue());
            }
        }
    }

    @Override
    public void build() {
        // 物理场无需单独 run，在 study 求解时生效
    }
}
