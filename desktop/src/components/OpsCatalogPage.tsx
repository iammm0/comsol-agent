import { useCallback, useEffect, useMemo, useState } from "react";
import type { OpsCatalogItem } from "../lib/types";
import { fetchOpsCatalog } from "../lib/opsCatalog";

type ModeFilter = "all" | OpsCatalogItem["invoke_mode"];

function getOpKey(item: OpsCatalogItem): string {
  return `${item.invoke_mode}:${item.category}:${item.label}:${item.recommended_action}`;
}

function getModeLabel(mode: OpsCatalogItem["invoke_mode"]): string {
  return mode === "native" ? "原生 Action" : "Wrapper 包装";
}

function getModeHint(mode: OpsCatalogItem["invoke_mode"]): string {
  return mode === "native"
    ? "由 Agent 直接调度的高层原生建模动作。"
    : "通过官方 API 包装层暴露出的底层调用入口。";
}

function countSchemaFields(schema: OpsCatalogItem["params_schema"]): number {
  return schema && typeof schema === "object" ? Object.keys(schema).length : 0;
}

function formatSchemaValue(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function buildSearchText(item: OpsCatalogItem): string {
  return [
    item.category,
    item.label,
    item.invoke_mode,
    item.recommended_action,
    item.params_schema ? JSON.stringify(item.params_schema) : "",
    item.examples ? JSON.stringify(item.examples) : "",
  ]
    .join(" ")
    .toLowerCase();
}

export function OpsCatalogPage() {
  const [items, setItems] = useState<OpsCatalogItem[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("全部");
  const [mode, setMode] = useState<ModeFilter>("all");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const loadCatalog = useCallback(async () => {
    setLoading(true);
    setError(null);

    const result = await fetchOpsCatalog({ limit: 0, offset: 0 });
    if (!result.ok) {
      setItems([]);
      setCategories([]);
      setError(result.message || "加载操作清单失败");
      setLoading(false);
      return;
    }

    setItems(result.items);
    setCategories(result.categories);
    setLoading(false);
  }, []);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return items.filter((item) => {
      if (category !== "全部" && item.category !== category) return false;
      if (mode !== "all" && item.invoke_mode !== mode) return false;
      if (!normalizedQuery) return true;
      return buildSearchText(item).includes(normalizedQuery);
    });
  }, [items, query, category, mode]);

  const grouped = useMemo(() => {
    const map = new Map<string, OpsCatalogItem[]>();

    for (const item of filtered) {
      const key = item.category || "未分类";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(item);
    }

    const orderedCategories = categories.length > 0 ? categories : Array.from(map.keys());
    const groups = orderedCategories
      .map((groupName) => ({
        category: groupName,
        items: map.get(groupName) ?? [],
      }))
      .filter((group) => group.items.length > 0);

    const extraGroups = Array.from(map.entries())
      .filter(([groupName]) => !orderedCategories.includes(groupName))
      .map(([groupName, groupItems]) => ({ category: groupName, items: groupItems }));

    return [...groups, ...extraGroups];
  }, [filtered, categories]);

  useEffect(() => {
    if (filtered.length === 0) {
      setSelectedKey(null);
      return;
    }

    const selectedStillVisible = filtered.some((item) => getOpKey(item) === selectedKey);
    if (!selectedStillVisible) {
      setSelectedKey(getOpKey(filtered[0]));
    }
  }, [filtered, selectedKey]);

  const selectedItem = useMemo(
    () => filtered.find((item) => getOpKey(item) === selectedKey) ?? null,
    [filtered, selectedKey]
  );

  const nativeCount = useMemo(
    () => items.filter((item) => item.invoke_mode === "native").length,
    [items]
  );
  const wrapperCount = items.length - nativeCount;
  const categoryCount = useMemo(() => new Set(items.map((item) => item.category)).size, [items]);

  return (
    <div className="ops-catalog-page">
      <div className="library-page-header">
        <div>
          <h2 className="library-page-title">COMSOL 可执行操作清单</h2>
          <p className="library-page-desc">
            这里只统计当前 Agent 可以直接对 COMSOL 执行的操作，不包含聊天、设置或导航命令。
            清单覆盖高层 native action 和官方 API wrapper，两类都会逐条展示。
          </p>
        </div>
        <div className="library-page-actions">
          <button type="button" className="dialog-btn secondary" onClick={() => setQuery(searchInput.trim())}>
            搜索
          </button>
          <button
            type="button"
            className="dialog-btn secondary"
            onClick={() => {
              setSearchInput("");
              setQuery("");
              setCategory("全部");
              setMode("all");
            }}
          >
            清空筛选
          </button>
          <button type="button" className="dialog-btn primary" onClick={() => void loadCatalog()} disabled={loading}>
            {loading ? "刷新中..." : "刷新清单"}
          </button>
        </div>
      </div>

      <div className="ops-summary-grid">
        <div className="ops-summary-card">
          <span className="ops-summary-card__label">全部 COMSOL 操作</span>
          <strong>{items.length}</strong>
          <span className="ops-summary-card__hint">可直接作用于 COMSOL 的全量目录</span>
        </div>
        <div className="ops-summary-card">
          <span className="ops-summary-card__label">原生建模 Action</span>
          <strong>{nativeCount}</strong>
          <span className="ops-summary-card__hint">由 Agent 直接编排的高层 COMSOL 动作</span>
        </div>
        <div className="ops-summary-card">
          <span className="ops-summary-card__label">官方 API Wrapper</span>
          <strong>{wrapperCount}</strong>
          <span className="ops-summary-card__hint">通过官方 API 包装层暴露的调用能力</span>
        </div>
        <div className="ops-summary-card">
          <span className="ops-summary-card__label">分类数量</span>
          <strong>{categoryCount}</strong>
          <span className="ops-summary-card__hint">定义、几何、材料、物理场等</span>
        </div>
      </div>

      <div className="ops-toolbar">
        <input
          className="case-library-search"
          type="text"
          placeholder="搜索 category / label / action / param..."
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              setQuery(searchInput.trim());
            }
          }}
        />
        <select className="case-library-category" value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="全部">全部分类</option>
          {categories.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          className="case-library-category"
          value={mode}
          onChange={(event) => setMode(event.target.value as ModeFilter)}
        >
          <option value="all">全部模式</option>
          <option value="native">原生 Action</option>
          <option value="wrapper">Wrapper 包装</option>
        </select>
      </div>

      {error && <div className="skills-banner skills-banner--error">{error}</div>}

      {loading ? (
        <div className="case-library-empty">正在加载操作清单...</div>
      ) : filtered.length === 0 ? (
        <div className="case-library-empty">当前筛选条件下没有匹配的操作。</div>
      ) : (
        <div className="ops-layout">
          <section className="ops-list-panel">
            <div className="ops-list-panel__head">
              <div>
                <h3 className="ops-section-title">COMSOL 操作目录</h3>
                <p className="ops-section-copy">
                  当前显示 {filtered.length} / {items.length} 条。左侧每一条都是当前可直接执行到 COMSOL 的真实操作。
                </p>
              </div>
            </div>

            <div className="ops-list-scroll">
              {grouped.map((group) => (
                <section key={group.category} className="ops-category-block">
                  <div className="ops-category-title">
                    <span>{group.category}</span>
                    <span>{group.items.length}</span>
                  </div>
                  <div className="ops-item-list">
                    {group.items.map((item) => {
                      const itemKey = getOpKey(item);
                      const schemaCount = countSchemaFields(item.params_schema);
                      const exampleCount = Array.isArray(item.examples) ? item.examples.length : 0;
                      const active = itemKey === selectedKey;

                      return (
                        <button
                          key={itemKey}
                          type="button"
                          className={`ops-item-card ${active ? "is-active" : ""}`}
                          onClick={() => setSelectedKey(itemKey)}
                        >
                          <div className="ops-item-card__head">
                            <div className="ops-item-card__body">
                              <span className="ops-item-card__title">{item.label}</span>
                              <span className="ops-item-card__action">{item.recommended_action}</span>
                            </div>
                            <span className={`ops-mode-chip ops-mode-chip--${item.invoke_mode}`}>
                              {getModeLabel(item.invoke_mode)}
                            </span>
                          </div>
                          <div className="ops-item-card__meta">
                            <span>{group.category}</span>
                            <span>参数 {schemaCount}</span>
                            <span>示例 {exampleCount}</span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>
          </section>

          <aside className="ops-detail-panel">
            {selectedItem ? (
              <>
                <div className="ops-detail-head">
                  <div>
                    <span className="skills-page-kicker">操作详情</span>
                    <h3 className="skills-page-title">{selectedItem.label}</h3>
                    <p className="skills-page-desc">
                      {selectedItem.category} · {getModeHint(selectedItem.invoke_mode)}
                    </p>
                  </div>
                  <span className={`ops-mode-chip ops-mode-chip--${selectedItem.invoke_mode}`}>
                    {getModeLabel(selectedItem.invoke_mode)}
                  </span>
                </div>

                <div className="ops-detail-stats">
                  <div className="ops-detail-stat">
                    <span className="ops-detail-stat__label">分类</span>
                    <strong>{selectedItem.category}</strong>
                  </div>
                  <div className="ops-detail-stat">
                    <span className="ops-detail-stat__label">推荐 Action</span>
                    <strong>{selectedItem.recommended_action}</strong>
                  </div>
                  <div className="ops-detail-stat">
                    <span className="ops-detail-stat__label">参数项数</span>
                    <strong>{countSchemaFields(selectedItem.params_schema)}</strong>
                  </div>
                </div>

                <section className="ops-detail-section">
                  <h4>参数清单</h4>
                  {selectedItem.params_schema && Object.keys(selectedItem.params_schema).length > 0 ? (
                    <div className="ops-schema-list">
                      {Object.entries(selectedItem.params_schema).map(([name, value]) => (
                        <div key={name} className="ops-schema-item">
                          <span className="ops-schema-item__name">{name}</span>
                          <code className="ops-schema-item__value">{formatSchemaValue(value)}</code>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="ops-detail-empty">当前操作没有记录参数 schema。</p>
                  )}
                </section>

                <section className="ops-detail-section">
                  <h4>调用示例</h4>
                  {Array.isArray(selectedItem.examples) && selectedItem.examples.length > 0 ? (
                    <div className="ops-example-list">
                      {selectedItem.examples.map((example, index) => (
                        <pre key={`${getOpKey(selectedItem)}-example-${index}`} className="ops-json-block">
                          {JSON.stringify(example, null, 2)}
                        </pre>
                      ))}
                    </div>
                  ) : (
                    <p className="ops-detail-empty">当前操作没有记录调用示例。</p>
                  )}
                </section>
              </>
            ) : (
              <div className="case-library-empty">请选择一条操作查看详细信息。</div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
