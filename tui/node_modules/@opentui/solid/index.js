// @bun
// index.ts
import { CliRenderer, createCliRenderer, engine as engine2 } from "@opentui/core";
import { createTestRenderer } from "@opentui/core/testing";

// src/elements/index.ts
import {
  ASCIIFontRenderable,
  BoxRenderable,
  CodeRenderable,
  DiffRenderable,
  InputRenderable as InputRenderable2,
  LineNumberRenderable,
  MarkdownRenderable,
  ScrollBoxRenderable as ScrollBoxRenderable2,
  SelectRenderable as SelectRenderable2,
  TabSelectRenderable as TabSelectRenderable2,
  TextareaRenderable,
  TextAttributes,
  TextNodeRenderable as TextNodeRenderable3,
  TextRenderable as TextRenderable3
} from "@opentui/core";

// src/elements/hooks.ts
import {
  engine,
  Timeline
} from "@opentui/core";
import { createContext, createSignal, onCleanup, onMount, useContext } from "solid-js";
var RendererContext = createContext();
var useRenderer = () => {
  const renderer = useContext(RendererContext);
  if (!renderer) {
    throw new Error("No renderer found");
  }
  return renderer;
};
var onResize = (callback) => {
  const renderer = useRenderer();
  onMount(() => {
    renderer.on("resize", callback);
  });
  onCleanup(() => {
    renderer.off("resize", callback);
  });
};
var useTerminalDimensions = () => {
  const renderer = useRenderer();
  const [terminalDimensions, setTerminalDimensions] = createSignal({ width: renderer.width, height: renderer.height });
  const callback = (width, height) => {
    setTerminalDimensions({ width, height });
  };
  onResize(callback);
  return terminalDimensions;
};
var useKeyboard = (callback, options) => {
  const renderer = useRenderer();
  const keyHandler = renderer.keyInput;
  onMount(() => {
    keyHandler.on("keypress", callback);
    if (options?.release) {
      keyHandler.on("keyrelease", callback);
    }
  });
  onCleanup(() => {
    keyHandler.off("keypress", callback);
    if (options?.release) {
      keyHandler.off("keyrelease", callback);
    }
  });
};
var usePaste = (callback) => {
  const renderer = useRenderer();
  const keyHandler = renderer.keyInput;
  onMount(() => {
    keyHandler.on("paste", callback);
  });
  onCleanup(() => {
    keyHandler.off("paste", callback);
  });
};
var useKeyHandler = useKeyboard;
var useSelectionHandler = (callback) => {
  const renderer = useRenderer();
  onMount(() => {
    renderer.on("selection", callback);
  });
  onCleanup(() => {
    renderer.off("selection", callback);
  });
};
var useTimeline = (options = {}) => {
  const timeline = new Timeline(options);
  onMount(() => {
    if (options.autoplay !== false) {
      timeline.play();
    }
    engine.register(timeline);
  });
  onCleanup(() => {
    timeline.pause();
    engine.unregister(timeline);
  });
  return timeline;
};
// src/elements/extras.ts
import { createEffect, createMemo as createMemo2, getOwner, onCleanup as onCleanup2, runWithOwner, splitProps, untrack as untrack2 } from "solid-js";

// src/reconciler.ts
import {
  BaseRenderable,
  createTextAttributes,
  InputRenderable,
  InputRenderableEvents,
  isTextNodeRenderable,
  parseColor,
  Renderable,
  RootTextNodeRenderable,
  ScrollBoxRenderable,
  SelectRenderable,
  SelectRenderableEvents,
  TabSelectRenderable,
  TabSelectRenderableEvents,
  TextNodeRenderable,
  TextRenderable
} from "@opentui/core";
import { useContext as useContext2 } from "solid-js";

