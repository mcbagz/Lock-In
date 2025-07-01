"""
Configuration Management for LockIn
Handles loading and saving application settings and configurations
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import subprocess


class ConfigManager:
    def __init__(self):
        self.config_dir = Path("config")
        self.apps_config_file = self.config_dir / "apps.json"
        self.settings_config_file = self.config_dir / "settings.json"
        self.presets_config_file = self.config_dir / "presets.json"
        
        # Ensure config directory exists
        self.config_dir.mkdir(exist_ok=True)
        
        # Load configurations
        self.apps_config = self._load_apps_config()
        self.settings_config = self._load_settings_config()
        self.presets_config = self._load_presets_config()
    
    def _load_apps_config(self) -> Dict[str, Any]:
        """Load applications configuration"""
        if self.apps_config_file.exists():
            try:
                with open(self.apps_config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading apps config: {e}")
        
        # Return default configuration
        return self._get_default_apps_config()
    
    def _load_settings_config(self) -> Dict[str, Any]:
        """Load settings configuration"""
        if self.settings_config_file.exists():
            try:
                with open(self.settings_config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading settings config: {e}")
        
        # Return default configuration
        return self._get_default_settings_config()
    
    def _load_presets_config(self) -> Dict[str, Any]:
        """Load presets configuration"""
        if self.presets_config_file.exists():
            try:
                with open(self.presets_config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading presets config: {e}")
        
        # Return default configuration
        return self._get_default_presets_config()
    
    def _get_default_apps_config(self) -> Dict[str, Any]:
        """Get default applications configuration"""
        return {
            "applications": [
                {
                    "name": "Notepad",
                    "path": "notepad.exe",
                    "category": "Text Editors",
                    "icon": "",
                    "args": []
                },
                {
                    "name": "Calculator",
                    "path": "calc.exe",
                    "category": "Utilities",
                    "icon": "",
                    "args": []
                },
                {
                    "name": "Paint",
                    "path": "mspaint.exe",
                    "category": "Graphics",
                    "icon": "",
                    "args": []
                },
                {
                    "name": "Task Manager",
                    "path": "taskmgr.exe",
                    "category": "System",
                    "icon": "",
                    "args": []
                }
            ],
            "categories": [
                "Text Editors",
                "Web Browsers",
                "Development",
                "Graphics",
                "Utilities",
                "Games",
                "System",
                "User Added"
            ]
        }
    
    def _get_default_settings_config(self) -> Dict[str, Any]:
        """Get default settings configuration"""
        return {
            "ui": {
                "theme": "dark",
                "sidebar_width": 300,
                "window_layout": "maximized",
                "auto_focus": True,
                "show_system_info": True
            },
            "ai": {
                "enabled": True,
                "auto_execute_commands": True,
                "response_delay": 1000,
                "api_key": "",
                "model": "gpt-3.5-turbo"
            },
            "desktop": {
                "hide_taskbar": True,
                "hide_desktop_icons": True,
                "virtual_desktop_name": "LockInDesktop"
            },
            "focus": {
                "distraction_blocking": False,
                "time_tracking": True,
                "productivity_metrics": True,
                "session_persistence": True
            }
        }
    
    def _get_default_presets_config(self) -> Dict[str, Any]:
        """Get default presets configuration"""
        return {
            "presets": {
                "Coding": {
                    "name": "Coding",
                    "description": "Development environment setup",
                    "apps": [
                        {
                            "name": "PowerShell",
                            "path": "powershell.exe",
                            "icon": "💻",
                            "args": []
                        },
                        {
                            "name": "Notepad",
                            "path": "notepad.exe", 
                            "icon": "📝",
                            "args": []
                        }
                    ],
                    "browser_tabs": {
                        "chrome": ["https://github.com", "https://stackoverflow.com"],
                        "edge": ["https://docs.microsoft.com"]
                    },
                    "created_at": datetime.now().isoformat(),
                    "last_used": None
                },
                "Writing": {
                    "name": "Writing",
                    "description": "Writing and documentation setup",
                    "apps": [
                        {
                            "name": "Notepad",
                            "path": "notepad.exe",
                            "icon": "📝",
                            "args": []
                        }
                    ],
                    "browser_tabs": {
                        "chrome": ["https://docs.google.com", "https://grammarly.com"]
                    },
                    "created_at": datetime.now().isoformat(),
                    "last_used": None
                }
            }
        }
    
    def save_apps_config(self) -> bool:
        """Save applications configuration to file"""
        try:
            with open(self.apps_config_file, 'w') as f:
                json.dump(self.apps_config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving apps config: {e}")
            return False
    
    def save_settings_config(self) -> bool:
        """Save settings configuration to file"""
        try:
            with open(self.settings_config_file, 'w') as f:
                json.dump(self.settings_config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving settings config: {e}")
            return False
    
    def save_presets_config(self) -> bool:
        """Save presets configuration to file"""
        try:
            with open(self.presets_config_file, 'w') as f:
                json.dump(self.presets_config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving presets config: {e}")
            return False
    
    def get_applications(self) -> List[Dict[str, Any]]:
        """Get list of configured applications"""
        return self.apps_config.get("applications", [])
    
    def get_categories(self) -> List[str]:
        """Get list of application categories"""
        return self.apps_config.get("categories", [])
    
    def add_application(self, app_data: Dict[str, Any]) -> bool:
        """Add a new application to the configuration"""
        try:
            applications = self.apps_config.get("applications", [])
            
            # Check if application already exists
            for app in applications:
                if app.get("path") == app_data.get("path"):
                    print(f"Application {app_data.get('name')} already exists")
                    return False
            
            # Add required fields if missing
            if "icon" not in app_data:
                app_data["icon"] = ""
            if "args" not in app_data:
                app_data["args"] = []
            if "category" not in app_data:
                app_data["category"] = "User Added"
            
            applications.append(app_data)
            self.apps_config["applications"] = applications
            
            return self.save_apps_config()
            
        except Exception as e:
            print(f"Error adding application: {e}")
            return False
    
    def remove_application(self, app_path: str) -> bool:
        """Remove an application from the configuration"""
        try:
            applications = self.apps_config.get("applications", [])
            original_count = len(applications)
            
            # Remove application with matching path
            self.apps_config["applications"] = [
                app for app in applications if app.get("path") != app_path
            ]
            
            # Check if anything was removed
            if len(self.apps_config["applications"]) < original_count:
                return self.save_apps_config()
            else:
                print(f"Application with path {app_path} not found")
                return False
                
        except Exception as e:
            print(f"Error removing application: {e}")
            return False
    
    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        """Get a specific setting value"""
        return self.settings_config.get(section, {}).get(key, default)
    
    def set_setting(self, section: str, key: str, value: Any) -> bool:
        """Set a specific setting value"""
        try:
            if section not in self.settings_config:
                self.settings_config[section] = {}
            
            self.settings_config[section][key] = value
            return self.save_settings_config()
            
        except Exception as e:
            print(f"Error setting {section}.{key}: {e}")
            return False
    
    def get_ui_settings(self) -> Dict[str, Any]:
        """Get UI settings"""
        return self.settings_config.get("ui", {})
    
    def get_ai_settings(self) -> Dict[str, Any]:
        """Get AI settings"""
        return self.settings_config.get("ai", {})
    
    def get_desktop_settings(self) -> Dict[str, Any]:
        """Get desktop settings"""
        return self.settings_config.get("desktop", {})
    
    def get_focus_settings(self) -> Dict[str, Any]:
        """Get focus settings"""
        return self.settings_config.get("focus", {})
    
    def reset_to_defaults(self) -> bool:
        """Reset all configurations to defaults"""
        try:
            self.apps_config = self._get_default_apps_config()
            self.settings_config = self._get_default_settings_config()
            
            return self.save_apps_config() and self.save_settings_config()
            
        except Exception as e:
            print(f"Error resetting to defaults: {e}")
            return False
    
    def get_presets(self) -> Dict[str, Any]:
        """Get all presets"""
        return self.presets_config.get("presets", {})
    
    def get_preset(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific preset"""
        presets = self.get_presets()
        return presets.get(preset_name)
    
    def save_preset(self, preset_name: str, preset_data: Dict[str, Any]) -> bool:
        """Save/update a preset"""
        try:
            if "presets" not in self.presets_config:
                self.presets_config["presets"] = {}
            
            # Add metadata
            preset_data["name"] = preset_name
            preset_data["created_at"] = preset_data.get("created_at", datetime.now().isoformat())
            preset_data["last_used"] = datetime.now().isoformat()
            
            self.presets_config["presets"][preset_name] = preset_data
            return self.save_presets_config()
            
        except Exception as e:
            print(f"Error saving preset {preset_name}: {e}")
            return False
    
    def delete_preset(self, preset_name: str) -> bool:
        """Delete a preset"""
        try:
            presets = self.presets_config.get("presets", {})
            if preset_name in presets:
                del presets[preset_name]
                return self.save_presets_config()
            else:
                print(f"Preset {preset_name} not found")
                return False
                
        except Exception as e:
            print(f"Error deleting preset {preset_name}: {e}")
            return False
    
    def get_current_apps_as_preset_data(self, managed_apps: Dict[str, Any], preset_name: str = "", description: str = "") -> Dict[str, Any]:
        """Convert currently running apps to preset data format"""
        try:
            apps_data = []
            browser_tabs = {"chrome": [], "edge": []}
            
            for app_id, app in managed_apps.items():
                app_data = {
                    "name": app.name,
                    "path": self._get_app_path_from_process(app),
                    "icon": self._get_app_icon(app.name),
                    "args": []
                }
                
                # Handle browsers specially
                if "chrome" in app.name.lower():
                    browser_tabs["chrome"] = self._get_chrome_tabs(app)
                elif "edge" in app.name.lower() or "msedge" in app.name.lower():
                    browser_tabs["edge"] = self._get_edge_tabs(app)
                else:
                    apps_data.append(app_data)
            
            # Add browsers if they have tabs
            if browser_tabs["chrome"]:
                apps_data.append({
                    "name": "Chrome",
                    "path": "chrome.exe",
                    "icon": "🌐",
                    "args": []
                })
            if browser_tabs["edge"]:
                apps_data.append({
                    "name": "Microsoft Edge",
                    "path": "msedge.exe",
                    "icon": "🌐",
                    "args": []
                })
            
            return {
                "name": preset_name,
                "description": description,
                "apps": apps_data,
                "browser_tabs": browser_tabs,
                "created_at": datetime.now().isoformat(),
                "last_used": None
            }
            
        except Exception as e:
            print(f"Error converting current apps to preset data: {e}")
            return {
                "name": preset_name,
                "description": description,
                "apps": [],
                "browser_tabs": {"chrome": [], "edge": []},
                "created_at": datetime.now().isoformat(),
                "last_used": None
            }
    
    def _get_app_path_from_process(self, app) -> str:
        """Get application path from process object"""
        try:
            if hasattr(app, 'process') and app.process.is_running():
                return app.process.exe()
            else:
                # Fallback to common paths
                return f"{app.name.lower()}.exe"
        except:
            return f"{app.name.lower()}.exe"
    
    def _get_app_icon(self, app_name: str) -> str:
        """Get appropriate icon for application"""
        app_name_lower = app_name.lower()
        icon_map = {
            "notepad": "📝",
            "calculator": "🔢",
            "paint": "🎨",
            "powershell": "💻",
            "cmd": "💻",
            "chrome": "🌐",
            "edge": "🌐",
            "msedge": "🌐",
            "firefox": "🌐",
            "code": "💻",
            "visual studio": "💻",
            "word": "📄",
            "excel": "📊",
            "powerpoint": "📊"
        }
        
        for key, icon in icon_map.items():
            if key in app_name_lower:
                return icon
        
        return "📱"  # Default icon
    
    def _get_chrome_tabs(self, app) -> List[str]:
        """Get Chrome tabs (simplified implementation)"""
        # For now, return empty list - can be enhanced later with Chrome DevTools Protocol
        # In future versions, we could use Chrome's remote debugging protocol
        return []

    def _get_edge_tabs(self, app) -> List[str]:
        """Get Edge tabs (simplified implementation)"""
        # For now, return empty list - can be enhanced later
        # In future versions, we could use Edge's DevTools protocol
        return []

    def launch_browser_with_tabs(self, browser_name: str, urls: List[str]) -> Dict[str, Any]:
        """Launch browser with multiple tabs in isolated instance"""
        try:
            if not urls:
                return {"success": True, "process": None, "browser_name": browser_name}
                
            browser_paths = {
                "chrome": [
                    "chrome.exe",
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    "google-chrome",
                    "chromium"
                ],
                "edge": [
                    "msedge.exe",
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                    "microsoft-edge"
                ]
            }
            
            browser_commands = browser_paths.get(browser_name.lower(), [])
            
            for browser_cmd in browser_commands:
                try:
                    # Create isolated browser instance with specific flags
                    if browser_name.lower() == "chrome":
                        # Chrome flags for isolated instance
                        import tempfile
                        import uuid
                        
                        # Create unique user data directory for isolation
                        temp_dir = tempfile.gettempdir()
                        user_data_dir = os.path.join(temp_dir, f"lockin_chrome_{uuid.uuid4().hex[:8]}")
                        
                        cmd = [
                            browser_cmd,
                            f"--user-data-dir={user_data_dir}",
                            "--new-window",
                            "--no-first-run",
                            "--no-default-browser-check",
                            "--disable-default-apps",
                            "--disable-extensions",
                            "--disable-plugins"
                        ] + urls
                        
                    elif browser_name.lower() == "edge":
                        # Edge flags for isolated instance
                        import tempfile
                        import uuid
                        
                        temp_dir = tempfile.gettempdir()
                        user_data_dir = os.path.join(temp_dir, f"lockin_edge_{uuid.uuid4().hex[:8]}")
                        
                        cmd = [
                            browser_cmd,
                            f"--user-data-dir={user_data_dir}",
                            "--new-window",
                            "--no-first-run",
                            "--no-default-browser-check"
                        ] + urls
                    else:
                        cmd = [browser_cmd] + urls
                    
                    # Launch isolated browser instance
                    process = subprocess.Popen(
                        cmd, 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                    )
                    
                    print(f"Launched isolated {browser_name} instance with {len(urls)} tabs (PID: {process.pid})")
                    
                    # Return the process info for tracking
                    return {
                        "success": True,
                        "process": process,
                        "browser_name": browser_name,
                        "urls": urls,
                        "user_data_dir": user_data_dir if browser_name.lower() in ["chrome", "edge"] else None
                    }
                    
                except FileNotFoundError:
                    continue
                except Exception as e:
                    print(f"Error launching isolated {browser_cmd}: {e}")
                    continue
            
            print(f"Could not find {browser_name} executable")
            return {"success": False, "error": f"Could not find {browser_name} executable"}
            
        except Exception as e:
            print(f"Error launching browser {browser_name}: {e}")
            return {"success": False, "error": str(e)}

    def detect_browser_in_running_apps(self, managed_apps: Dict[str, Any]) -> Dict[str, List[str]]:
        """Detect browsers in running apps and attempt to get their tabs"""
        browser_tabs = {"chrome": [], "edge": []}
        
        for app_id, app in managed_apps.items():
            app_name_lower = app.name.lower()
            
            # Detect Chrome
            if "chrome" in app_name_lower:
                # For future enhancement: could use Chrome DevTools Protocol
                # For now, add some default useful URLs for coding
                browser_tabs["chrome"] = [
                    "https://github.com",
                    "https://stackoverflow.com"
                ]
            
            # Detect Edge
            elif "edge" in app_name_lower or "msedge" in app_name_lower:
                # For future enhancement: could use Edge DevTools Protocol
                # For now, add some default useful URLs
                browser_tabs["edge"] = [
                    "https://docs.microsoft.com"
                ]
        
        return browser_tabs 