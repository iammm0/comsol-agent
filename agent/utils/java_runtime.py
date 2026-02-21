"""内置 Java 运行时：未配置 JAVA_HOME 时使用项目内嵌的 JDK 11（首次使用时自动下载）。"""
import os
import platform
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import unquote
from urllib.request import urlopen, Request

from agent.utils.config import get_install_dir, get_settings
from agent.utils.logger import get_logger

logger = get_logger(__name__)


def ensure_java_home_from_venv(project_root: Path) -> None:
    """
    在导入会触发 JVM/COMSOL 的 agent 模块之前调用：若未设置 JAVA_HOME，
    则尝试使用 project_root/.venv 下的 JDK（如 .venv/Lib/runtime/java 或子目录 jdk-11.x.x）。
    与 scripts/py_to_mph_minimal.py 的 _ensure_java_home 逻辑一致，供 main/cli 等主进程使用。
    """
    if os.environ.get("JAVA_HOME"):
        return
    venv = project_root / ".venv"
    if not venv.is_dir():
        return
    lib = venv / "Lib" if (venv / "Lib").is_dir() else venv / "lib"
    rt_java = lib / "runtime" / "java"
    if not rt_java.is_dir():
        return
    for name in ("java.exe", "java"):
        if (rt_java / "bin" / name).exists():
            os.environ["JAVA_HOME"] = str(rt_java.resolve())
            return
    for sub in sorted(rt_java.iterdir()):
        if sub.is_dir() and ((sub / "bin" / "java.exe").exists() or (sub / "bin" / "java").exists()):
            os.environ["JAVA_HOME"] = str(sub.resolve())
            return

# 项目内嵌 JDK 目录（不提交到 git）
BUNDLED_JAVA_DIR_NAME = "runtime"
JDK_VERSION = 11
ADOPTIUM_BASE = "https://api.adoptium.net/v3/binary/latest"
# 国内镜像：清华 TUNA（可配置 JAVA_DOWNLOAD_MIRROR=tsinghua）
TSINGHUA_MIRROR_BASE = "https://mirrors.tuna.tsinghua.edu.cn/Adoptium"


def _platform_tuple() -> tuple[str, str]:
    """返回 (os, arch) 用于 Adoptium API / 镜像路径。"""
    machine = platform.machine().lower()
    system = platform.system().lower()
    if system == "windows":
        os_name = "windows"
        arch = "x64" if machine in ("amd64", "x86_64", "x64") else "aarch64" if machine == "arm64" else "x64"
    elif system == "darwin":
        os_name = "mac"
        arch = "aarch64" if machine in ("arm64", "aarch64") else "x64"
    else:
        os_name = "linux"
        arch = "aarch64" if machine in ("aarch64", "arm64") else "x64"
    return os_name, arch


def _download_url() -> tuple[str, str]:
    """返回 (下载 URL, 期望扩展名 .zip 或 .tgz)。国内用户可设 JAVA_DOWNLOAD_MIRROR=tsinghua 使用清华镜像。"""
    os_name, arch = _platform_tuple()
    if os_name == "windows":
        archive_type = "zip"
        ext = ".zip"
    else:
        archive_type = "tar.gz"
        ext = ".tar.gz"

    mirror = (get_settings().java_download_mirror or "").strip().lower()
    if mirror == "tsinghua":
        # 先向官方 API 发 HEAD 取重定向后的文件名，再从清华镜像下载同文件名（国内加速）
        api_url = (
            f"{ADOPTIUM_BASE}/{JDK_VERSION}/ga/{os_name}/{arch}/jdk/hotspot/normal/eclipse"
            f"?project=jdk&archive_type={archive_type}"
        )
        try:
            req = Request(api_url, method="HEAD", headers={"User-Agent": "comsol-agent"})
            with urlopen(req, timeout=15) as r:
                final_url = r.geturl()
            filename = unquote(final_url.rstrip("/").split("/")[-1])
            if filename.endswith(ext):
                url = f"{TSINGHUA_MIRROR_BASE}/{JDK_VERSION}/jdk/{arch}/{os_name}/{filename}"
                logger.info("使用清华镜像下载 JDK: %s", url)
                return url, ext
        except Exception as e:
            logger.warning("获取清华镜像文件名失败，回退官方源: %s", e)

    url = (
        f"{ADOPTIUM_BASE}/{JDK_VERSION}/ga/{os_name}/{arch}/jdk/hotspot/normal/eclipse"
        f"?project=jdk&archive_type={archive_type}"
    )
    return url, ext


def _bundled_java_root() -> Path:
    """项目内嵌 Java 根目录：install_dir/runtime/java。"""
    return get_install_dir() / BUNDLED_JAVA_DIR_NAME / "java"


# 项目内常用 JDK 目录名（供「已集成到项目/venv」的 JDK 使用）
_PROJECT_JAVA_DIR_NAMES = ("java11", "jdk11", "java", "jdk")


def _venv_lib_runtime_java() -> Path:
    """.venv 下的 runtime/java 路径：Windows 为 .venv/Lib/runtime/java，Unix 为 .venv/lib/runtime/java。"""
    venv = get_install_dir() / ".venv"
    lib = venv / "Lib" if (venv / "Lib").is_dir() else venv / "lib"
    return lib / "runtime" / "java"


