import { CircleHelp, X } from "lucide-react";
import { useState } from "react";

import { api } from "../../api/client";
import { usePodStore } from "../../store/podStore";
import { Avatar } from "../common/Avatar";
import "./SmeQuestionModal.css";

/**
 * Surfaces the oldest open SME question, matching the dashboard's
 * "Question for Business SME" modal. In SME_MODE=auto (the default for an
 * unattended live run) the backend usually answers within a second or two,
 * so this modal is mostly relevant when SME_MODE=human -- a person plays
 * the Business SME and answers here, which is what actually unblocks the
 * agent that asked and lets the pipeline continue past that clarification.
 */
export function SmeQuestionModal() {
  const questions = usePodStore((s) => s.smeQuestions);
  const agents = usePodStore((s) => s.agents);
  const refreshSmeQuestions = usePodStore((s) => s.refreshSmeQuestions);
  const [answer, setAnswer] = useState("");
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [sending, setSending] = useState(false);

  const open = questions.find((q) => !dismissed.has(q.question.question_id));
  if (!open) return null;

  const asker = agents.find((a) => a.agent_id === open.question.asked_by);

  const send = async () => {
    if (!answer.trim() || sending) return;
    setSending(true);
    try {
      await api.answerSmeQuestion(open.question.question_id, answer.trim());
      setAnswer("");
      await refreshSmeQuestions();
    } finally {
      setSending(false);
    }
  };

  const cancel = () => {
    setDismissed((prev) => new Set(prev).add(open.question.question_id));
  };

  return (
    <div className="sme-modal-backdrop">
      <div className="sme-modal">
        <div className="sme-modal-header">
          <div className="panel-title">
            <CircleHelp size={16} />
            Question for Business SME
          </div>
          <button className="btn btn-ghost btn-sm" onClick={cancel} aria-label="Dismiss">
            <X size={16} />
          </button>
        </div>

        <div className="sme-modal-body">
          <div className="sme-modal-from">
            <Avatar name={asker?.avatar_initials ?? "AG"} color={asker?.color ?? "#495057"} size={28} />
            <div>
              <div className="sme-modal-from-label">From: {open.question.asked_by_name}</div>
              <span className={"badge " + (open.question.priority === "high" ? "badge-red" : "badge-neutral")}>
                {open.question.priority} priority
              </span>
            </div>
          </div>

          <div className="sme-modal-question">{open.question.text}</div>
          {open.question.reason && <div className="sme-modal-reason">Why it's unclear: {open.question.reason}</div>}
        </div>

        <div className="sme-modal-footer">
          <input
            className="input"
            placeholder="Type your answer for the team..."
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") send();
            }}
          />
          <button className="btn" onClick={cancel}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={send} disabled={!answer.trim() || sending}>
            Send to Team
          </button>
        </div>
      </div>
    </div>
  );
}