// src/renderer/universal.js
import { createRoot, createRenderEffect, createMemo, createComponent, untrack, mergeProps } from "solid-js";
var memo = (fn) => createMemo(() => fn());
function createRenderer({
  createElement,
  createTextNode,
  createSlotNode,
  isTextNode,
  replaceText,
  insertNode,
  removeNode,
  setProperty,
  getParentNode,
  getFirstChild,
  getNextSibling
}) {
  function insert(parent, accessor, marker, initial) {
    if (marker !== undefined && !initial)
      initial = [];
    if (typeof accessor !== "function")
      return insertExpression(parent, accessor, initial, marker);
    createRenderEffect((current) => insertExpression(parent, accessor(), current, marker), initial);
  }
  function insertExpression(parent, value, current, marker, unwrapArray) {
    while (typeof current === "function")
      current = current();
    if (value === current)
      return current;
    const t = typeof value, multi = marker !== undefined;
    if (t === "string" || t === "number") {
      if (t === "number")
        value = value.toString();
      if (multi) {
        let node = current[0];
        if (node && isTextNode(node)) {
          replaceText(node, value);
        } else
          node = createTextNode(value);
        current = cleanChildren(parent, current, marker, node);
      } else {
        if (current !== "" && typeof current === "string") {
          replaceText(getFirstChild(parent), current = value);
        } else {
          cleanChildren(parent, current, marker, createTextNode(value));
          current = value;
        }
      }
    } else if (value == null || t === "boolean") {
      current = cleanChildren(parent, current, marker);
    } else if (t === "function") {
      createRenderEffect(() => {
        let v = value();
        while (typeof v === "function")
          v = v();
        current = insertExpression(parent, v, current, marker);
      });
      return () => current;
    } else if (Array.isArray(value)) {
      const array = [];
      if (normalizeIncomingArray(array, value, unwrapArray)) {
        createRenderEffect(() => current = insertExpression(parent, array, current, marker, true));
        return () => current;
      }
      if (array.length === 0) {
        const replacement = cleanChildren(parent, current, marker);
        if (multi)
          return current = replacement;
      } else {
        if (Array.isArray(current)) {
          if (current.length === 0) {
            appendNodes(parent, array, marker);
          } else
            reconcileArrays(parent, current, array);
        } else if (current == null || current === "") {
          appendNodes(parent, array);
        } else {
          reconcileArrays(parent, multi && current || [getFirstChild(parent)], array);
        }
      }
      current = array;
    } else {
      if (Array.isArray(current)) {
        if (multi)
          return current = cleanChildren(parent, current, marker, value);
        cleanChildren(parent, current, null, value);
      } else if (current == null || current === "" || !getFirstChild(parent)) {
        insertNode(parent, value);
      } else
        replaceNode(parent, value, getFirstChild(parent));
      current = value;
    }
    return current;
  }
  function normalizeIncomingArray(normalized, array, unwrap) {
    let dynamic = false;
    for (let i = 0, len = array.length;i < len; i++) {
      let item = array[i], t;
      if (item == null || item === true || item === false)
        ;
      else if (Array.isArray(item)) {
        dynamic = normalizeIncomingArray(normalized, item) || dynamic;
      } else if ((t = typeof item) === "string" || t === "number") {
        normalized.push(createTextNode(item));
      } else if (t === "function") {
        if (unwrap) {
          while (typeof item === "function")
            item = item();
          dynamic = normalizeIncomingArray(normalized, Array.isArray(item) ? item : [item]) || dynamic;
        } else {
          normalized.push(item);
          dynamic = true;
        }
      } else
        normalized.push(item);
    }
    return dynamic;
  }
  function reconcileArrays(parentNode, a, b) {
    let bLength = b.length, aEnd = a.length, bEnd = bLength, aStart = 0, bStart = 0, after = getNextSibling(a[aEnd - 1]), map = null;
    while (aStart < aEnd || bStart < bEnd) {
      if (a[aStart] === b[bStart]) {
        aStart++;
        bStart++;
        continue;
      }
      while (a[aEnd - 1] === b[bEnd - 1]) {
        aEnd--;
        bEnd--;
      }
      if (aEnd === aStart) {
        const node = bEnd < bLength ? bStart ? getNextSibling(b[bStart - 1]) : b[bEnd - bStart] : after;
        while (bStart < bEnd)
          insertNode(parentNode, b[bStart++], node);
      } else if (bEnd === bStart) {
        while (aStart < aEnd) {
          if (!map || !map.has(a[aStart]))
            removeNode(parentNode, a[aStart]);
          aStart++;
        }
      } else if (a[aStart] === b[bEnd - 1] && b[bStart] === a[aEnd - 1]) {
        const node = getNextSibling(a[--aEnd]);
        insertNode(parentNode, b[bStart++], getNextSibling(a[aStart++]));
        insertNode(parentNode, b[--bEnd], node);
        a[aEnd] = b[bEnd];
      } else {
        if (!map) {
          map = new Map;
          let i = bStart;
          while (i < bEnd)
            map.set(b[i], i++);
        }
        const index = map.get(a[aStart]);
        if (index != null) {
          if (bStart < index && index < bEnd) {
            let i = aStart, sequence = 1, t;
            while (++i < aEnd && i < bEnd) {
              if ((t = map.get(a[i])) == null || t !== index + sequence)
                break;
              sequence++;
            }
            if (sequence > index - bStart) {
              const node = a[aStart];
              while (bStart < index)
                insertNode(parentNode, b[bStart++], node);
            } else
              replaceNode(parentNode, b[bStart++], a[aStart++]);
          } else
            aStart++;
        } else
          removeNode(parentNode, a[aStart++]);
      }
    }
  }
  function cleanChildren(parent, current, marker, replacement) {
    if (marker === undefined) {
      let removed;
      while (removed = getFirstChild(parent))
        removeNode(parent, removed);
      replacement && insertNode(parent, replacement);
      return replacement ?? "";
    }
    const node = replacement || createSlotNode();
    if (current.length) {
      let inserted = false;
      for (let i = current.length - 1;i >= 0; i--) {
        const el = current[i];
        if (node !== el) {
          const isParent = getParentNode(el) === parent;
          if (!inserted && !i)
            isParent ? replaceNode(parent, node, el) : insertNode(parent, node, marker);
          else
            isParent && removeNode(parent, el);
        } else
          inserted = true;
      }
    } else
      insertNode(parent, node, marker);
    return [node];
  }
  function appendNodes(parent, array, marker) {
    for (let i = 0, len = array.length;i < len; i++)
      insertNode(parent, array[i], marker);
  }
  function replaceNode(parent, newNode, oldNode) {
    insertNode(parent, newNode, oldNode);
    removeNode(parent, oldNode);
  }
  function spreadExpression(node, props, prevProps = {}, skipChildren) {
    props || (props = {});
    if (!skipChildren) {
      createRenderEffect(() => prevProps.children = insertExpression(node, props.children, prevProps.children));
    }
    createRenderEffect(() => props.ref && props.ref(node));
    createRenderEffect(() => {
      for (const prop in props) {
        if (prop === "children" || prop === "ref")
          continue;
        const value = props[prop];
        if (value === prevProps[prop])
          continue;
        setProperty(node, prop, value, prevProps[prop]);
        prevProps[prop] = value;
      }
    });
    return prevProps;
  }
  return {
    render(code, element) {
      let disposer;
      createRoot((dispose) => {
        disposer = dispose;
        insert(element, code());
      });
      return disposer;
    },
    insert,
    spread(node, accessor, skipChildren) {
      if (typeof accessor === "function") {
        createRenderEffect((current) => spreadExpression(node, accessor(), current, skipChildren));
      } else
        spreadExpression(node, accessor, undefined, skipChildren);
    },
    createElement,
    createTextNode,
    insertNode,
    setProp(node, name, value, prev) {
      setProperty(node, name, value, prev);
      return value;
    },
    mergeProps,
    effect: createRenderEffect,
    memo,
    createComponent,
    use(fn, element, arg) {
      return untrack(() => fn(element, arg));
    }
  };
}

