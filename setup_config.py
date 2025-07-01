#!/usr/bin/env python3
"""
LockIn Configuration Setup Script
Run this script to set up configuration files from templates
"""

import os
import shutil
from pathlib import Path

def setup_config():
    """Set up configuration files from templates"""
    print("🔒 LockIn Configuration Setup")
    print("=" * 40)
    
    # Create config directory if it doesn't exist
    config_dir = Path("config")
    template_dir = Path("config_templates")
    
    if not template_dir.exists():
        print("❌ Error: config_templates folder not found!")
        print("   Make sure you're running this from the LockIn directory.")
        return False
    
    # Create config directory
    config_dir.mkdir(exist_ok=True)
    print(f"📁 Created config directory: {config_dir}")
    
    # Copy template files
    template_files = [
        "settings.json.template",
        "apps.json.template", 
        "presets.json.template"
    ]
    
    copied_files = []
    skipped_files = []
    
    for template_file in template_files:
        template_path = template_dir / template_file
        config_file = template_file.replace(".template", "")
        config_path = config_dir / config_file
        
        if template_path.exists():
            if config_path.exists():
                print(f"⚠️  Skipping {config_file} (already exists)")
                skipped_files.append(config_file)
            else:
                shutil.copy2(template_path, config_path)
                print(f"✅ Created {config_file}")
                copied_files.append(config_file)
        else:
            print(f"❌ Template not found: {template_file}")
    
    # Summary
    print("\n📋 Setup Summary:")
    if copied_files:
        print(f"✅ Created {len(copied_files)} configuration files:")
        for file in copied_files:
            print(f"   • {file}")
    
    if skipped_files:
        print(f"⚠️  Skipped {len(skipped_files)} existing files:")
        for file in skipped_files:
            print(f"   • {file}")
    
    print("\n🚀 Next Steps:")
    print("1. Run the application: python main.py")
    print("2. Configure your OpenAI API key in the AI Assistant")
    print("3. Customize apps.json with your preferred applications")
    print("4. Create task presets for your workflows")
    
    print("\n💡 Tips:")
    print("• Your config/ folder is private and won't be shared on GitHub")
    print("• You can always reset by deleting config/ and running this script again")
    print("• See README_DISTRIBUTION.md for detailed usage instructions")
    
    return True

if __name__ == "__main__":
    success = setup_config()
    
    if success:
        print("\n🎉 Configuration setup completed successfully!")
    else:
        print("\n❌ Setup failed. Please check the error messages above.")
        
    input("\nPress Enter to exit...") 