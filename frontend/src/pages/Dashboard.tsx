import { ConversationPanel } from "../components/conversations/ConversationPanel";
import { ActiveTasksCard } from "../components/dashboard/ActiveTasksCard";
import { CurrentSprintCard } from "../components/dashboard/CurrentSprintCard";
import "../components/dashboard/dashboard.css";
import { ProjectProgressCard } from "../components/dashboard/ProjectProgressCard";
import { RecentGitActivityCard } from "../components/dashboard/RecentGitActivityCard";
import { UpcomingMeetingsCard } from "../components/dashboard/UpcomingMeetingsCard";
import { SmeQuestionModal } from "../components/sme/SmeQuestionModal";
import { LiveTerminal } from "../components/terminal/LiveTerminal";
import { usePodStore } from "../store/podStore";
import { NoProjectBanner } from "./NoProjectBanner";

export function Dashboard() {
  const hasProject = usePodStore((s) => s.hasProject);
  const loaded = usePodStore((s) => s.loaded);

  if (loaded && !hasProject) {
    return <NoProjectBanner />;
  }

  return (
    <div className="dashboard-grid">
      <div className="dashboard-top-row">
        <ConversationPanel />
        <LiveTerminal />
      </div>
      <div className="dashboard-bottom-row">
        <ProjectProgressCard />
        <CurrentSprintCard />
        <ActiveTasksCard />
        <RecentGitActivityCard />
        <UpcomingMeetingsCard />
      </div>
      <SmeQuestionModal />
    </div>
  );
}
