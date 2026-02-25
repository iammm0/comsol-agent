"""基于 SQLite + sqlite-vec 的技能持久化与向量检索（VSS）。"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

from agent.utils.config import get_project_root
from agent.utils.logger import get_logger

logger = get_logger(__name__)

# 默认向量维度（sentence-transformers all-MiniLM-L6-v2 / paraphrase-multilingual-MiniLM 等常用 384）
DEFAULT_VECTOR_DIM = 384

# 单条 content 最大长度（避免 SQLite 与 vec0 元数据过大）
MAX_CONTENT_LEN = 32_000


def _get_default_db_path() -> Path:
    """默认 DB 路径：项目根目录下 data/skills.db。"""
    root = get_project_root()
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "skills.db"


def _load_sqlite_vec(conn: sqlite3.Connection) -> None:
    """加载 sqlite-vec 扩展。"""
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception as e:
        raise RuntimeError("加载 sqlite-vec 失败，请确认已安装: pip install sqlite-vec") from e


class SkillVectorStore:
    """
    使用 SQLite + sqlite-vec 持久化技能内容并做向量相似度检索（VSS）。
    需配合嵌入模型使用（如 sentence-transformers）；若无嵌入则仅做持久化存储，检索回退到调用方。
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        vector_dim: int = DEFAULT_VECTOR_DIM,
        embedder: Optional[object] = None,
    ):
        self.db_path = Path(db_path) if db_path else _get_default_db_path()
        self.vector_dim = vector_dim
        self._embedder = embedder
        self._connection: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.db_path))
            self._connection.row_factory = sqlite3.Row
            _load_sqlite_vec(self._connection)
        return self._connection

    def _embed(self, text: str) -> Optional[List[float]]:
        """调用嵌入模型得到向量；无模型或失败时返回 None。"""
        if not text or not self._embedder:
            return None
        try:
            # sentence-transformers: .encode(text) -> ndarray
            if hasattr(self._embedder, "encode"):
                emb = self._embedder.encode(text, normalize_embeddings=True)
                return emb.tolist() if hasattr(emb, "tolist") else list(emb)
            return None
        except Exception as e:
            logger.debug("嵌入失败: %s", e)
            return None

    def _ensure_table(self) -> None:
        """创建 vec0 虚拟表（若不存在）。向量列 + 短元数据 skill_name + 长文本用 +content 辅助列。"""
        sql = f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS skill_vec USING vec0(
            embedding float[{self.vector_dim}],
            skill_name text,
            +content text
        );
        """
        self.conn.execute(sql)
        self.conn.commit()

    def index_skills(self, skills: List[object]) -> int:
        """
        将技能列表写入 vec0 并建立向量索引。
        skills 为 Skill 对象列表，需有 .name, .instructions 属性。
        返回写入条数。
        """
        # 全量重建：DROP 后重建，避免 DELETE 不回收 vec0 内部存储（见 sqlite-vec#178/#205）
        self.conn.execute("DROP TABLE IF EXISTS skill_vec")
        self.conn.commit()
        self._ensure_table()

        count = 0
        for s in skills:
            name = getattr(s, "name", "") or ""
            content = (getattr(s, "instructions", "") or "").strip()
            if not content:
                content = (getattr(s, "description", "") or "").strip()
            if len(content) > MAX_CONTENT_LEN:
                content = content[:MAX_CONTENT_LEN] + "\n..."
            embedding = self._embed(content)
            if embedding is None:
                # 无嵌入时仍可存一条“占位”，但无法做向量检索；这里跳过，仅在有嵌入时写入
                continue
            if len(embedding) != self.vector_dim:
                logger.warning("技能 %s 向量维度 %s != %s，跳过", name, len(embedding), self.vector_dim)
                continue
            # vec0 插入：embedding 用 JSON 列表字符串；skill_name 为 metadata，content 为 + 辅助列
            emb_json = json.dumps([float(x) for x in embedding])
            self.conn.execute(
                "INSERT INTO skill_vec(embedding, skill_name, content) VALUES (?, ?, ?)",
                (emb_json, name, content),
            )
            count += 1
        self.conn.commit()
        logger.info("SkillVectorStore 已索引 %s 条技能到 %s", count, self.db_path)
        return count

    def ensure_indexed(self, skills: List[object]) -> bool:
        """
        若表为空且有嵌入模型，则索引全部技能并返回 True；否则返回 False（未做变更）。
        用于首次使用或 DB 清空后自动建索引。
        """
        if not self._embedder or not skills:
            return False
        self._ensure_table()
        try:
            n = self.conn.execute("SELECT COUNT(*) FROM skill_vec").fetchone()[0]
        except sqlite3.OperationalError:
            n = 0
        if n > 0:
            return False
        self.index_skills(skills)
        return True

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, str, float]]:
        """
        向量相似度检索。返回 [(skill_name, content, distance), ...]。
        若无嵌入模型或表中无数据，返回空列表。
        """
        embedding = self._embed(query)
        if embedding is None:
            return []
        emb_json = json.dumps([float(x) for x in embedding])
        try:
            self._ensure_table()
            rows = self.conn.execute(
                """
                SELECT skill_name, content, distance
                FROM skill_vec
                WHERE embedding MATCH ? AND k = ?
                """,
                (emb_json, top_k),
            ).fetchall()
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower() or "empty" in str(e).lower():
                return []
            raise
        result = []
        for r in rows:
            name = r["skill_name"] or ""
            content = r["content"] or ""
            dist = float(r["distance"])
            result.append((name, content, dist))
        return result

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> "SkillVectorStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def get_default_embedder():
    """可选：返回 sentence-transformers 的嵌入模型（安装 vec 可选依赖时可用）。"""
    try:
        from sentence_transformers import SentenceTransformer
        # 小模型、支持中英文
        return SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    except ImportError:
        return None
