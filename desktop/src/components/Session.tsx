import { Header } from "./Header";
import { Footer } from "./Footer";
import { MessageList } from "./MessageList";
import { Prompt } from "./Prompt";
import { useAppState } from "../context/AppStateContext";

export function Session() {
  return (
    <div className="session-layout">
      <div className="session-main">
        <Header />
        <MessageList />
        <Prompt />
        <Footer />
      </div>
    </div>
  );
}
