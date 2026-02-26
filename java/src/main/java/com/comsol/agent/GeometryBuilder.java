package com.comsol.agent;

import com.comsol.model.*;

import java.util.ArrayList;
import java.util.List;

/**
 * 几何构建器：在几何节点下创建 2D/3D feature 及布尔运算、拉伸、旋转等操作。
 */
public class GeometryBuilder extends BaseModelBuilder {
    private final String geomName;
    private final int dimension;
    private final List<String> featureNames = new ArrayList<>();

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

    // ===== 2D Primitives =====

    public void addRectangle(String name, double width, double height, double x, double y) {
        addRectangle(name, width, height, x, y, 0.0);
    }

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

    public void addPolygon(String name, double[] x, double[] y) {
        if (x == null || y == null || x.length != y.length || x.length < 3) {
            throw new IllegalArgumentException("多边形至少需要 3 个顶点，且 x、y 长度一致");
        }
        model.geom(geomName).create(name, "Polygon");
        model.geom(geomName).feature(name).set("x", x);
        model.geom(geomName).feature(name).set("y", y);
        featureNames.add(name);
    }

    // ===== 3D Primitives =====

    /** 长方体 (Block) — 仅 3D */
    public void addBlock(String name, double width, double height, double depth,
                         double x, double y, double z) {
        ensureDimension(3, "Block");
        model.geom(geomName).create(name, "Block");
        model.geom(geomName).feature(name).set("size", new double[]{width, depth, height});
        model.geom(geomName).feature(name).set("pos", new double[]{x, y, z});
        featureNames.add(name);
    }

    /** 圆柱 (Cylinder) — 仅 3D */
    public void addCylinder(String name, double radius, double height,
                            double x, double y, double z) {
        ensureDimension(3, "Cylinder");
        model.geom(geomName).create(name, "Cylinder");
        model.geom(geomName).feature(name).set("r", radius);
        model.geom(geomName).feature(name).set("h", height);
        model.geom(geomName).feature(name).set("pos", new double[]{x, y, z});
        featureNames.add(name);
    }

    /** 球 (Sphere) — 仅 3D */
    public void addSphere(String name, double radius,
                          double x, double y, double z) {
        ensureDimension(3, "Sphere");
        model.geom(geomName).create(name, "Sphere");
        model.geom(geomName).feature(name).set("r", radius);
        model.geom(geomName).feature(name).set("pos", new double[]{x, y, z});
        featureNames.add(name);
    }

    /** 锥体 (Cone) — 仅 3D */
    public void addCone(String name, double rBottom, double rTop, double height,
                        double x, double y, double z) {
        ensureDimension(3, "Cone");
        model.geom(geomName).create(name, "Cone");
        model.geom(geomName).feature(name).set("r", rBottom);
        model.geom(geomName).feature(name).set("rtop", rTop);
        model.geom(geomName).feature(name).set("h", height);
        model.geom(geomName).feature(name).set("pos", new double[]{x, y, z});
        featureNames.add(name);
    }

    /** 圆环 (Torus) — 仅 3D */
    public void addTorus(String name, double rMajor, double rMinor,
                         double x, double y, double z) {
        ensureDimension(3, "Torus");
        model.geom(geomName).create(name, "Torus");
        model.geom(geomName).feature(name).set("rmaj", rMajor);
        model.geom(geomName).feature(name).set("rmin", rMinor);
        model.geom(geomName).feature(name).set("pos", new double[]{x, y, z});
        featureNames.add(name);
    }

    // ===== Operations =====

    /** 拉伸 (Extrude) — 将 2D 截面拉伸为 3D；distance 为拉伸高度 */
    public void extrude(String name, String[] inputFeatures, double distance) {
        ensureDimension(3, "Extrude");
        model.geom(geomName).create(name, "Extrude");
        model.geom(geomName).feature(name).set("input", inputFeatures);
        model.geom(geomName).feature(name).set("distance", distance);
        featureNames.add(name);
    }

    /** 旋转 (Revolve) — 将 2D 截面绕轴旋转；angleDeg 为旋转角度（度） */
    public void revolve(String name, String[] inputFeatures, double angleDeg) {
        ensureDimension(3, "Revolve");
        model.geom(geomName).create(name, "Revolve");
        model.geom(geomName).feature(name).set("input", inputFeatures);
        model.geom(geomName).feature(name).set("angle1", angleDeg);
        featureNames.add(name);
    }

    /** 工作面 (WorkPlane) — 在指定 z 偏移处创建 2D 工作面 */
    public void addWorkPlane(String name, double zOffset) {
        ensureDimension(3, "WorkPlane");
        model.geom(geomName).create(name, "WorkPlane");
        model.geom(geomName).feature(name).set("quickz", zOffset);
        featureNames.add(name);
    }

    // ===== Boolean Operations =====

    public void union(String unionName, String[] input, boolean keep) {
        model.geom(geomName).create(unionName, "Union");
        model.geom(geomName).feature(unionName).set("input", input);
        model.geom(geomName).feature(unionName).set("keep", keep);
        featureNames.add(unionName);
    }

    public void union(String unionName, List<String> input, boolean keep) {
        union(unionName, input.toArray(new String[0]), keep);
    }

    public void difference(String diffName, String[] input, boolean keep) {
        model.geom(geomName).create(diffName, "Difference");
        model.geom(geomName).feature(diffName).set("input", input);
        model.geom(geomName).feature(diffName).set("keep", keep);
        featureNames.add(diffName);
    }

    public void intersection(String interName, String[] input, boolean keep) {
        model.geom(geomName).create(interName, "Intersection");
        model.geom(geomName).feature(interName).set("input", input);
        model.geom(geomName).feature(interName).set("keep", keep);
        featureNames.add(interName);
    }

    // ===== Build & Validate =====

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

    // ===== Helpers =====

    private void ensureDimension(int required, String featureType) {
        if (dimension != required) {
            throw new ModelException(
                featureType + " 需要 " + required + "D 几何，当前维度为 " + dimension + "D");
        }
    }
}