// src/renderer/index.ts
import { mergeProps as mergeProps2 } from "solid-js";
function createRenderer2(options) {
  const renderer = createRenderer(options);
  renderer.mergeProps = mergeProps2;
  return renderer;
}

// src/utils/id-counter.ts
var idCounter = new Map;
function getNextId(elementType) {
  if (!idCounter.has(elementType)) {
    idCounter.set(elementType, 0);
  }
  const value = idCounter.get(elementType) + 1;
  idCounter.set(elementType, value);
  return `${elementType}-${value}`;
}

// src/utils/log.ts
var log = (...args) => {
  if (process.env.DEBUG) {
    console.log("[Reconciler]", ...args);
  }
};

// src/reconciler.ts
class TextNode extends TextNodeRenderable {
  static fromString(text, options = {}) {
    const node = new TextNode(options);
    node.add(text);
    return node;
  }
}
var logId = (node) => {
  if (!node)
    return;
  return node.id;
};
var getNodeChildren = (node) => {
  let children;
  if (node instanceof TextRenderable) {
    children = node.getTextChildren();
  } else {
    children = node.getChildren();
  }
  return children;
};
function _insertNode(parent, node, anchor) {
  log("Inserting node:", logId(node), "into parent:", logId(parent), "with anchor:", logId(anchor), node instanceof TextNode);
  if (node instanceof SlotRenderable) {
    node.parent = parent;
    node = node.getSlotChild(parent);
  }
  if (anchor && anchor instanceof SlotRenderable) {
    anchor = anchor.getSlotChild(parent);
  }
  if (isTextNodeRenderable(node)) {
    if (!(parent instanceof TextRenderable) && !isTextNodeRenderable(parent)) {
      throw new Error(`Orphan text error: "${node.toChunks().map((c) => c.text).join("")}" must have a <text> as a parent: ${parent.id} above ${node.id}`);
    }
  }
  if (!(parent instanceof BaseRenderable)) {
    console.error("[INSERT]", "Tried to mount a non base renderable");
    throw new Error("Tried to mount a non base renderable");
  }
  if (!anchor) {
    parent.add(node);
    return;
  }
  const children = getNodeChildren(parent);
  const anchorIndex = children.findIndex((el) => el.id === anchor.id);
  if (anchorIndex === -1) {
    log("[INSERT]", "Could not find anchor", logId(parent), logId(anchor), "[children]", ...children.map((c) => c.id));
  }
  parent.add(node, anchorIndex);
}
function _removeNode(parent, node) {
  log("Removing node:", logId(node), "from parent:", logId(parent));
  if (node instanceof SlotRenderable) {
    node.parent = null;
    node = node.getSlotChild(parent);
  }
  parent.remove(node.id);
  process.nextTick(() => {
    if (node instanceof BaseRenderable && !node.parent) {
      node.destroyRecursively();
      return;
    }
  });
}
function _createTextNode(value) {
  log("Creating text node:", value);
  const id = getNextId("text-node");
  if (typeof value === "number") {
    value = value.toString();
  }
  return TextNode.fromString(value, { id });
}
function createSlotNode() {
  const id = getNextId("slot-node");
  log("Creating slot node", id);
  return new SlotRenderable(id);
}
function _getParentNode(childNode) {
  log("Getting parent of node:", logId(childNode));
  let parent = childNode.parent ?? undefined;
  if (parent instanceof RootTextNodeRenderable) {
    parent = parent.textParent ?? undefined;
  }
  const scrollBoxCandidate = parent?.parent?.parent?.parent;
  if (scrollBoxCandidate instanceof ScrollBoxRenderable && scrollBoxCandidate.content === parent) {
    parent = scrollBoxCandidate;
  }
  return parent;
}
var {
  render: _render,
  effect,
  memo: memo2,
  createComponent: createComponent2,
  createElement,
  createTextNode,
  insertNode,
  insert,
  spread,
  setProp,
  mergeProps: mergeProps3,
  use
} = createRenderer2({
  createElement(tagName) {
    log("Creating element:", tagName);
    const id = getNextId(tagName);
    const solidRenderer = useContext2(RendererContext);
    if (!solidRenderer) {
      throw new Error("No renderer found");
    }
    const elements = getComponentCatalogue();
    if (!elements[tagName]) {
      throw new Error(`[Reconciler] Unknown component type: ${tagName}`);
    }
    const element = new elements[tagName](solidRenderer, { id });
    log("Element created with id:", id);
    return element;
  },
  createTextNode: _createTextNode,
  createSlotNode,
  replaceText(textNode, value) {
    log("Replacing text:", value, "in node:", logId(textNode));
    if (!(textNode instanceof TextNode))
      return;
    textNode.replace(value, 0);
  },
  setProperty(node, name, value, prev) {
    if (name.startsWith("on:")) {
      const eventName = name.slice(3);
      if (value) {
        node.on(eventName, value);
      }
      if (prev) {
        node.off(eventName, prev);
      }
      return;
    }
    if (isTextNodeRenderable(node)) {
      if (name === "href") {
        node.link = { url: value };
        return;
      }
      if (name === "style") {
        node.attributes |= createTextAttributes(value);
        node.fg = value.fg ? parseColor(value.fg) : node.fg;
        node.bg = value.bg ? parseColor(value.bg) : node.bg;
        return;
      }
      return;
    }
    switch (name) {
      case "id":
        log("Id mapped", node.id, "=", value);
        node[name] = value;
        break;
      case "focused":
        if (!(node instanceof Renderable))
          return;
        if (value) {
          node.focus();
        } else {
          node.blur();
        }
        break;
      case "onChange":
        let event = undefined;
        if (node instanceof SelectRenderable) {
          event = SelectRenderableEvents.SELECTION_CHANGED;
        } else if (node instanceof TabSelectRenderable) {
          event = TabSelectRenderableEvents.SELECTION_CHANGED;
        } else if (node instanceof InputRenderable) {
          event = InputRenderableEvents.CHANGE;
        }
        if (!event)
          break;
        if (value) {
          node.on(event, value);
        }
        if (prev) {
          node.off(event, prev);
        }
        break;
      case "onInput":
        if (node instanceof InputRenderable) {
          if (value) {
            node.on(InputRenderableEvents.INPUT, value);
          }
          if (prev) {
            node.off(InputRenderableEvents.INPUT, prev);
          }
        }
        break;
      case "onSubmit":
        if (node instanceof InputRenderable) {
          if (value) {
            node.on(InputRenderableEvents.ENTER, value);
          }
          if (prev) {
            node.off(InputRenderableEvents.ENTER, prev);
          }
        } else {
          node[name] = value;
        }
        break;
      case "onSelect":
        if (node instanceof SelectRenderable) {
          if (value) {
            node.on(SelectRenderableEvents.ITEM_SELECTED, value);
          }
          if (prev) {
            node.off(SelectRenderableEvents.ITEM_SELECTED, prev);
          }
        } else if (node instanceof TabSelectRenderable) {
          if (value) {
            node.on(TabSelectRenderableEvents.ITEM_SELECTED, value);
          }
          if (prev) {
            node.off(TabSelectRenderableEvents.ITEM_SELECTED, prev);
          }
        }
        break;
      case "style":
        for (const prop in value) {
          const propVal = value[prop];
          if (prev !== undefined && propVal === prev[prop])
            continue;
          node[prop] = propVal;
        }
        break;
      case "text":
      case "content":
        node[name] = typeof value === "string" ? value : Array.isArray(value) ? value.join("") : `${value}`;
        break;
      default:
        node[name] = value;
    }
  },
  isTextNode(node) {
    return node instanceof TextNode;
  },
  insertNode: _insertNode,
  removeNode: _removeNode,
  getParentNode: _getParentNode,
  getFirstChild(node) {
    log("Getting first child of node:", logId(node));
    const firstChild = getNodeChildren(node)[0];
    if (!firstChild) {
      log("No first child found for node:", logId(node));
      return;
    }
    log("First child found:", logId(firstChild), "for node:", logId(node));
    return firstChild;
  },
  getNextSibling(node) {
    log("Getting next sibling of node:", logId(node));
    const parent = _getParentNode(node);
    if (!parent) {
      log("No parent found for node:", logId(node));
      return;
    }
    const siblings = getNodeChildren(parent);
    const index = siblings.indexOf(node);
    if (index === -1 || index === siblings.length - 1) {
      log("No next sibling found for node:", logId(node));
      return;
    }
    const nextSibling = siblings[index + 1];
    if (!nextSibling) {
      log("Next sibling is null for node:", logId(node));
      return;
    }
    log("Next sibling found:", logId(nextSibling), "for node:", logId(node));
    return nextSibling;
  }
});

