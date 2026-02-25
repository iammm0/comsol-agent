import { CliRenderer, type CliRendererConfig } from "@opentui/core";
import { type TestRendererOptions } from "@opentui/core/testing";
import type { JSX } from "./jsx-runtime";
export declare const render: (node: () => JSX.Element, rendererOrConfig?: CliRenderer | CliRendererConfig) => Promise<void>;
export declare const testRender: (node: () => JSX.Element, renderConfig?: TestRendererOptions) => Promise<{
    renderer: import("@opentui/core/testing").TestRenderer;
    mockInput: import("@opentui/core/testing").MockInput;
    mockMouse: import("@opentui/core/testing").MockMouse;
    renderOnce: () => Promise<void>;
    captureCharFrame: () => string;
    captureSpans: () => import("@opentui/core").CapturedFrame;
    resize: (width: number, height: number) => void;
}>;
export * from "./src/reconciler";
export * from "./src/elements";
export * from "./src/types/elements";
export { type JSX };
