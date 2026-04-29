#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Test Platform - 统一启动入口
"""
import subprocess
import sys
import os
import threading

def start_backend():
    """启动后端服务"""
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    os.chdir(backend_dir)
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "main:app", "--host", "127.0.0.1", "--port", "8020", "--reload"
    ])

def start_frontend():
    """启动前端服务"""
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    os.chdir(frontend_dir)
    subprocess.run(["npm", "run", "dev"], shell=True)

def main():
    print("🚀 AI Test Platform 启动中...")
    print("=" * 50)
    print("📡 后端服务: http://localhost:8020")
    print("🌐 前端服务: http://localhost:8010")
    print("📚 API 文档: http://localhost:8020/docs")
    print("=" * 50)
    print("\n提示: 如需分别启动，请使用 PowerShell 脚本:")
    print("  - Start-Backend.ps1  (后端)")
    print("  - Start-Frontend.ps1 (前端)")
    print("\n按 Ctrl+C 停止所有服务\n")
    
    # 启动后端（前台运行）
    start_backend()

if __name__ == "__main__":
    main()
