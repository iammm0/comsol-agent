package com.comsol.agent;

/**
 * COMSOL 模型相关异常（验证失败、保存失败、API 调用错误等）
 */
public class ModelException extends Exception {

    public ModelException(String message) {
        super(message);
    }

    public ModelException(String message, Throwable cause) {
        super(message, cause);
    }
}
