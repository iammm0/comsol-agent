import { useCallback, useEffect, useMemo, useState } from "react";
import { useAppState } from "../context/AppStateContext";
import { fetchCaseLibrary, type CaseLibraryItem } from "../lib/caseLibrary";

function buildParsePrompt(item: CaseLibraryItem): string {
  return [
    `请解析这个 COMSOL 官方案例，并给出可复现的建模步骤与关键参数：`,
    `案例标题：${item.title}`,
    `案例分类：${item.category}`,
    `官方链接：${item.officialUrl}`,
    `下载链接：${item.downloadUrl}`,
    `补充要求：`,
    `1. 先说明物理场接口和耦合关系`,
    `2. 再给出几何、材料、边界条件、研究类型`,
    `3. 最后给出在本项目里可直接执行的建模指令草案`,
  ].join("\n");
}

export function CaseLibraryPage() {
  const { dispatch } = useAppState();
  const [items, setItems] = useState<CaseLibraryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState("全部");

  const loadCases = useCallback(async () => {
    setLoading(true);
    const list = await fetchCaseLibrary();
    setItems(list);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadCases();
  }, [loadCases]);

  const categories = useMemo(() => {
    const set = new Set<string>(["全部"]);
    items.forEach((item) => set.add(item.category));
    return Array.from(set);
  }, [items]);

  const filtered = useMemo(() => {
    const q = keyword.trim().toLowerCase();
    return items.filter((item) => {
      if (category !== "全部" && item.category !== category) return false;
      if (!q) return true;
      const haystack = `${item.title} ${item.summary} ${item.tags.join(" ")}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [items, keyword, category]);

  const handleOpen = useCallback((url: string) => {
    window.open(url, "_blank", "noopener,noreferrer");
  }, []);

  const handleQuickParse = useCallback(
    (item: CaseLibraryItem) => {
      dispatch({ type: "SET_MODE", mode: "plan" });
      dispatch({ type: "SET_EDITING_DRAFT", text: buildParsePrompt(item) });
      dispatch({ type: "SET_VIEW", view: "session" });
    },
    [dispatch]
  );

  return (
    <div className="case-library">
      <div className="case-library-toolbar">
        <input
          className="case-library-search"
          type="text"
          placeholder="搜索案例标题/标签..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <select
          className="case-library-category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat}
            </option>
          ))}
        </select>
        <button type="button" className="dialog-btn secondary" onClick={loadCases} disabled={loading}>
          {loading ? "刷新中..." : "刷新"}
        </button>
      </div>

      <div className="case-library-list">
        {loading && items.length === 0 && <div className="case-library-empty">正在加载案例库...</div>}
        {!loading && filtered.length === 0 && <div className="case-library-empty">未找到匹配案例</div>}
        {filtered.map((item) => (
          <article key={item.id} className="case-card">
            <div className="case-card-head">
              <h3 className="case-card-title">{item.title}</h3>
              <span className="case-card-category">{item.category}</span>
            </div>
            <p className="case-card-summary">{item.summary}</p>
            <div className="case-card-tags">
              {item.tags.map((tag) => (
                <span className="case-card-tag" key={tag}>
                  {tag}
                </span>
              ))}
            </div>
            <div className="case-card-actions">
              <button type="button" className="dialog-btn secondary" onClick={() => handleOpen(item.officialUrl)}>
                查看详情
              </button>
              <button type="button" className="dialog-btn secondary" onClick={() => handleOpen(item.downloadUrl)}>
                下载案例
              </button>
              <button type="button" className="dialog-btn primary" onClick={() => handleQuickParse(item)}>
                一键跳转解析
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
