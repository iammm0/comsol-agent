"""Prompt 模板加载器"""
from pathlib import Path
from typing import Dict


class PromptLoader:
    """Prompt 模板加载器"""
    
    def __init__(self, prompts_dir: str = "prompts"):
        """
        初始化 Prompt 加载器
        
        Args:
            prompts_dir: Prompt 模板目录路径
        """
        self.prompts_dir = Path(prompts_dir)
        self._cache: Dict[str, str] = {}
    
    def load(self, category: str, name: str) -> str:
        """
        加载 Prompt 模板
        
        Args:
            category: 类别（如 "planner", "executor"）
            name: 模板名称（不含扩展名）
        
        Returns:
            Prompt 模板内容
        """
        cache_key = f"{category}/{name}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        template_path = self.prompts_dir / category / f"{name}.txt"
        
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt 模板不存在: {template_path}")
        
        content = template_path.read_text(encoding="utf-8")
        self._cache[cache_key] = content
        
        return content
    
    def format(self, category: str, name: str, **kwargs) -> str:
        """
        加载并格式化 Prompt 模板
        
        Args:
            category: 类别
            name: 模板名称
            **kwargs: 格式化参数
        
        Returns:
            格式化后的 Prompt
        """
        template = self.load(category, name)
        return template.format(**kwargs)


# 全局实例
prompt_loader = PromptLoader()
