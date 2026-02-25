import {
  createContext,
  useContext,
  Show,
  type ParentProps,
  type JSX,
} from "solid-js";
import { createStore } from "solid-js/store";
import { useKeyboard, useTerminalDimensions } from "@opentui/solid";
import { RGBA } from "@opentui/core";
import { useTheme } from "./theme";

type StackEntry = {
  element: JSX.Element;
  onClose?: () => void;
};

type DialogContextValue = {
  stack: StackEntry[];
  replace: (element: () => JSX.Element, onClose?: () => void) => void;
  clear: () => void;
  size: "medium" | "large";
  setSize: (size: "medium" | "large") => void;
};

const DialogContext = createContext<DialogContextValue | undefined>(undefined);

export function DialogProvider(props: ParentProps) {
  const [store, setStore] = createStore({
    stack: [] as StackEntry[],
    size: "medium" as "medium" | "large",
  });
  const { theme } = useTheme();
  const dimensions = useTerminalDimensions();

  useKeyboard((evt) => {
    if (store.stack.length === 0) return;
    if (evt.defaultPrevented) return;
    if (evt.name === "escape" || (evt.ctrl && evt.name === "c")) {
      const current = store.stack.at(-1);
      current?.onClose?.();
      setStore("stack", store.stack.slice(0, -1));
      evt.preventDefault();
      evt.stopPropagation?.();
    }
  });

  const value: DialogContextValue = {
    get stack() {
      return store.stack;
    },
    replace(element: () => JSX.Element, onClose?: () => void) {
      for (const item of store.stack) {
        item.onClose?.();
      }
      setStore("size", "medium");
      setStore("stack", [{ element: element(), onClose }]);
    },
    clear() {
      for (const item of store.stack) {
        item.onClose?.();
      }
      setStore("size", "medium");
      setStore("stack", []);
    },
    get size() {
      return store.size;
    },
    setSize(size: "medium" | "large") {
      setStore("size", size);
    },
  };

  return (
    <DialogContext.Provider value={value}>
      {props.children}
      <Show when={store.stack.length > 0} fallback={<box />}>
        <box
          position="absolute"
          width={dimensions().width}
          height={dimensions().height}
          left={0}
          top={0}
          alignItems="center"
          paddingTop={Math.floor(dimensions().height / 4)}
          backgroundColor={RGBA.fromInts(0, 0, 0, 150)}
          onMouseUp={() => value.clear()}
        >
          <box
            onMouseUp={(e: any) => {
              e?.stopPropagation?.();
            }}
            width={store.size === "large" ? 80 : 60}
            maxWidth={dimensions().width - 2}
            backgroundColor={theme.backgroundPanel}
            paddingTop={1}
          >
            {store.stack.at(-1)?.element}
          </box>
        </box>
      </Show>
    </DialogContext.Provider>
  );
}

export function useDialog() {
  const ctx = useContext(DialogContext);
  if (!ctx) throw new Error("useDialog must be used within DialogProvider");
  return ctx;
}
