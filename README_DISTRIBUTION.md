# 🔒 LockIn - Desktop Focus Manager

LockIn is a powerful desktop application that helps you maintain focus by creating isolated virtual desktops for specific tasks. It combines application management, AI assistance, and task presets to boost your productivity.

## ✨ Features

- **Virtual Desktop Management**: Creates isolated virtual desktops for distraction-free work
- **Application Launcher**: Quick launch and manage applications for specific tasks
- **AI Assistant**: Integrated OpenAI-powered chat for help and productivity tips
- **Task Presets**: Save and load complete work environments with apps and browser tabs
- **Window Management**: Automatically organizes and manages application windows
- **Always-on-top Interface**: Floating windows that stay accessible

## 📥 Installation Options

### Option 1: Download Executable (Recommended for Users)
1. Download the latest `LockIn.exe` from the releases page
2. Run the executable - no installation required!
3. Configure your API keys and settings on first run

### Option 2: Build from Source (For Developers)

#### Prerequisites
- Python 3.8 or higher
- Windows 10/11 (required for virtual desktop features)
- Git (for cloning the repository)

#### Setup Steps
1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/lockin.git
   cd lockin
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up configuration**
   ```bash
   # Copy template files to config folder
   mkdir config
   copy config_templates\settings.json.template config\settings.json
   copy config_templates\apps.json.template config\apps.json
   copy config_templates\presets.json.template config\presets.json
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

## 🏗️ Building Your Own Executable

To create a standalone executable:

1. **Run the build script**
   ```bash
   python build_executable.py
   ```

2. **Find your executable**
   - The executable will be created in `dist/LockIn.exe`
   - This file is completely portable and self-contained

### Build Options
- **Quick build**: `python build_executable.py`
- **Advanced build**: `pyinstaller LockIn.spec` (after running the build script once)

## ⚙️ Configuration

### First Run Setup
1. **API Keys**: Enter your OpenAI API key in the AI Assistant settings
2. **Applications**: Customize the list of available applications in the App Manager
3. **Presets**: Create task presets for different work modes

### Configuration Files
- `config/settings.json` - General application settings
- `config/apps.json` - Available applications for launching
- `config/presets.json` - Saved task presets
- `config/api_keys.enc` - Encrypted API keys (auto-generated)

### Example Settings
See the `config_templates/` folder for example configuration files.

## 🚀 Usage

### Basic Workflow
1. **Start LockIn** - Creates a new virtual desktop
2. **Launch Apps** - Use the App Manager to launch applications
3. **Set Up AI** - Configure the AI Assistant with your API key
4. **Create Presets** - Save your current setup as a preset
5. **Focus Mode** - Work in your isolated environment
6. **Clean Exit** - Use the header close button to return to your original desktop

### Keyboard Shortcuts
- The app primarily uses mouse interaction
- Close confirmation prevents accidental shutdown
- All windows can be minimized to title bars

### Virtual Desktop Features
- Creates isolated workspace separate from your main desktop
- Automatically manages application windows
- Restores original desktop on exit
- Handles multi-monitor setups

## 🤖 AI Assistant

### Setup
1. Click the settings gear in the AI Assistant window
2. Enter your OpenAI API key
3. Choose your preferred model (GPT-4 recommended)
4. Select a conversation preset

### Features
- **Conversation History**: Automatically saves and loads conversations
- **Preset Modes**: Different AI personalities for various tasks
- **Semantic Search**: Find previous conversations and information
- **Export Options**: Save important conversations

### Presets
- **General**: Balanced assistant for general questions
- **Coding**: Programming-focused assistance
- **Writing**: Help with writing and editing
- **Research**: Research and analysis support

## 📊 Task Presets

### Creating Presets
1. Set up your ideal work environment (apps + browser tabs)
2. Use "Save Preset" in the App Manager
3. Give it a descriptive name and description

### Loading Presets
1. Select a preset from the dropdown
2. Click "Load Preset"
3. Applications will launch automatically in sequence

### Preset Examples
- **Development**: VS Code + Terminal + Documentation tabs
- **Writing**: Text editor + Grammar tools + Research tabs
- **Research**: Multiple browser tabs + Note-taking app

## 🔒 Privacy & Security

### What's Private
- Your API keys are encrypted locally
- Chat conversations are stored locally only
- No data is transmitted except to OpenAI (when using AI features)
- Virtual desktop isolation provides additional privacy

### What's Shared (in this repository)
- Source code (no sensitive data)
- Template configuration files
- Documentation and build scripts

### What's NOT Shared
- Your actual configuration files (`config/` folder)
- API keys and encrypted data
- Chat history and personal data
- Build artifacts and executables

## 🛠️ Development

### Project Structure
```
Lock-In/
├── src/                    # Source code
│   ├── ai/                # AI integration
│   ├── core/              # Core functionality
│   ├── ui/                # User interface
│   └── utils/             # Utilities
├── assets/                # Icons and styles
├── config_templates/      # Template configurations
├── main.py               # Application entry point
├── build_executable.py   # Build script
└── requirements.txt      # Dependencies
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### Dependencies
- **PySide6**: Qt-based GUI framework
- **OpenAI**: AI integration
- **ChromaDB**: Vector database for semantic search
- **Transitions**: State machine for AI chat
- **Cryptography**: API key encryption

## 📋 Requirements

### System Requirements
- **OS**: Windows 10 version 1903 or later (required for virtual desktop API)
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 100MB for application, additional space for conversations
- **Network**: Internet connection required for AI features only

### Hardware Requirements
- Any modern x64 processor
- Multi-monitor support (optional but recommended)
- Keyboard and mouse

## 🐛 Troubleshooting

### Common Issues

**App won't start**
- Check Windows version (need 1903+)
- Run as administrator if needed
- Verify all dependencies installed

**Virtual desktop not working**
- Ensure Windows virtual desktop feature is enabled
- Check if other virtual desktop software is running
- Try running as administrator

**AI features not working**
- Verify OpenAI API key is valid
- Check internet connection
- Ensure API key has sufficient credits

**Applications won't launch**
- Check application paths in `config/apps.json`
- Verify applications are installed
- Try running LockIn as administrator

### Getting Help
1. Check this README for common solutions
2. Look at the example configuration files
3. Create an issue on GitHub with details
4. Include log files if available

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with PySide6 and the Qt framework
- Powered by OpenAI's language models
- Uses ChromaDB for semantic search
- Virtual desktop integration via Windows API

---

**Made with ❤️ for focused productivity** 