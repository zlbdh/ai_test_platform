#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Test Platform - Unified startup entry point
"""
import subprocess
import sys
import os
import threading

def start_backend():
    """Start the backend service"""
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    os.chdir(backend_dir)
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "main:app", "--host", "127.0.0.1", "--port", "8020", "--reload"
    ])

def start_frontend():
    """Start the frontend service"""
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    os.chdir(frontend_dir)
    subprocess.run(["npm", "run", "dev"], shell=True)

def main():
    print("🚀 Starting AI Test Platform...")
    print("=" * 50)
    print("📡 Backend service: http://localhost:8020")
    print("🌐 Frontend service: http://localhost:8010")
    print("📚 API documentation: http://localhost:8020/docs")
    print("=" * 50)
    print("\nTip: To start services separately, use the PowerShell scripts:")
    print("  - Start-Backend.ps1  (backend)")
    print("  - Start-Frontend.ps1 (frontend)")
    print("\nPress Ctrl+C to stop all services\n")
    
    # Start the backend (in the foreground)
    start_backend()

if __name__ == "__main__":
    main()
