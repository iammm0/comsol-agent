import { Header } from "./Header";
import { Footer } from "./Footer";
import { MessageList } from "./MessageList";
import { Prompt } from "./Prompt";

export function Session() {
  return (
    <>
      <Header />
      <MessageList />
      <Prompt />
      <Footer />
    </>
  );
}