def _project_java_candidates() -> list[Path]:
    """返回可能存在的项目内 JDK 目录：项目根、.venv 根、以及 .venv/Lib(lib)/runtime/java 及其子目录（如 jdk-11.0.29）。"""
    root = get_install_dir()
    candidates = [root / name for name in _PROJECT_JAVA_DIR_NAMES]
    venv = root / ".venv"
    if venv.is_dir():
        candidates.extend([venv / name for name in _PROJECT_JAVA_DIR_NAMES])
        # .venv/Lib/runtime/java 或 .venv/lib/runtime/java（其下可能直接有 bin，或再有 jdk-11.x.x/bin）
        rt_java = _venv_lib_runtime_java()
        if rt_java.is_dir():
            if _has_java_in_dir(rt_java):
                candidates.append(rt_java)
            else:
                for sub in sorted(rt_java.iterdir()):
                    if sub.is_dir() and _has_java_in_dir(sub):
                        candidates.append(sub)
    return candidates


def _has_java_in_dir(path: Path) -> bool:
    """目录是否为有效 JDK（存在 bin/java 或 bin/java.exe）。"""
    if not path.is_dir():
        return False
    for name in ("java.exe", "java"):
        if (path / "bin" / name).exists():
            return True
    return False


def is_bundled_java_path(path: Optional[str]) -> bool:
    """判断 path 是否为项目内置的 runtime/java 路径。"""
    if not path:
        return False
    try:
        return Path(path).resolve() == _bundled_java_root().resolve()
    except Exception:
        return False


def is_project_java_path(path: Optional[str]) -> bool:
    """判断 path 是否为项目内 Java（runtime/java 或 java11/jdk11 等）。"""
    if not path:
        return False
    try:
        resolved = Path(path).resolve()
        if resolved == _bundled_java_root().resolve():
            return True
        for candidate in _project_java_candidates():
            if candidate.resolve().exists() and resolved == candidate.resolve():
                return True
        return False
    except Exception:
        return False


def get_effective_java_home() -> Optional[str]:
    """
    解析当前应使用的 JAVA_HOME。
    顺序：配置/环境变量 JAVA_HOME > 项目内 java11/jdk11/java/jdk 目录 > runtime/java（若已存在）。
    """
    settings = get_settings()
    if settings.java_home and Path(settings.java_home).exists():
        return settings.java_home
    env_java = os.environ.get("JAVA_HOME")
    if env_java and Path(env_java).exists():
        return env_java
    # 项目内已集成的 JDK（如 venv 旁放置的 java11 目录）
    for candidate in _project_java_candidates():
        if _has_java_in_dir(candidate):
            return str(candidate)
    bundled = _bundled_java_root()
    if _has_java_in_dir(bundled):
        return str(bundled)
    return None


def ensure_bundled_java() -> str:
    """
    获取可用的 JAVA_HOME；若未配置且无内嵌 JDK，则自动下载 JDK 11 到 runtime/java（可被 JAVA_SKIP_AUTO_DOWNLOAD 禁用）。
    返回用于启动 JVM 的 JAVA_HOME 路径。
    """
    effective = get_effective_java_home()
    if effective:
        return effective

    bundled_root = _bundled_java_root()
    if _has_java_in_dir(bundled_root):
        return str(bundled_root)

    if get_settings().java_skip_auto_download:
        raise RuntimeError(
            "未检测到 Java。请设置 JAVA_HOME 或将 JDK 解压到 runtime/java；"
            "若需自动下载请勿设置 JAVA_SKIP_AUTO_DOWNLOAD=1。"
        )

    # 自动下载并解压到 runtime/java
    logger.info("未检测到 JAVA_HOME，正在下载内置 JDK 11（仅首次）...")
    url, ext = _download_url()
    try:
        _download_and_extract(url, ext, bundled_root)
    except Exception as e:
        logger.exception("下载或解压 JDK 失败")
        raise RuntimeError(
            f"无法自动下载 JDK 11: {e}. 请手动设置 JAVA_HOME 或将 JDK 解压到: {bundled_root}"
        ) from e

    if not _has_java_in_dir(bundled_root):
        raise RuntimeError(f"解压后未找到 Java: {bundled_root}")
    logger.info(f"内置 JDK 已就绪: {bundled_root}")
    return str(bundled_root)


def _download_and_extract(url: str, ext: str, target_dir: Path) -> None:
    """下载并解压到 target_dir，使 target_dir/bin/java 存在。"""
    target_dir = target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    req = Request(url, headers={"User-Agent": "comsol-agent"})
    with urlopen(req, timeout=60) as resp:
        total = resp.headers.get("Content-Length")
        data = resp.read()
    if total:
        logger.debug(f"下载大小: {int(total) / (1024*1024):.2f} MB")

    import tempfile
    tmp = tempfile.mkdtemp(prefix="comsol-agent-jdk-")
    try:
        archive = Path(tmp) / ("jdk" + ext)
        archive.write_bytes(data)
        if ext == ".zip":
            with zipfile.ZipFile(archive, "r") as zf:
                zf.extractall(tmp)
        else:
            with tarfile.open(archive, "r:gz") as tf:
                tf.extractall(tmp)

        # 解压后通常有一个顶层目录 jdk-11.x.x+xx，取其内容移到 target_dir
        entries = [p for p in Path(tmp).iterdir() if p.name != "jdk" + ext]
        if len(entries) == 1 and entries[0].is_dir():
            jdk_root = entries[0]
            for item in jdk_root.iterdir():
                dest = target_dir / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                shutil.move(str(item), str(dest))
        else:
            # 多个文件/目录时，把整个 tmp 内容移进 target_dir（避免覆盖已有）
            for item in entries:
                dest = target_dir / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                shutil.move(str(item), str(dest))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
