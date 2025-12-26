#!/usr/bin/env python
"""
测试运行脚本
检查虚拟环境和依赖，并提供友好的错误提示
"""
import sys
import os
import subprocess


# 期望的虚拟环境名称
EXPECTED_ENV = "paper-whisperer"


def check_virtual_env():
    """检查是否在正确的虚拟环境中"""
    # 检查 CONDA_DEFAULT_ENV
    conda_env = os.environ.get("CONDA_DEFAULT_ENV", "")
    
    # 检查 VIRTUAL_ENV
    virtual_env = os.environ.get("VIRTUAL_ENV", "")
    
    if conda_env == EXPECTED_ENV:
        print(f"✅ 当前虚拟环境: {conda_env}")
        return True
    elif EXPECTED_ENV in virtual_env:
        print(f"✅ 当前虚拟环境: {virtual_env}")
        return True
    else:
        current_env = conda_env or virtual_env or "系统 Python"
        print(f"⚠️  当前环境: {current_env}")
        print(f"   建议使用虚拟环境: {EXPECTED_ENV}")
        print()
        print("请先激活虚拟环境:")
        print(f"   conda activate {EXPECTED_ENV}")
        print()
        return False


def check_dependencies():
    """检查必要的依赖"""
    missing = []
    
    # 检查测试框架
    try:
        import pytest
        print("✅ pytest 已安装")
    except ImportError:
        missing.append("pytest")
    
    try:
        import pytest_asyncio
        print("✅ pytest-asyncio 已安装")
    except ImportError:
        missing.append("pytest-asyncio")
    
    # 检查 pymilvus
    try:
        import pymilvus
        print("✅ pymilvus 已安装")
        can_run_all = True
    except ImportError:
        print("⚠️  pymilvus 未安装 - Milvus 相关测试将被跳过")
        can_run_all = False
    
    if missing:
        print("\n❌ 缺少以下依赖:")
        for pkg in missing:
            print(f"   - {pkg}")
        print("\n请运行: pip install " + " ".join(missing))
        return False, False
    
    return True, can_run_all


def main():
    """主函数"""
    print("="*60)
    print("PaperWhisperer - 测试运行器")
    print("="*60)
    print()
    
    # 检查 Python 版本
    py_version = sys.version_info
    print(f"Python 版本: {py_version.major}.{py_version.minor}.{py_version.micro}")
    print(f"Python 路径: {sys.executable}")
    print()
    
    # 检查虚拟环境
    env_ok = check_virtual_env()
    print()
    
    if not env_ok:
        print("="*60)
        print("📝 激活虚拟环境后重新运行此脚本")
        print("="*60)
        # 不强制退出，允许用户继续（可能已手动确认）
        response = input("是否继续在当前环境运行? [y/N]: ").strip().lower()
        if response != 'y':
            return 1
        print()
    
    # 检查依赖
    has_test_deps, can_run_all = check_dependencies()
    
    if not has_test_deps:
        return 1
    
    print()
    print("="*60)
    
    # 运行测试
    print("🚀 开始运行测试...")
    print("="*60)
    print()
    
    # 构建 pytest 命令
    cmd = [sys.executable, "-m", "pytest", "tests/", "-v"]
    
    # 添加命令行参数
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    
    # 运行测试
    result = subprocess.run(cmd)
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