// src/elements/extras.ts
function Portal(props) {
  const renderer = useRenderer();
  const marker = createSlotNode(), mount = () => props.mount || renderer.root, owner = getOwner();
  let content;
  createEffect(() => {
    content || (content = runWithOwner(owner, () => createMemo2(() => props.children)));
    const el = mount();
    const container = createElement("box"), renderRoot = container;
    Object.defineProperty(container, "_$host", {
      get() {
        return marker.parent;
      },
      configurable: true
    });
    insert(renderRoot, content);
    el.add(container);
    props.ref && props.ref(container);
    onCleanup2(() => el.remove(container.id));
  }, undefined, { render: true });
  return marker;
}
function createDynamic(component, props) {
  const cached = createMemo2(component);
  return createMemo2(() => {
    const component2 = cached();
    switch (typeof component2) {
      case "function":
        return untrack2(() => component2(props));
      case "string":
        const el = createElement(component2);
        spread(el, props);
        return el;
      default:
        break;
    }
  });
}
function Dynamic(props) {
  const [, others] = splitProps(props, ["component"]);
  return createDynamic(() => props.component, others);
}
// src/elements/slot.ts
import { BaseRenderable as BaseRenderable2, isTextNodeRenderable as isTextNodeRenderable2, TextNodeRenderable as TextNodeRenderable2, TextRenderable as TextRenderable2, Yoga } from "@opentui/core";

