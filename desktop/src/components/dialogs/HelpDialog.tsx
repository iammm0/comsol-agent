export function HelpDialog() {
  return (
    <>
      <div className="dialog-header">帮助</div>
      <div className="dialog-body">
        <div className="dialog-section-title">快捷键</div>
        <div className="dialog-row">
          <span className="dialog-row-key">Esc</span>
          <span className="dialog-row-val">关闭对话框</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">Enter</span>
          <span className="dialog-row-val">发送消息</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">Shift+Enter</span>
          <span className="dialog-row-val">换行</span>
        </div>

        <div className="dialog-section-title">斜杠命令</div>
        <div className="dialog-row">
          <span className="dialog-row-key">/help</span>
          <span className="dialog-row-val">显示帮助</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">/ops</span>
          <span className="dialog-row-val">支持的 COMSOL 操作</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">/run</span>
          <span className="dialog-row-val">默认模式（自然语言 → 模型）</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">/plan</span>
          <span className="dialog-row-val">计划模式（自然语言 → JSON）</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">/exec</span>
          <span className="dialog-row-val">根据 JSON 创建模型</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">/backend</span>
          <span className="dialog-row-val">选择 LLM 后端</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">/context</span>
          <span className="dialog-row-val">查看或清除对话历史</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">/output</span>
          <span className="dialog-row-val">设置默认输出文件名</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">/demo</span>
          <span className="dialog-row-val">演示示例</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">/doctor</span>
          <span className="dialog-row-val">环境诊断</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">/exit</span>
          <span className="dialog-row-val">退出</span>
        </div>

        <div className="dialog-section-title">支持能力</div>
        <div className="dialog-row">
          <span className="dialog-row-key">2D/3D 几何</span>
          <span className="dialog-row-val">
            矩形/圆/椭圆/多边形/长方体/圆柱/球/锥/圆环
          </span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">布尔运算</span>
          <span className="dialog-row-val">并集/差集/交集/拉伸/旋转</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">材料系统</span>
          <span className="dialog-row-val">内置材料库 + 自定义属性</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">物理场</span>
          <span className="dialog-row-val">
            传热/电磁/结构/流体/声学/压电/化学/多体
          </span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">多物理场耦合</span>
          <span className="dialog-row-val">热应力/流固/电磁热</span>
        </div>
        <div className="dialog-row">
          <span className="dialog-row-key">研究类型</span>
          <span className="dialog-row-val">
            稳态/瞬态/特征值/频域/参数化扫描
          </span>
        </div>
      </div>
    </>
  );
}
