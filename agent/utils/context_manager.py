"""上下文管理模块 - 对话历史和摘要"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict

from agent.utils.config import get_settings, get_install_dir
from agent.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConversationEntry:
    """对话条目"""
    timestamp: str
    user_input: str
    plan: Optional[Dict[str, Any]] = None
    model_path: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class ContextSummary:
    """上下文摘要"""
    summary: str
    last_updated: str
    total_conversations: int
    recent_shapes: List[str]  # 最近使用的形状类型
    preferences: Dict[str, Any]  # 用户偏好（如常用单位、尺寸范围等）


class ContextManager:
    """上下文管理器"""
    
    def __init__(self, context_dir: Optional[Path] = None):
        """
        初始化上下文管理器
        
        Args:
            context_dir: 上下文存储目录，如果为 None 则使用默认目录
        """
        if context_dir is None:
            settings = get_settings()
            install_dir = get_install_dir()
            # 使用安装目录下的 .context 文件夹
            context_dir = install_dir / ".context"
        
        self.context_dir = Path(context_dir)
        self.context_dir.mkdir(parents=True, exist_ok=True)
        
        self.history_file = self.context_dir / "history.json"
        self.summary_file = self.context_dir / "summary.json"
    
    def add_conversation(
        self,
        user_input: str,
        plan: Optional[Dict[str, Any]] = None,
        model_path: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> ConversationEntry:
        """
        添加对话记录
        
        Args:
            user_input: 用户输入
            plan: 解析后的计划
            model_path: 生成的模型路径
            success: 是否成功
            error: 错误信息
        
        Returns:
            ConversationEntry 对象
        """
        entry = ConversationEntry(
            timestamp=datetime.now().isoformat(),
            user_input=user_input,
            plan=plan,
            model_path=str(model_path) if model_path else None,
            success=success,
            error=error
        )
        
        # 加载历史记录
        history = self.load_history()
        history.append(asdict(entry))
        
        # 保存历史记录（只保留最近 100 条）
        if len(history) > 100:
            history = history[-100:]
        
        self.save_history(history)
        
        # 更新摘要
        self.update_summary()
        
        logger.debug(f"已添加对话记录: {user_input[:50]}...")
        return entry
    
    def load_history(self) -> List[Dict[str, Any]]:
        """加载对话历史"""
        if not self.history_file.exists():
            return []
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载历史记录失败: {e}")
            return []
    
    def save_history(self, history: List[Dict[str, Any]]):
        """保存对话历史"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存历史记录失败: {e}")
    
    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的对话历史"""
        history = self.load_history()
        return history[-limit:]
    
    def load_summary(self) -> Optional[ContextSummary]:
        """加载上下文摘要"""
        if not self.summary_file.exists():
            return None
        
        try:
            with open(self.summary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return ContextSummary(**data)
        except Exception as e:
            logger.warning(f"加载摘要失败: {e}")
            return None
    
    def save_summary(self, summary: ContextSummary):
        """保存上下文摘要"""
        try:
            with open(self.summary_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(summary), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存摘要失败: {e}")
    
    def update_summary(self):
        """更新上下文摘要"""
        history = self.load_history()
        
        if not history:
            return
        
        # 提取最近使用的形状类型
        recent_shapes = []
        for entry in history[-20:]:  # 最近 20 条
            if entry.get('plan') and 'shapes' in entry['plan']:
                for shape in entry['plan']['shapes']:
                    shape_type = shape.get('type', '')
                    if shape_type and shape_type not in recent_shapes:
                        recent_shapes.append(shape_type)
        
        # 提取用户偏好
        preferences = {}
        units_count = {}
        for entry in history[-20:]:
            if entry.get('plan'):
                plan = entry['plan']
                # 统计常用单位
                unit = plan.get('units', 'm')
                units_count[unit] = units_count.get(unit, 0) + 1
        
        if units_count:
            preferences['preferred_unit'] = max(units_count.items(), key=lambda x: x[1])[0]
        
        # 生成摘要文本
        summary_text = self._generate_summary_text(history, recent_shapes, preferences)
        
        summary = ContextSummary(
            summary=summary_text,
            last_updated=datetime.now().isoformat(),
            total_conversations=len(history),
            recent_shapes=recent_shapes,
            preferences=preferences
        )
        
        self.save_summary(summary)
        logger.debug("上下文摘要已更新")
    
    def _generate_summary_text(
        self,
        history: List[Dict[str, Any]],
        recent_shapes: List[str],
        preferences: Dict[str, Any]
    ) -> str:
        """生成摘要文本"""
        if not history:
            return "暂无对话历史"
        
        # 统计信息
        total = len(history)
        successful = sum(1 for e in history if e.get('success', True))
        
        # 最近活动
        recent_count = min(5, total)
        recent_entries = history[-recent_count:]
        
        summary_parts = [
            f"总计 {total} 次对话，成功 {successful} 次。",
        ]
        
        if recent_shapes:
            summary_parts.append(f"最近使用的形状类型: {', '.join(recent_shapes)}。")
        
        if preferences.get('preferred_unit'):
            summary_parts.append(f"常用单位: {preferences['preferred_unit']}。")
        
        if recent_entries:
            summary_parts.append("最近活动:")
            for entry in recent_entries:
                user_input = entry.get('user_input', '')[:50]
                status = "成功" if entry.get('success', True) else "失败"
                summary_parts.append(f"  - {user_input}... ({status})")
        
        return "\n".join(summary_parts)
    
    def get_context_for_planner(self) -> str:
        """获取用于 Planner 的上下文信息"""
        summary = self.load_summary()
        if not summary:
            return ""
        
        context_parts = []
        
        if summary.recent_shapes:
            context_parts.append(f"用户最近使用的形状类型: {', '.join(summary.recent_shapes)}")
        
        if summary.preferences.get('preferred_unit'):
            context_parts.append(f"用户常用单位: {summary.preferences['preferred_unit']}")
        
        # 添加最近几次对话的关键信息
        recent_history = self.get_recent_history(3)
        if recent_history:
            context_parts.append("最近的对话:")
            for entry in recent_history:
                if entry.get('success', True) and entry.get('plan'):
                    plan = entry['plan']
                    shapes_info = []
                    for shape in plan.get('shapes', []):
                        shape_type = shape.get('type', '')
                        if shape_type:
                            shapes_info.append(shape_type)
                    if shapes_info:
                        context_parts.append(f"  - 创建了: {', '.join(shapes_info)}")
        
        return "\n".join(context_parts) if context_parts else ""
    
    def clear_history(self):
        """清除对话历史"""
        if self.history_file.exists():
            self.history_file.unlink()
        if self.summary_file.exists():
            self.summary_file.unlink()
        logger.info("对话历史已清除")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        history = self.load_history()
        summary = self.load_summary()
        
        return {
            "total_conversations": len(history),
            "successful": sum(1 for e in history if e.get('success', True)),
            "failed": sum(1 for e in history if not e.get('success', True)),
            "summary": summary.summary if summary else "暂无摘要",
            "recent_shapes": summary.recent_shapes if summary else [],
            "preferences": summary.preferences if summary else {},
        }


# 全局上下文管理器实例
_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """获取上下文管理器实例（单例）"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
