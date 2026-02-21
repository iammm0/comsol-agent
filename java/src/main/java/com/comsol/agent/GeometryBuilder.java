package com.comsol.agent;

import com.comsol.model.*;

import java.util.ArrayList;
import java.util.List;

/**
 * 几何构建器：在几何节点下创建 feature（矩形、圆、椭圆、多边形）及布尔运算。
 * 正确用法：model.geom(geomName).create(featureName, type)，model.geom(geomName).feature(featureName).set(...)
 */
public class GeometryBuilder extends BaseModelBuilder {
    private final String geomName;
    private final int dimension;
    private final List<String> featureNames = new ArrayList<>();

    /**
     * 2D 几何（默认）
     */
    public GeometryBuilder(String modelName) {
        this(modelName, 2);
    }

    /**
     * @param modelName 模型名称
     * @param dimension 2 或 3
     */
    public GeometryBuilder(String modelName, int dimension) {
        super(modelName);
        this.geomName = "geom1";
        this.dimension = dimension;
        model.geom().create(geomName, dimension);
    }

    public String getGeomName() {
        return geomName;
    }

    public int getDimension() {
        return dimension;
    }

    /** 在 geom 节点下创建矩形 feature，设置 size、pos，可选旋转 */
    public void addRectangle(String name, double width, double height, double x, double y) {
        addRectangle(name, width, height, x, y, 0.0);
    }

    /** 带旋转角（度）的矩形 */
    public void addRectangle(String name, double width, double height, double x, double y, double rotDeg) {
        model.geom(geomName).create(name, "Rectangle");
        model.geom(geomName).feature(name).set("size", new double[]{width, height});
        model.geom(geomName).feature(name).set("pos", new double[]{x, y});
        if (rotDeg != 0.0) {
            model.geom(geomName).feature(name).set("rot", rotDeg);
        }
        featureNames.add(name);
    }

    public void addCircle(String name, double radius, double x, double y) {
        model.geom(geomName).create(name, "Circle");
        model.geom(geomName).feature(name).set("r", radius);
        model.geom(geomName).feature(name).set("pos", new double[]{x, y});
        featureNames.add(name);
    }

    public void addEllipse(String name, double a, double b, double x, double y) {
        model.geom(geomName).create(name, "Ellipse");
        model.geom(geomName).feature(name).set("a", a);
        model.geom(geomName).feature(name).set("b", b);
        model.geom(geomName).feature(name).set("pos", new double[]{x, y});
        featureNames.add(name);
    }

    /**
     * 多边形：x 与 y 为顶点坐标数组，长度一致。
     */
    public void addPolygon(String name, double[] x, double[] y) {
        if (x == null || y == null || x.length != y.length || x.length < 3) {
            throw new IllegalArgumentException("多边形至少需要 3 个顶点，且 x、y 长度一致");
        }
        model.geom(geomName).create(name, "Polygon");
        model.geom(geomName).feature(name).set("x", x);
        model.geom(geomName).feature(name).set("y", y);
        featureNames.add(name);
    }

    /** 并集：input 为已创建的 feature 名称列表，keep 保留输入对象 */
    public void union(String unionName, String[] input, boolean keep) {
        model.geom(geomName).create(unionName, "Union");
        model.geom(geomName).feature(unionName).set("input", input);
        model.geom(geomName).feature(unionName).set("keep", keep);
        featureNames.add(unionName);
    }

    public void union(String unionName, List<String> input, boolean keep) {
        union(unionName, input.toArray(new String[0]), keep);
    }

    /** 差集 */
    public void difference(String diffName, String[] input, boolean keep) {
        model.geom(geomName).create(diffName, "Difference");
        model.geom(geomName).feature(diffName).set("input", input);
        model.geom(geomName).feature(diffName).set("keep", keep);
        featureNames.add(diffName);
    }

    /** 交集 */
    public void intersection(String interName, String[] input, boolean keep) {
        model.geom(geomName).create(interName, "Intersection");
        model.geom(geomName).feature(interName).set("input", input);
        model.geom(geomName).feature(interName).set("keep", keep);
        featureNames.add(interName);
    }

    @Override
    public void build() {
        try {
            model.geom(geomName).run();
            if (!validateGeometry()) {
                throw new ModelException("几何构建后验证失败");
            }
        } catch (ModelException e) {
            throw e;
        } catch (Exception e) {
            throw new ModelException("构建几何时出错: " + e.getMessage(), e);
        }
    }

    /**
     * 简单验证：几何节点存在且至少有一个域。
     */
    public boolean validateGeometry() {
        try {
            if (!model.geom().has(geomName)) {
                return false;
            }
            return model.geom(geomName).getNDomains() > 0;
        } catch (Exception e) {
            return false;
        }
    }
}
