/**
 * PlaygroundCockpit: the cross-border e-commerce survey workbench.
 *
 * The platform runs Amazon buyer simulation surveys only, so this cockpit is
 * a thin shell around SurveyEvalCockpit. Chatbot / web / OS-app cockpits were
 * removed for the cross-border e-commerce product; the task type is fixed to
 * "survey" and the URL state still honors `pgTask` for deep links.
 */
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { SurveyEvalCockpit } from "./SurveyEvalCockpit";
import { type PlaygroundTaskType } from "./TaskTypeSwitch";
import { useUrlState } from "@/lib/useUrlState";
import type { ConfigOptionsResponse } from "@/lib/types";

export interface PlaygroundCockpitProps {
  /** Config metadata (knobs + defaults + environment) from the app. */
  options: ConfigOptionsResponse | null;
  /** Open a Harbor batch job detail in the Runs sub-view. */
  onOpenHarborJob?: (jobName: string) => void;
  /** Open a Harbor trial debrief in the Runs sub-view. */
  onOpenHarborTrial?: (jobName: string, trialName: string) => void;
  /** Report the honest footer context up (task type + active app/instrument/site). */
  onFooterContextChange?: (context: string) => void;
}

/** Keep the survey cockpit mounted (hidden) so setup + run state survives. */
function CockpitPanel({ active, children }: { active: boolean; children: ReactNode }) {
  return (
    <div
      className={active ? "flex min-h-0 flex-1 flex-col overflow-hidden" : "hidden"}
      aria-hidden={!active}
    >
      {children}
    </div>
  );
}

function parsePlaygroundTask(_value: string | null): PlaygroundTaskType {
  // Cross-border e-commerce platform: survey-based buyer simulation only.
  return "survey";
}

export function PlaygroundCockpit({
  options,
  onOpenHarborJob,
  onOpenHarborTrial,
  onFooterContextChange,
}: PlaygroundCockpitProps) {
  const { state: urlState, setState: setUrlState } = useUrlState();
  const [taskType, setTaskTypeInternal] = useState<PlaygroundTaskType>(() => parsePlaygroundTask(urlState.pgTask));

  useEffect(() => {
    const next = parsePlaygroundTask(urlState.pgTask);
    setTaskTypeInternal((current) => (current === next ? current : next));
  }, [urlState.pgTask]);

  const setTaskType = useCallback(
    (next: PlaygroundTaskType) => {
      setTaskTypeInternal(next);
      setUrlState({
        pgTask: next,
        cockpitJob: null,
        cockpitTrial: null,
        cockpitBatch: null,
      });
    },
    [setUrlState],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <CockpitPanel active={taskType === "survey"}>
        <SurveyEvalCockpit
          options={options}
          taskType={taskType}
          onTaskTypeChange={setTaskType}
          onFooterContextChange={onFooterContextChange}
          onOpenHarborJob={onOpenHarborJob}
          onOpenHarborTrial={onOpenHarborTrial}
          isActive={taskType === "survey"}
        />
      </CockpitPanel>
    </div>
  );
}

export default PlaygroundCockpit;
