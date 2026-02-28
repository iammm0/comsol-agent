import { COMSOL_OPS } from "../../lib/types";

export function ComsolOpsDialog({ onClose }: { onClose: () => void }) {
  return (
    <>
      <div className="dialog-header">支持的 COMSOL 操作</div>
      <div className="dialog-body">
        <p className="dialog-hint" style={{ marginBottom: "12px" }}>
          以下为当前 Agent 支持的 COMSOL 建模操作，选择斜杠命令 /ops 后在此弹窗中实时查看。
        </p>
        <div className="dialog-section-title">执行步骤</div>
        {COMSOL_OPS.map((op) => (
          <div key={op.action} className="dialog-row">
            <span className="dialog-row-key">{op.label}</span>
            <span className="dialog-row-val">{op.description}</span>
          </div>
        ))}
        <div className="dialog-actions" style={{ marginTop: "16px" }}>
          <button type="button" className="dialog-btn primary" onClick={onClose}>
            关闭
          </button>
        </div>
      </div>
    </>
  );
}
