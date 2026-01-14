"""COMSOL 环境验证脚本"""
import sys
from pathlib import Path

from src.comsol.config import comsol_config
from src.utils.config import settings


def verify_environment():
    """验证 COMSOL 环境配置"""
    print("=" * 60)
    print("COMSOL 环境验证")
    print("=" * 60)
    
    # 验证配置
    print("\n1. 验证配置...")
    is_valid, error = comsol_config.validate()
    if not is_valid:
        print(f"❌ 配置验证失败: {error}")
        return False
    print("✅ 配置验证通过")
    
    # 验证 JAR 文件
    print(f"\n2. 验证 COMSOL JAR 文件...")
    jar_path = Path(comsol_config.jar_path)
    if jar_path.exists():
        print(f"✅ JAR 文件存在: {jar_path}")
        print(f"   文件大小: {jar_path.stat().st_size / (1024*1024):.2f} MB")
    else:
        print(f"❌ JAR 文件不存在: {jar_path}")
        return False
    
    # 验证 Java 环境
    print(f"\n3. 验证 Java 环境...")
    java_home = comsol_config.java_home
    if java_home:
        print(f"✅ JAVA_HOME: {java_home}")
        java_path = comsol_config.get_java_path()
        if java_path:
            print(f"✅ Java 可执行文件: {java_path}")
        else:
            print(f"⚠️  未找到 Java 可执行文件")
    else:
        print(f"❌ JAVA_HOME 未配置")
        return False
    
    # 验证输出目录
    print(f"\n4. 验证输出目录...")
    output_dir = comsol_config.model_output_dir
    if output_dir.exists():
        print(f"✅ 输出目录存在: {output_dir}")
    else:
        print(f"⚠️  输出目录不存在，将自动创建: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # 验证 Qwen API
    print(f"\n5. 验证 Qwen API 配置...")
    if settings.dashscope_api_key:
        print(f"✅ Dashscope API Key 已配置")
    else:
        print(f"⚠️  Dashscope API Key 未配置，请设置 DASHSCOPE_API_KEY")
    
    # 尝试导入 jpype1
    print(f"\n6. 验证 Python 依赖...")
    try:
        import jpype
        print(f"✅ jpype1 已安装")
    except ImportError:
        print(f"❌ jpype1 未安装，请运行: pip install jpype1")
        return False
    
    try:
        import dashscope
        print(f"✅ dashscope 已安装")
    except ImportError:
        print(f"❌ dashscope 未安装，请运行: pip install dashscope")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 环境验证完成！")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = verify_environment()
    sys.exit(0 if success else 1)