class SlotBaseRenderable extends BaseRenderable2 {
  constructor(id) {
    super({
      id
    });
  }
  add(obj, index) {
    throw new Error("Can't add children on an Slot renderable");
  }
  getChildren() {
    return [];
  }
  remove(id) {}
  insertBefore(obj, anchor) {
    throw new Error("Can't add children on an Slot renderable");
  }
  getRenderable(id) {
    return;
  }
  getChildrenCount() {
    return 0;
  }
  requestRender() {}
  findDescendantById(id) {
    return;
  }
}

class TextSlotRenderable extends TextNodeRenderable2 {
  slotParent;
  destroyed = false;
  constructor(id, parent) {
    super({ id });
    this._visible = false;
    this.slotParent = parent;
  }
  destroy() {
    if (this.destroyed) {
      return;
    }
    this.destroyed = true;
    this.slotParent?.destroy();
    super.destroy();
  }
}

class LayoutSlotRenderable extends SlotBaseRenderable {
  yogaNode;
  slotParent;
  destroyed = false;
  constructor(id, parent) {
    super(id);
    this._visible = false;
    this.slotParent = parent;
    this.yogaNode = Yoga.default.Node.create();
    this.yogaNode.setDisplay(Yoga.Display.None);
  }
  getLayoutNode() {
    return this.yogaNode;
  }
  updateFromLayout() {}
  updateLayout() {}
  onRemove() {}
  destroy() {
    if (this.destroyed) {
      return;
    }
    this.destroyed = true;
    super.destroy();
    this.slotParent?.destroy();
  }
}

