# LockIn - Desktop Application Focus Manager

LockIn is a powerful desktop application designed to help users focus on their tasks by managing other applications within a clean, organized workspace. Built with PySide6 and designed for Windows 11, LockIn provides a distraction-free environment for enhanced productivity.

## Features

### Phase 1: Virtual Desktop Foundation ✅
- **Virtual Desktop Management**: Attempts to create a clean virtual desktop environment
- **Taskbar Control**: Hides the taskbar for a distraction-free experience
- **Clean Environment**: Provides a clutter-free workspace

### Phase 2: Core Interface ✅
- **Three-Column Layout**: 
  - Left sidebar for application launching and management
  - Center area for workspace monitoring
  - Right sidebar for AI assistant
- **Dark Theme**: Modern, eye-friendly interface

### Phase 3: Application Management ✅
- **Process Control**: Launch and manage applications within the virtual desktop
- **Application Monitoring**: Track running applications and their status
- **Graceful Cleanup**: Proper shutdown and resource management

## Installation

### Prerequisites
- Windows 10/11
- Python 3.8 or higher
- pip package manager

### Setup
1. Clone or download the LockIn application
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Dependencies
- **PySide6**: Modern Qt-based GUI framework
- **pywin32**: Windows API access for desktop management
- **psutil**: Process and system monitoring
- **requests**: HTTP client for future AI integration
- **openai**: OpenAI API client for AI assistant
- **Pillow**: Image processing capabilities

## Usage

### Starting LockIn
```bash
python main.py
```

### Interface Overview

#### Left Sidebar - App Launcher
- **Quick Launch**: Pre-configured buttons for common applications (Notepad, Calculator)
- **Running Apps**: List of currently managed applications with their process IDs
- **Application Management**: Launch, focus, and close applications

#### Center Area - Application Workspace
- **Window Table**: Overview of all managed application windows
- **Status Information**: Current window count and management status
- **Layout Control**: Visual feedback on current window arrangement

#### Right Sidebar - AI Assistant
- **Chat Interface**: Interactive AI assistant for productivity guidance
- **Command Processing**: Simple command interpretation for basic tasks
- **Help System**: Built-in help and tips for using LockIn effectively

### Key Features

#### Application Management
- Launch applications using the Quick Launch buttons
- Monitor running applications in the Running Apps section
- View detailed window information in the center workspace

#### AI Assistant
- Ask for help with productivity tips
- Simple command processing for basic tasks

#### Window Management
- Automatic window detection and tracking
- Clean interface for managing multiple applications

## Configuration

### Application Configuration
Edit `config/apps.json` to customize available applications:
```json
{
    "applications": [
        {
            "name": "Your App",
            "path": "path/to/your/app.exe",
            "category": "Custom",
            "icon": "",
            "args": []
        }
    ]
}
```

### Settings Configuration
Modify `config/settings.json` for UI and behavior customization:
```json
{
    "ui": {
        "theme": "dark",
        "sidebar_width": 300,
        "window_layout": "maximized"
    },
    "desktop": {
        "hide_taskbar": true,
        "virtual_desktop_name": "LockInDesktop"
    }
}
```

## Architecture

### Core Components
- **VirtualDesktopManager**: Handles Windows virtual desktop creation and management
- **ProcessManager**: Manages application launching and process control
- **ConfigManager**: Handles configuration file management

### UI Components
- **MainWindow**: Coordinates the overall interface and component communication
- **AppLauncher**: Left sidebar for application management
- **AiChat**: Right sidebar AI assistant interface
- **AppArea**: Center workspace for window monitoring

## System Status

### ✅ **WORKING FEATURES**
1. **Virtual Desktop Creation**: Successfully creates virtual desktops using PowerShell method with multiple fallbacks
2. **Taskbar Control**: Properly hides and restores taskbar across desktop scenarios
3. **Process Management**: Robust application launching, tracking, and cleanup
4. **Application Lifecycle**: Complete control over managed applications

### ⚠️ **KNOWN LIMITATIONS**
1. **Window Management**: Some applications may not respond to window positioning commands (minor)
2. **Window Detection**: Window discovery timing may need adjustment for some apps (minor)  
3. **AI Features**: Currently simplified; full AI integration planned for future releases

## Troubleshooting

### Common Issues

**Application Won't Start**
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version compatibility (3.8+)
- Run as administrator if permissions are required

**Virtual Desktop Creation Failed**
- LockIn uses multiple methods (PowerShell, COM interfaces, kiosk mode)
- If PowerShell method fails, it will fall back to kiosk mode automatically
- Requires Windows 10/11 for best virtual desktop support

**Applications Not Launching**
- Verify application paths in the configuration
- Check if applications require administrator privileges
- Ensure applications exist at the specified paths

**Window Management Issues**
- Some applications may not respond to window positioning
- Try relaunching the application within LockIn
- Check if the application supports window management

## Future Enhancements

### Phase 4: Advanced Features (Planned)
- **Enhanced AI Integration**: Full OpenAI API integration with advanced command processing
- **Session Persistence**: Save and restore workspace layouts
- **Distraction Blocking**: Prevent access to distracting websites and applications
- **Time Tracking**: Monitor focus time and productivity metrics
- **Advanced Window Layouts**: Tiled, quad, and custom layout options
- **Keyboard Shortcuts**: Efficient navigation and control
- **Application Embedding**: Direct embedding of applications within LockIn interface

## Contributing

LockIn is designed to be extensible and customizable. Key areas for contribution:
- Additional window layout algorithms
- Enhanced AI command processing
- Improved virtual desktop management
- Additional application integrations
- UI/UX improvements

## License

This project is provided as-is for educational and productivity purposes.

## Support

For issues, questions, or feature requests, please refer to the application's help system or consult the source code documentation.

---

**LockIn** - *Focus on what matters most* 