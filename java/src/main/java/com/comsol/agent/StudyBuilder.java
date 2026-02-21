package com.comsol.agent;

import com.comsol.model.*;

import java.util.Map;

/**
 * 研究/求解构建器：创建研究、配置求解器、运行求解。
 */
public class StudyBuilder extends BaseModelBuilder {

    public StudyBuilder(String modelName) {
        super(modelName);
    }

    public StudyBuilder(Model model, String modelName) {
        super(model, modelName);
    }

    /**
     * 创建研究。
     *
     * @param studyName 研究名称，如 "std1"
     * @param studyType 研究类型 tag，如 "Stationary"、"Time"、"Eigenvalue" 等（以官方文档为准）
     */
    public void createStudy(String studyName, String studyType) {
        model.study().create(studyName, studyType);
    }

    /**
     * 在研究下创建求解器特征并设置参数。
     *
     * @param studyName  研究名称
     * @param solverName 求解器特征名
     * @param solverType 求解器类型 tag
     * @param params     可选参数键值对
     */
    public void createSolver(String studyName, String solverName, String solverType, Map<String, Object> params) {
        model.study(studyName).create(solverName, solverType);
        if (params != null) {
            for (Map.Entry<String, Object> e : params.entrySet()) {
                model.study(studyName).feature(solverName).set(e.getKey(), e.getValue());
            }
        }
    }

    /**
     * 运行研究（包含求解）。
     */
    public void runStudy(String studyName) {
        model.study(studyName).run();
    }

    @Override
    public void build() {
        // 默认无操作，由调用方显式 runStudy
    }
}
