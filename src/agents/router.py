"""
模块路由：根据用户意图将请求分派到 COMSOL 三模块之一。

与 docs/comsol-modules-and-context.md 中的「模块路由」对应。
扩展点：可替换为基于关键词/规则/模型的更复杂实现，或增加 get_agent(module) 等。
"""
from typing import Literal

COMSOLModuleRoute = Literal["model_developer", "app_developer", "model_manager", "qa"]


def route_to_module(user_input: str) -> COMSOLModuleRoute:
    """
    根据用户输入决定走哪个 COMSOL 模块（或 Q&A）。

    当前为占位实现：除明确匹配 App/模型管理 的关键词外，均走模型开发器；
    问候/帮助类短句可在此扩展为返回 "qa"。
    """
    text = (user_input or "").strip().lower()
    if not text:
        return "qa"

    # App 开发器相关意图（后续可扩展）
    app_keywords = ("app", "应用", "界面", "form", "方法", "method", "打包", "部署")
    if any(k in text for k in app_keywords) and any(
        w in text for w in ("做", "做成", "开发", "定制", "建", "创建")
    ):
        return "app_developer"

    # 模型管理器相关意图（后续可扩展）
    manager_keywords = ("列出", "列表", "最近", "打开项目", "版本", "检索", "管理", "工作区")
    if any(k in text for k in manager_keywords):
        return "model_manager"

    # 默认：建模、几何、物理、网格、求解等均走模型开发器
    return "model_developer"
