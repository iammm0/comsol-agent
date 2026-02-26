package com.comsol.agent;

import com.comsol.model.*;

import java.util.Map;

/**
 * 物理场构建器：添加物理场接口、边界条件、域条件、初始条件、多物理场耦合。
 */
public class PhysicsBuilder extends BaseModelBuilder {

    public PhysicsBuilder(String modelName) {
        super(modelName);
    }

    public PhysicsBuilder(Model model, String modelName) {
        super(model, modelName);
    }

    /** 添加物理场接口 */
    public void addPhysics(String interfaceName, String physicsType) {
        model.physics().create(interfaceName, physicsType);
    }

    /** 在指定几何上添加物理场（3 参数形式，避免 0D） */
    public void addPhysics(String interfaceName, String physicsType, String geomTag) {
        model.physics().create(interfaceName, physicsType, geomTag);
    }

    /** 设置边界条件 */
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

    /** 设置边界条件并指定边界选择 */
    public void setBoundaryCondition(
            String physicsName,
            String boundaryName,
            String conditionType,
            int[] boundaryIds,
            Map<String, Object> params) {
        model.physics(physicsName).create(boundaryName, conditionType);
        if (boundaryIds != null && boundaryIds.length > 0) {
            model.physics(physicsName).feature(boundaryName).selection().set(boundaryIds);
        }
        if (params != null) {
            for (Map.Entry<String, Object> e : params.entrySet()) {
                model.physics(physicsName).feature(boundaryName).set(e.getKey(), e.getValue());
            }
        }
    }

    /** 设置域条件 */
    public void setDomainCondition(
            String physicsName,
            String condName,
            String conditionType,
            int[] domainIds,
            Map<String, Object> params) {
        model.physics(physicsName).create(condName, conditionType);
        if (domainIds != null && domainIds.length > 0) {
            model.physics(physicsName).feature(condName).selection().set(domainIds);
        }
        if (params != null) {
            for (Map.Entry<String, Object> e : params.entrySet()) {
                model.physics(physicsName).feature(condName).set(e.getKey(), e.getValue());
            }
        }
    }

    /** 设置初始条件 */
    public void setInitialCondition(
            String physicsName,
            String condName,
            String variable,
            Object value) {
        try {
            model.physics(physicsName).feature("init1").set(variable, value);
        } catch (Exception e) {
            model.physics(physicsName).create(condName, "init");
            model.physics(physicsName).feature(condName).set(variable, value);
        }
    }

    /** 添加多物理场耦合节点 */
    public void addCoupling(String couplingName, String couplingType) {
        model.multiphysics().create(couplingName, couplingType);
    }

    @Override
    public void build() {
        // 物理场无需单独 run，在 study 求解时生效
    }
}
