import type { ReactNode, MouseEvent } from "react";

interface Props {
  onClose: () => void;
  children: ReactNode;
}

export function DialogOverlay({ onClose, children }: Props) {
  const handleBackdrop = (e: MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div className="dialog-overlay" onClick={handleBackdrop}>
      <div className="dialog-box">{children}</div>
    </div>
  );
}
