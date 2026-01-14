package com.comsol.agent;

import com.comsol.model.*;
import com.comsol.model.util.*;

/**
 * COMSOL 模型构建器基类
 */
public abstract class BaseModelBuilder {
    protected Model model;
    protected String modelName;
    
    public BaseModelBuilder(String modelName) {
        this.modelName = modelName;
        this.model = ModelUtil.create(modelName);
    }
    
    public Model getModel() {
        return model;
    }
    
    public abstract void build();
    
    public void save(String filePath) {
        model.save(filePath);
        System.out.println("模型已保存到: " + filePath);
    }
}
