"""路由：根据用户输入决定走 Q&A 还是技术/执行流（Planner → Core → Summary）。"""
from typing import Literal

RouteResult = Literal["qa", "technical"]

# 问候/再见 -> 走 Q&A
GREETING_KEYWORDS = ["你好", "嗨", "hello", "hi", "再见", "bye", "谢谢", "感谢", "帮助", "help"]
# 操作类动词 -> 走 technical
TECHNICAL_KEYWORDS = ["创建", "建", "画", "添加", "执行", "分析", "扫描", "生成", "建模", "几何", "物理", "网格", "求解", "研究", "create", "add", "build", "run", "solve", "model"]


def route(user_input: str) -> RouteResult:
    """
    根据用户输入返回 "qa" 或 "technical"。
    规则：先匹配问候/再见 -> 问答；再匹配操作词 -> technical；短句且无操作词默认 qa。
    """
    text = (user_input or "").strip().lower()
    if not text:
        return "qa"

    # 先匹配问候/再见
    for w in GREETING_KEYWORDS:
        if w in text and len(text) < 80:
            return "qa"

    # 再匹配操作类
    for w in TECHNICAL_KEYWORDS:
        if w in text:
            return "technical"

    # 短句且无操作词默认 Q&A
    if len(text) < 30:
        return "qa"
    return "technical"
