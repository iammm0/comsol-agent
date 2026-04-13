import { MessageList } from "./MessageList";
import { ContextMemorySidebar } from "./ContextMemorySidebar";
import { Prompt } from "./Prompt";

export function Session() {
  return (
    <div className="session-layout">
      <div className="session-main">
        <MessageList />
        <Prompt />
      </div>
      <ContextMemorySidebar />
    </div>
  );
}
