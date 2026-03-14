import type { ClarifyingOption, ClarifyingQuestion } from "../../lib/types";
import {
  isMultiSelectQuestion,
  isSupplementOption,
} from "../../lib/clarifying";

export interface ClarifyingQuestionItemProps {
  question: ClarifyingQuestion;
  selectedOptionIds: string[];
  supplementText?: string;
  onToggleOption: (questionId: string, optionId: string) => void;
  onChangeSupplement: (questionId: string, value: string) => void;
}

export function ClarifyingQuestionItem({
  question,
  selectedOptionIds,
  supplementText = "",
  onToggleOption,
  onChangeSupplement,
}: ClarifyingQuestionItemProps) {
  const isMulti = isMultiSelectQuestion(question);

  const isSelected = (option: ClarifyingOption): boolean =>
    selectedOptionIds.includes(option.id);

  return (
    <div className="plan-question-item">
      <div className="plan-question-text">
        {question.text}
        <span className="plan-question-type">{isMulti ? "（多选）" : "（单选）"}</span>
      </div>

      <div className="plan-question-options">
        {question.options.map((option: ClarifyingOption) => {
          const selected = isSelected(option);
          const supplement = isSupplementOption(option);

          return (
            <div key={option.id} className="plan-question-option-wrap">
              <button
                type="button"
                className={`plan-question-option ${selected ? "selected" : ""} ${option.recommended ? "recommended" : ""}`}
                onClick={() => onToggleOption(question.id, option.id)}
              >
                {option.recommended && (
                  <span className="plan-question-option-badge">推荐</span>
                )}
                {option.label}
              </button>

              {supplement && selected ? (
                <textarea
                  className="plan-question-supplement-input"
                  placeholder="请输入补充内容..."
                  value={supplementText}
                  onChange={(e) =>
                    onChangeSupplement(question.id, e.currentTarget.value)
                  }
                  rows={2}
                />
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