class SlotRenderable extends SlotBaseRenderable {
  layoutNode;
  textNode;
  destroyed = false;
  constructor(id) {
    super(id);
    this._visible = false;
  }
  getSlotChild(parent) {
    if (isTextNodeRenderable2(parent) || parent instanceof TextRenderable2) {
      if (!this.textNode) {
        this.textNode = new TextSlotRenderable(`slot-text-${this.id}`, this);
      }
      return this.textNode;
    }
    if (!this.layoutNode) {
      this.layoutNode = new LayoutSlotRenderable(`slot-layout-${this.id}`, this);
    }
    return this.layoutNode;
  }
  destroy() {
    if (this.destroyed) {
      return;
    }
    this.destroyed = true;
    if (this.layoutNode) {
      this.layoutNode.destroy();
    }
    if (this.textNode) {
      this.textNode.destroy();
    }
  }
}

// src/elements/index.ts
class SpanRenderable extends TextNodeRenderable3 {
  _ctx;
  constructor(_ctx, options) {
    super(options);
    this._ctx = _ctx;
  }
}
var textNodeKeys = ["span", "b", "strong", "i", "em", "u", "a"];

class TextModifierRenderable extends SpanRenderable {
  constructor(options, modifier) {
    super(null, options);
    if (modifier === "b" || modifier === "strong") {
      this.attributes = (this.attributes || 0) | TextAttributes.BOLD;
    } else if (modifier === "i" || modifier === "em") {
      this.attributes = (this.attributes || 0) | TextAttributes.ITALIC;
    } else if (modifier === "u") {
      this.attributes = (this.attributes || 0) | TextAttributes.UNDERLINE;
    }
  }
}

