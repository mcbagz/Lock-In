#!/usr/bin/env python3
"""
Build script to create LockIn executable
Run this script to build the executable: python build_executable.py
"""

import subprocess
import sys
import os
from pathlib import Path
import shutil

def install_pyinstaller():
    """Install PyInstaller if not already installed"""
    try:
        import PyInstaller
        print("✅ PyInstaller already installed")
    except ImportError:
        print("📦 Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller installed successfully")

def check_privacy_protection():
    """Ensure sensitive data is not included in the build"""
    print("🔒 Privacy Protection Check")
    print("=" * 40)
    
    sensitive_files = [
        "config/api_keys.enc",
        "config/ai_data.db", 
        "config/settings.json",
        "config/apps.json",
        "config/presets.json",
        "config/system_apps_cache.json"
    ]
    
    sensitive_dirs = [
        "config/chroma_db"
    ]
    
    warnings = []
    
    for file_path in sensitive_files:
        if Path(file_path).exists():
            warnings.append(f"⚠️  Found sensitive file: {file_path}")
    
    for dir_path in sensitive_dirs:
        if Path(dir_path).exists():
            warnings.append(f"⚠️  Found sensitive directory: {dir_path}")
    
    if warnings:
        print("Found sensitive data that will be EXCLUDED from the executable:")
        for warning in warnings:
            print(f"  {warning}")
        print("✅ These files will be excluded to protect your privacy")
    else:
        print("✅ No sensitive data found - good to go!")
    
    print()

def prepare_build_environment():
    """Prepare the build environment"""
    print("🛠️  Preparing Build Environment")
    print("=" * 40)
    
    # Clean previous builds
    for dir_name in ["build", "dist", "__pycache__"]:
        if Path(dir_name).exists():
            print(f"🧹 Cleaning {dir_name}/")
            shutil.rmtree(dir_name)
    
    # Remove .pyc files
    for pyc_file in Path(".").rglob("*.pyc"):
        pyc_file.unlink()
    
    # Remove __pycache__ directories
    for pycache_dir in Path(".").rglob("__pycache__"):
        shutil.rmtree(pycache_dir)
    
    print("✅ Build environment prepared")
    print()

def build_executable():
    """Build the LockIn executable"""
    print("🏗️  Building LockIn executable...")
    print("=" * 40)
    
    # Check if icon exists
    icon_path = Path("assets/icons/app.ico")
    
    try:
        print("🚀 Running PyInstaller...")
        
        # Import PyInstaller
        import PyInstaller.__main__
        
        # Prepare arguments for PyInstaller
        args = [
            "--onefile",                    # Single executable file
            "--windowed",                   # No console window (GUI app)
            "--name=LockIn",               # Executable name
            "--add-data=assets;assets",    # Include assets folder
            "--add-data=config_templates;config_templates",  # Include config templates
            "--add-data=VirtualDesktopAccessor.dll;.",  # Include DLL
            "--hidden-import=PySide6.QtCore",
            "--hidden-import=PySide6.QtWidgets", 
            "--hidden-import=PySide6.QtGui",
            "--hidden-import=transitions",
            "--hidden-import=chromadb",
            "--hidden-import=openai",
            "--hidden-import=cryptography",
            "--hidden-import=psutil",
            "--hidden-import=comtypes",
            "--hidden-import=markdown",
            "--exclude-module=config",      # Exclude config folder with sensitive data
            "--exclude-module=__pycache__", # Exclude pycache
            "--clean",                      # Clean build folder
        ]
        
        # Add icon if it exists
        if icon_path.exists():
            args.append(f"--icon={icon_path}")
            print(f"📎 Using icon: {icon_path}")
        else:
            print("📎 No icon found - building without icon")
        
        # Add the main script
        args.append("main.py")
        
        # Run PyInstaller
        PyInstaller.__main__.run(args)
        
        print("✅ Build completed successfully!")
        print()
        
        # Check if executable was created
        exe_path = Path("dist/LockIn.exe")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📁 Executable created: {exe_path}")
            print(f"📊 Size: {size_mb:.1f} MB")
        else:
            print("❌ Executable not found after build")
            
    except Exception as e:
        print(f"❌ Build failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure all dependencies are installed: pip install -r requirements.txt")
        print("2. Check that all import paths are correct")
        print("3. Verify assets folder exists")
        return False
    
    return True

def create_spec_file():
    """Create a PyInstaller spec file for advanced configuration"""
    print("📝 Creating PyInstaller spec file...")
    
    # Check if icon exists
    icon_path = Path("assets/icons/app.ico")
    icon_line = f"    icon='{icon_path}'" if icon_path.exists() else "    icon=None"
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# LockIn PyInstaller Spec File
# This file provides advanced configuration for building the executable

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('VirtualDesktopAccessor.dll', '.')],
    datas=[
        ('assets', 'assets'),
        ('config_templates', 'config_templates')
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'transitions',
        'chromadb',
        'openai',
        'cryptography',
        'psutil',
        'comtypes',
        'markdown'
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'config',  # Exclude sensitive config folder
        '__pycache__'
    ],
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
{icon_line}
)
'''
    
    with open('LockIn.spec', 'w') as f:
        f.write(spec_content)
    print("✅ Created LockIn.spec file")
    print()

def create_distribution_readme():
    """Create a README for the distribution"""
    readme_content = """# LockIn - Focus Management Desktop Application

## About
LockIn is a powerful desktop application designed to help you maintain focus and productivity by creating a distraction-free environment.

## Features
- 🎯 Virtual desktop management for isolated work environments
- 🚀 Quick app launcher with customizable presets
- 🤖 AI-powered productivity assistant
- ⌨️ Global hotkeys (Ctrl+T for App Manager, Ctrl+U for AI Chat)
- 📱 Modern, intuitive interface

## First Run Setup
1. Run LockIn.exe
2. The app will create a config folder with default settings
3. Set up your OpenAI API key in the AI Assistant for full functionality
4. Customize your apps and presets as needed

## System Requirements
- Windows 10 or later
- 4GB RAM minimum
- 50MB disk space

## Privacy & Security
- Your conversations and settings are stored locally
- No data is transmitted except to OpenAI (when using AI features)
- API keys are encrypted and stored securely
- This executable contains NO personal data from the developer

## Support
For issues or questions, please visit the project repository or contact support.

## Version Information
Built with Python and PySide6
"""
    
    with open('README_DISTRIBUTION.md', 'w') as f:
        f.write(readme_content)
    print("✅ Created distribution README")

def main():
    """Main build process"""
    print("🚀 LockIn Executable Builder")
    print("=" * 50)
    print()
    
    # Privacy protection check
    check_privacy_protection()
    
    # Prepare build environment
    prepare_build_environment()
    
    # Install PyInstaller
    install_pyinstaller()
    
    # Create spec file
    create_spec_file()
    
    # Build executable
    if build_executable():
        # Create distribution readme
        create_distribution_readme()
        
        print("🎉 Build Process Complete!")
        print("=" * 50)
        print("📋 Next Steps:")
        print("1. Test the executable: dist/LockIn.exe")
        print("2. The executable is completely self-contained")
        print("3. Users will configure their own API keys on first run")
        print("4. Share the dist/LockIn.exe file with your friends")
        print("5. Optionally share README_DISTRIBUTION.md for user guidance")
        print()
        print("🔒 Privacy Protected:")
        print("- No API keys included")
        print("- No conversation history included") 
        print("- No personal settings included")
        print("- Users get a clean, fresh installation")
        
    else:
        print("❌ Build failed. Please check the errors above.")

if __name__ == "__main__":
    main() 