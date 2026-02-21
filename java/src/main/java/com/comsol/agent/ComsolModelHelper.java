package com.comsol.agent;

import com.comsol.model.*;
import com.comsol.model.util.*;

/**
 * 轻量模型工具类：不绑定构建流程，提供 create/load/save/param/variable 静态方法。
 */
public final class ComsolModelHelper {

    private ComsolModelHelper() {}

    public static Model create(String modelName) {
        return ModelUtil.create(modelName);
    }

    /**
     * 从 .mph 文件加载模型（与 java_api_controller 中 load 一致）。
     */
    public static Model load(String filePath) {
        return ModelUtil.load(filePath);
    }

    public static void save(Model model, String filePath) throws ModelException {
        if (model == null) {
            throw new ModelException("模型为 null，无法保存");
        }
        try {
            model.save(filePath);
        } catch (Exception e) {
            throw new ModelException("保存模型失败: " + e.getMessage(), e);
        }
    }

    public static void setParam(Model model, String name, Object value) {
        model.param().set(name, value);
    }

    public static void setVariable(Model model, String name, String expression) {
        model.variable().set(name, expression);
    }
}
