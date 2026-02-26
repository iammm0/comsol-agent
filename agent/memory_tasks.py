"""Celery 任务：会话记忆更新（摘要式记忆）。"""
from agent.celery_app import app
from agent.memory_agent import update_conversation_memory


@app.task(name="agent.memory_tasks.update_memory_task")
def update_memory_task(
    conversation_id: str,
    user_input: str,
    assistant_summary: str,
    success: bool = True,
) -> None:
    """
    后台任务：更新指定会话的摘要记忆。
    桌面端每次 run 结束后可调用此任务，由 Celery worker 异步执行。
    """
    update_conversation_memory(
        conversation_id=conversation_id,
        user_input=user_input,
        assistant_summary=assistant_summary,
        success=success,
    )
