import { createSignal, createMemo, For, Show } from "solid-js";
import { useTheme } from "../context/theme";
import { useDialog } from "../context/dialog";

export type DialogSelectOption = {
  title: string;
  value: string;
  description?: string;
  category?: string;
  footer?: string;
};

export function DialogSelect(props: {
  title: string;
  options: DialogSelectOption[];
  onSelect?: (option: DialogSelectOption) => void;
}) {
  const { theme } = useTheme();
  const dialog = useDialog();
  const [filter, setFilter] = createSignal("");

  const filtered = createMemo(() => {
    const q = filter().toLowerCase();
    if (!q) return props.options;
    return props.options.filter(
      (o) =>
        o.title.toLowerCase().includes(q) ||
        (o.description ?? "").toLowerCase().includes(q) ||
        (o.category ?? "").toLowerCase().includes(q),
    );
  });

  const grouped = createMemo(() => {
    const groups = new Map<string, DialogSelectOption[]>();
    for (const opt of filtered()) {
      const cat = opt.category ?? "";
      if (!groups.has(cat)) groups.set(cat, []);
      groups.get(cat)!.push(opt);
    }
    return groups;
  });

  return (
    <box flexDirection="column" paddingBottom={1}>
      <box paddingLeft={2} paddingRight={2} paddingBottom={1}>
        <text fg={theme.text}>{props.title}</text>
      </box>
      <box paddingLeft={2} paddingRight={2} paddingBottom={1}>
        <input
          placeholder=" 搜索..."
          width="100%"
          focused={true}
          onSubmit={(v: unknown) => {
            const items = filtered();
            if (items.length > 0) {
              const item = items[0];
              if (props.onSelect) {
                props.onSelect(item);
              }
              dialog.clear();
            }
          }}
          onInput={(v: string) => setFilter(v)}
        />
      </box>
      <scrollbox maxHeight={16} flexGrow={1}>
        <box flexDirection="column">
          <For each={[...grouped().entries()]}>
            {([category, options]) => (
              <>
                <Show when={category}>
                  <box paddingLeft={2} paddingTop={1}>
                    <text fg={theme.textMuted}>{category}</text>
                  </box>
                </Show>
                <For each={options}>
                  {(option) => (
                    <box
                      paddingLeft={4}
                      paddingRight={2}
                      flexDirection="row"
                      justifyContent="space-between"
                      onMouseUp={() => {
                        if (props.onSelect) {
                          props.onSelect(option);
                        }
                        dialog.clear();
                      }}
                    >
                      <text fg={theme.text}>{option.title}</text>
                      <Show when={option.footer}>
                        <text fg={theme.textMuted}>{option.footer}</text>
                      </Show>
                    </box>
                  )}
                </For>
              </>
            )}
          </For>
          <Show when={filtered().length === 0}>
            <box paddingLeft={2}>
              <text fg={theme.textMuted}>无匹配项</text>
            </box>
          </Show>
        </box>
      </scrollbox>
    </box>
  );
}
