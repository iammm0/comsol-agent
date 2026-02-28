"""
Celery 应用：供记忆 Agent 在后台异步更新会话摘要。
需安装可选依赖：uv sync -e memory 或 pip install celery redis
启动 Redis 后运行: celery -A agent.core.celery_app worker -l info
"""
from celery import Celery

app = Celery(
    "comsol_agent",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["agent.memory.tasks"],
)
app.conf.task_default_queue = "memory"
app.conf.task_routes = {"agent.memory.tasks.update_memory_task": {"queue": "memory"}}
