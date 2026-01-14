package com.comsol.agent;

/**
 * COMSOL Agent 主类
 * 示例用法
 */
public class Main {
    public static void main(String[] args) {
        try {
            // 创建几何构建器
            GeometryBuilder builder = new GeometryBuilder("test_model");
            
            // 添加几何形状
            builder.addRectangle("rect1", 1.0, 0.5, 0.0, 0.0);
            builder.addCircle("circ1", 0.3, 1.5, 0.0);
            
            // 构建几何
            builder.build();
            
            // 保存模型
            builder.save("output.mph");
            
        } catch (Exception e) {
            System.err.println("错误: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
    }
}