class BoldSpanRenderable extends TextModifierRenderable {
  constructor(options) {
    super(options, "b");
  }
}

class ItalicSpanRenderable extends TextModifierRenderable {
  constructor(options) {
    super(options, "i");
  }
}

class UnderlineSpanRenderable extends TextModifierRenderable {
  constructor(options) {
    super(options, "u");
  }
}

class LineBreakRenderable extends SpanRenderable {
  constructor(_ctx, options) {
    super(null, options);
    this.add();
  }
  add() {
    return super.add(`
`);
  }
}

class LinkRenderable extends SpanRenderable {
  constructor(_ctx, options) {
    const linkOptions = {
      ...options,
      link: { url: options.href }
    };
    super(null, linkOptions);
  }
}
var baseComponents = {
  box: BoxRenderable,
  text: TextRenderable3,
  input: InputRenderable2,
  select: SelectRenderable2,
  textarea: TextareaRenderable,
  ascii_font: ASCIIFontRenderable,
  tab_select: TabSelectRenderable2,
  scrollbox: ScrollBoxRenderable2,
  code: CodeRenderable,
  diff: DiffRenderable,
  line_number: LineNumberRenderable,
  markdown: MarkdownRenderable,
  span: SpanRenderable,
  strong: BoldSpanRenderable,
  b: BoldSpanRenderable,
  em: ItalicSpanRenderable,
  i: ItalicSpanRenderable,
  u: UnderlineSpanRenderable,
  br: LineBreakRenderable,
  a: LinkRenderable
};
var componentCatalogue = { ...baseComponents };
function extend(objects) {
  Object.assign(componentCatalogue, objects);
}
function getComponentCatalogue() {
  return componentCatalogue;
}

// index.ts
var render = async (node, rendererOrConfig = {}) => {
  let isDisposed = false;
  let dispose;
  const renderer = rendererOrConfig instanceof CliRenderer ? rendererOrConfig : await createCliRenderer({
    ...rendererOrConfig,
    onDestroy: () => {
      if (!isDisposed) {
        isDisposed = true;
        dispose();
      }
      rendererOrConfig.onDestroy?.();
    }
  });
  if (rendererOrConfig instanceof CliRenderer) {
    renderer.on("destroy", () => {
      if (!isDisposed) {
        isDisposed = true;
        dispose();
      }
    });
  }
  engine2.attach(renderer);
  dispose = _render(() => createComponent2(RendererContext.Provider, {
    get value() {
      return renderer;
    },
    get children() {
      return createComponent2(node, {});
    }
  }), renderer.root);
};
var testRender = async (node, renderConfig = {}) => {
  let isDisposed = false;
  const testSetup = await createTestRenderer({
    ...renderConfig,
    onDestroy: () => {
      if (!isDisposed) {
        isDisposed = true;
        dispose();
      }
      renderConfig.onDestroy?.();
    }
  });
  engine2.attach(testSetup.renderer);
  const dispose = _render(() => createComponent2(RendererContext.Provider, {
    get value() {
      return testSetup.renderer;
    },
    get children() {
      return createComponent2(node, {});
    }
  }), testSetup.renderer.root);
  return testSetup;
};
export {
  useTimeline,
  useTerminalDimensions,
  useSelectionHandler,
  useRenderer,
  usePaste,
  useKeyboard,
  useKeyHandler,
  use,
  textNodeKeys,
  testRender,
  spread,
  setProp,
  render,
  onResize,
  mergeProps3 as mergeProps,
  memo2 as memo,
  insertNode,
  insert,
  getComponentCatalogue,
  extend,
  effect,
  createTextNode,
  createSlotNode,
  createElement,
  createDynamic,
  createComponent2 as createComponent,
  componentCatalogue,
  baseComponents,
  _render,
  UnderlineSpanRenderable,
  TextSlotRenderable,
  SlotRenderable,
  RendererContext,
  Portal,
  LinkRenderable,
  LineBreakRenderable,
  LayoutSlotRenderable,
  ItalicSpanRenderable,
  Dynamic,
  BoldSpanRenderable
};
