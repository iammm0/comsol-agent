package com.comsol.agent;

import com.comsol.model.*;
import com.comsol.model.util.*;

/**
 * COMSOL 模型构建器基类：管理模型生命周期、保存前校验、参数/变量封装。
 */
public abstract class BaseModelBuilder {
    protected Model model;
    protected String modelName;

    public BaseModelBuilder(String modelName) {
        this.modelName = modelName;
        this.model = ModelUtil.create(modelName);
    }

    /**
     * 从已有模型构造（不创建新模型），用于在已有 .mph 上继续操作。
     */
    protected BaseModelBuilder(Model model, String modelName) {
        this.model = model;
        this.modelName = modelName;
    }

    public Model getModel() {
        return model;
    }

    public String getModelName() {
        return modelName;
    }

    public abstract void build();

    /**
     * 保存前校验，子类可重写增强校验。
     */
    protected boolean validateModel() {
        return model != null;
    }

    /**
     * 保存模型到指定路径，校验失败或保存失败时抛出 ModelException。
     */
    public void save(String filePath) throws ModelException {
        if (!validateModel()) {
            throw new ModelException("模型验证失败，无法保存");
        }
        try {
            model.save(filePath);
            System.out.println("模型已保存到: " + filePath);
        } catch (Exception e) {
            throw new ModelException("保存模型失败: " + e.getMessage(), e);
        }
    }

    /**
     * 设置全局参数。value 支持 Number、String 等 COMSOL 接受的类型。
     */
    public void setParam(String name, Object value) {
        model.param().set(name, value);
    }

    /**
     * 设置模型变量。
     */
    public void setVariable(String name, String expression) {
        model.variable().set(name, expression);
    }
}
