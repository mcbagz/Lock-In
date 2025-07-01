#!/usr/bin/env python3
"""
Build script to create LockIn executable
Run this script to build the executable: python build_executable.py
"""

import subprocess
import sys
import os
from pathlib import Path

def install_pyinstaller():
    """Install PyInstaller if not already installed"""
    try:
        import PyInstaller
        print("✅ PyInstaller already installed")
    except ImportError:
        print("📦 Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller installed successfully")

def build_executable():
    """Build the LockIn executable"""
    print("🏗️ Building LockIn executable...")
    
    # PyInstaller command with options
    cmd = [
        "pyinstaller",
        "--onefile",                    # Single executable file
        "--windowed",                   # No console window (GUI app)
        "--name=LockIn",               # Executable name
        "--icon=assets/icons/app.ico", # App icon (if exists)
        "--add-data=assets;assets",    # Include assets folder
        "--add-data=VirtualDesktopAccessor.dll;.",  # Include DLL
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtWidgets", 
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=transitions",
        "--hidden-import=chromadb",
        "--hidden-import=openai",
        "--exclude-module=config",      # Exclude config folder with sensitive data
        "--clean",                      # Clean build folder
        "main.py"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("✅ Build completed successfully!")
        print("📁 Executable created in: dist/LockIn.exe")
        print("\n📋 Next steps:")
        print("1. Test the executable: dist/LockIn.exe")
        print("2. The executable is self-contained and portable")
        print("3. Users will need to configure their own API keys on first run")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure all dependencies are installed: pip install -r requirements.txt")
        print("2. Check that all import paths are correct")
        print("3. Verify assets folder exists")

def create_spec_file():
    """Create a PyInstaller spec file for advanced configuration"""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('VirtualDesktopAccessor.dll', '.')],
    datas=[('assets', 'assets')],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'transitions',
        'chromadb',
        'openai',
        'cryptography'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['config'],  # Exclude sensitive config folder
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LockIn',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    cofile=None,
    icon='assets/icons/app.ico'  # Update path if icon exists
)
'''
    
    with open('LockIn.spec', 'w') as f:
        f.write(spec_content)
    print("✅ Created LockIn.spec file for advanced building")
    print("💡 You can also build with: pyinstaller LockIn.spec")

if __name__ == "__main__":
    print("🚀 LockIn Executable Builder")
    print("=" * 40)
    
    # Install PyInstaller
    install_pyinstaller()
    
    # Create spec file
    create_spec_file()
    
    # Build executable
    build_executable() 