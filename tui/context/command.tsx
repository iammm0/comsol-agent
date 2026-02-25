import {
  createContext,
  useContext,
  createSignal,
  createMemo,
  onCleanup,
  type ParentProps,
  type Accessor,
} from "solid-js";
import { useKeyboard } from "@opentui/solid";
import { useDialog } from "./dialog";
import { DialogSelect, type DialogSelectOption } from "../ui/DialogSelect";

export type Slash = { name: string; aliases?: string[] };

export type CommandOption = {
  title: string;
  value: string;
  description?: string;
  keybind?: string;
  category?: string;
  slash?: Slash;
  hidden?: boolean;
  enabled?: boolean;
  suggested?: boolean;
  onSelect: (dialog: ReturnType<typeof useDialog>) => void;
};

type CommandContextValue = {
  register: (fn: () => CommandOption[]) => void;
  trigger: (value: string) => void;
  show: () => void;
  slashes: () => { display: string; value: string; description?: string; onSelect: () => void }[];
};

const CommandContext = createContext<CommandContextValue | undefined>(undefined);

export function CommandProvider(props: ParentProps) {
  const dialog = useDialog();
  const [registrations, setRegistrations] = createSignal<Accessor<CommandOption[]>[]>([]);

  const entries = createMemo(() =>
    registrations().flatMap((fn) => fn()),
  );

  const isEnabled = (o: CommandOption) => o.enabled !== false;
  const isVisible = (o: CommandOption) => isEnabled(o) && !o.hidden;

  const visibleOptions = createMemo(() => entries().filter(isVisible));

  const slashes = createMemo(() =>
    visibleOptions()
      .filter((o) => o.slash)
      .flatMap((o) => {
        const name = o.slash!.name;
        const onSelect = () => result.trigger(o.value);
        const items = [{ display: "/" + name, value: o.value, description: o.description ?? o.title, onSelect }];
        for (const alias of o.slash!.aliases ?? []) {
          items.push({ display: "/" + alias, value: o.value, description: o.description ?? o.title, onSelect });
        }
        return items;
      }),
  );

  function showCommandDialog() {
    const options: DialogSelectOption[] = visibleOptions().map((o) => ({
      title: o.title,
      value: o.value,
      description: o.description,
      category: o.category,
      footer: o.keybind,
    }));
    dialog.replace(() => (
      <DialogSelect
        title="命令"
        options={options}
        onSelect={(opt) => result.trigger(opt.value)}
      />
    ));
  }

  const result: CommandContextValue = {
    register(fn: () => CommandOption[]) {
      const memo = createMemo(fn);
      setRegistrations((prev) => [memo, ...prev]);
      onCleanup(() => {
        setRegistrations((prev) => prev.filter((x) => x !== memo));
      });
    },
    trigger(value: string) {
      const option = entries().find((e) => e.value === value);
      if (option && isEnabled(option)) {
        option.onSelect(dialog);
      }
    },
    show: showCommandDialog,
    slashes,
  };

  useKeyboard((evt) => {
    if (evt.defaultPrevented) return;

    // Ctrl+K opens command palette
    if (evt.ctrl && evt.name === "k") {
      if (dialog.stack.length === 0) {
        evt.preventDefault();
        evt.stopPropagation?.();
        showCommandDialog();
        return;
      }
    }

    // ESC closes dialog
    if (dialog.stack.length > 0) {
      return;
    }

    // Global keybind matching
    for (const option of entries()) {
      if (!isEnabled(option)) continue;
      if (option.keybind && matchKeybind(option.keybind, evt)) {
        evt.preventDefault();
        option.onSelect(dialog);
        return;
      }
    }

    // q to exit (when no dialog open)
    if (evt.name === "q" && !evt.ctrl && !evt.meta) {
      result.trigger("app.exit");
      evt.preventDefault?.();
    }
  });

  return (
    <CommandContext.Provider value={result}>
      {props.children}
    </CommandContext.Provider>
  );
}

function matchKeybind(keybind: string, evt: any): boolean {
  const parts = keybind.toLowerCase().split("+");
  const key = parts[parts.length - 1];
  const needCtrl = parts.includes("ctrl");
  const needMeta = parts.includes("meta");
  const needShift = parts.includes("shift");

  if (needCtrl && !evt.ctrl) return false;
  if (!needCtrl && evt.ctrl) return false;
  if (needMeta && !evt.meta) return false;
  if (needShift && !evt.shift) return false;

  return evt.name === key;
}

export function useCommand() {
  const ctx = useContext(CommandContext);
  if (!ctx) throw new Error("useCommand must be used within CommandProvider");
  return ctx;
}
