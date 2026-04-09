/**
 * 清理流式输出中常见的转义残片/未完成 JSON 片段，避免污染消息展示。
 */
export function sanitizeLLMDisplayText(input: string): string {
  if (!input) return "";

  let text = input.replace(/\r\n?/g, "\n");

  // 常见后端双重转义残片
  text = text.replace(/\\n/g, "\n").replace(/\\t/g, "\t").replace(/\\"/g, '"');

  // 去掉整段被包裹的多余引号（保留正文）
  if (text.startsWith('"') && text.endsWith('"') && text.length > 1) {
    text = text.slice(1, -1);
  }

  const lines = text.split("\n");
  const filtered = lines.filter((line) => {
    const t = line.trim();
    if (!t) return true;

    // 类似 "\"steps\""、"\"steps\":"、"{", "}", "," 这类碎片直接忽略
    if (/^[\[\]{}(),]+$/.test(t)) return false;
    if (/^\\*"?[A-Za-z0-9_-]+"?\s*:?$/.test(t)) return false;
    if (/^\\*"\s*[A-Za-z0-9_-]+\s*"\\*,?$/.test(t)) return false;

    return true;
  });

  // 折叠过多空行
  const compact = filtered.join("\n").replace(/\n{3,}/g, "\n\n").trim();
  return compact;
}
