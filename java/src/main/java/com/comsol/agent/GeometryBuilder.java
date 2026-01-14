package com.comsol.agent;

import com.comsol.model.*;

/**
 * 几何构建器
 */
public class GeometryBuilder extends BaseModelBuilder {
    private String geomName;
    
    public GeometryBuilder(String modelName) {
        super(modelName);
        this.geomName = "geom1";
        // 创建 2D 几何节点
        model.geom().create(geomName, 2);
    }
    
    public void addRectangle(String name, double width, double height, double x, double y) {
        model.geom().create(name, "Rectangle");
        model.geom(name).set("size", new double[]{width, height});
        model.geom(name).set("pos", new double[]{x, y});
    }
    
    public void addCircle(String name, double radius, double x, double y) {
        model.geom().create(name, "Circle");
        model.geom(name).set("r", radius);
        model.geom(name).set("pos", new double[]{x, y});
    }
    
    public void addEllipse(String name, double a, double b, double x, double y) {
        model.geom().create(name, "Ellipse");
        model.geom(name).set("a", a);
        model.geom(name).set("b", b);
        model.geom(name).set("pos", new double[]{x, y});
    }
    
    @Override
    public void build() {
        // 构建几何
        model.geom(geomName).run();
    }
}
