/** 尚无 bridge 事件时，提示推理正在进行（避免空白像卡死） */

interface ReasoningLivePlaceholderProps {
  phaseHint: string;
}

export function ReasoningLivePlaceholder({ phaseHint }: ReasoningLivePlaceholderProps) {
  return (
    <div
      className="reasoning-live-placeholder"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="reasoning-live-placeholder__header">
        <span className="reasoning-live-placeholder__dots" aria-hidden>
          <span className="reasoning-live-placeholder__dot" />
          <span className="reasoning-live-placeholder__dot" />
          <span className="reasoning-live-placeholder__dot" />
        </span>
        <span className="reasoning-live-placeholder__title">推理进行中</span>
        <span className="reasoning-live-placeholder__phase">{phaseHint}</span>
      </div>
      <p className="reasoning-live-placeholder__hint">
        正在等待模型与执行层输出，流式内容将出现在下方。
      </p>
      <div className="reasoning-live-placeholder__skeleton" aria-hidden>
        <div className="reasoning-live-placeholder__bar" />
        <div className="reasoning-live-placeholder__bar reasoning-live-placeholder__bar--mid" />
        <div className="reasoning-live-placeholder__bar reasoning-live-placeholder__bar--short" />
      </div>
    </div>
  );
}
