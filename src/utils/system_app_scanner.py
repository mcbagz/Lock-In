"""
System Application Scanner for Windows
Discovers installed applications and caches results
"""

import os
import json
import winreg
import time
from pathlib import Path
from typing import List, Dict, Set, Optional
import threading
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class SystemApp:
    name: str
    path: str
    icon: str = "📱"
    category: str = "System"
    source: str = "registry"  # "registry", "path", "programs"


class SystemAppScanner:
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.cache_file = config_dir / "system_apps_cache.json"
        self.cache_max_age = 7 * 24 * 60 * 60  # 7 days in seconds
        self._cached_apps: List[SystemApp] = []
        self._scan_lock = threading.Lock()
        
    def get_installed_apps(self, force_refresh: bool = False) -> List[SystemApp]:
        """Get list of installed applications, using cache if available"""
        if force_refresh or self._should_refresh_cache():
            print("Scanning system for installed applications...")
            self._scan_system_apps()
        elif not self._cached_apps:
            self._load_from_cache()
            
        return self._cached_apps.copy()
    
    def _should_refresh_cache(self) -> bool:
        """Check if cache should be refreshed"""
        if not self.cache_file.exists():
            return True
        
        try:
            cache_age = time.time() - self.cache_file.stat().st_mtime
            return cache_age > self.cache_max_age
        except:
            return True
    
    def _load_from_cache(self) -> bool:
        """Load applications from cache file"""
        try:
            if not self.cache_file.exists():
                return False
            
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            self._cached_apps = []
            for app_data in cache_data.get('apps', []):
                app = SystemApp(
                    name=app_data['name'],
                    path=app_data['path'],
                    icon=app_data.get('icon', '📱'),
                    category=app_data.get('category', 'System'),
                    source=app_data.get('source', 'registry')
                )
                self._cached_apps.append(app)
            
            print(f"Loaded {len(self._cached_apps)} applications from cache")
            return True
            
        except Exception as e:
            print(f"Error loading app cache: {e}")
            return False
    
    def _save_to_cache(self):
        """Save applications to cache file"""
        try:
            cache_data = {
                'version': '1.0',
                'scan_time': time.time(),
                'apps': []
            }
            
            for app in self._cached_apps:
                cache_data['apps'].append({
                    'name': app.name,
                    'path': app.path,
                    'icon': app.icon,
                    'category': app.category,
                    'source': app.source
                })
            
            # Ensure directory exists
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            print(f"Cached {len(self._cached_apps)} applications")
            
        except Exception as e:
            print(f"Error saving app cache: {e}")
    
    def _scan_system_apps(self):
        """Scan system for installed applications"""
        with self._scan_lock:
            apps_dict = {}  # Use dict to avoid duplicates by path
            
            # Scan registry for installed programs
            print("Scanning Windows registry...")
            registry_apps = self._scan_registry()
            for app in registry_apps:
                apps_dict[app.path.lower()] = app
            
            # Scan common program directories
            print("Scanning program directories...")
            program_apps = self._scan_program_directories()
            for app in program_apps:
                if app.path.lower() not in apps_dict:
                    apps_dict[app.path.lower()] = app
            
            # Scan PATH environment
            print("Scanning PATH environment...")
            path_apps = self._scan_path_environment()
            for app in path_apps:
                if app.path.lower() not in apps_dict:
                    apps_dict[app.path.lower()] = app
            
            # Add common system apps that might not be in registry
            print("Adding system applications...")
            system_apps = self._get_system_apps()
            for app in system_apps:
                if app.path.lower() not in apps_dict:
                    apps_dict[app.path.lower()] = app
            
            # Convert dict to list and sort
            self._cached_apps = sorted(apps_dict.values(), key=lambda x: x.name.lower())
            print(f"Found {len(self._cached_apps)} total applications")
            
            # Save to cache
            self._save_to_cache()
    
    def _scan_registry(self) -> List[SystemApp]:
        """Scan Windows registry for installed programs"""
        apps = []
        
        # Registry paths to scan
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        
        for hkey, path in registry_paths:
            try:
                self._scan_registry_key(hkey, path, apps)
            except Exception as e:
                print(f"Error scanning registry path {path}: {e}")
        
        return apps
    
    def _scan_registry_key(self, hkey: int, path: str, apps: List[SystemApp]):
        """Scan a specific registry key for applications"""
        try:
            with winreg.OpenKey(hkey, path) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey_path = f"{path}\\{subkey_name}"
                        
                        try:
                            with winreg.OpenKey(hkey, subkey_path) as subkey:
                                app = self._extract_app_from_registry(subkey)
                                if app and self._is_valid_app(app):
                                    apps.append(app)
                        except Exception:
                            pass
                        
                        i += 1
                    except OSError:
                        break
        except Exception as e:
            print(f"Error accessing registry key {path}: {e}")
    
    def _extract_app_from_registry(self, key) -> Optional[SystemApp]:
        """Extract application info from registry key"""
        try:
            # Try to get display name
            try:
                name = winreg.QueryValueEx(key, "DisplayName")[0]
            except FileNotFoundError:
                return None
            
            # Skip if no name or system components
            if not name or any(skip in name.lower() for skip in [
                "microsoft visual c++", "microsoft .net", "windows sdk",
                "redistributable", "runtime", "update", "hotfix", "kb"
            ]):
                return None
            
            # Try to get executable path
            exe_path = None
            
            # Try InstallLocation + executable
            try:
                install_location = winreg.QueryValueEx(key, "InstallLocation")[0]
                if install_location and os.path.exists(install_location):
                    # Look for main executable
                    possible_exes = [
                        f"{name}.exe",
                        f"{name.replace(' ', '')}.exe",
                        f"{name.split()[0]}.exe"
                    ]
                    
                    for exe_name in possible_exes:
                        exe_path = os.path.join(install_location, exe_name)
                        if os.path.exists(exe_path):
                            break
                    else:
                        # Look for any .exe in the directory
                        for file in os.listdir(install_location):
                            if file.endswith('.exe') and not file.startswith('unins'):
                                exe_path = os.path.join(install_location, file)
                                break
            except (FileNotFoundError, OSError):
                pass
            
            # Try DisplayIcon
            if not exe_path:
                try:
                    icon_path = winreg.QueryValueEx(key, "DisplayIcon")[0]
                    if icon_path and icon_path.endswith('.exe') and os.path.exists(icon_path):
                        exe_path = icon_path
                except (FileNotFoundError, OSError):
                    pass
            
            # Try UninstallString
            if not exe_path:
                try:
                    uninstall_string = winreg.QueryValueEx(key, "UninstallString")[0]
                    if uninstall_string and '.exe' in uninstall_string:
                        # Extract exe path from uninstall string
                        parts = uninstall_string.split('.exe')
                        if parts:
                            potential_path = parts[0] + '.exe'
                            # Remove quotes
                            potential_path = potential_path.strip('"')
                            if os.path.exists(potential_path):
                                exe_path = potential_path
                except (FileNotFoundError, OSError):
                    pass
            
            if not exe_path:
                return None
            
            return SystemApp(
                name=name,
                path=exe_path,
                icon=self._get_app_icon(name),
                category=self._categorize_app(name),
                source="registry"
            )
            
        except Exception as e:
            return None
    
    def _scan_program_directories(self) -> List[SystemApp]:
        """Scan common program directories for executables"""
        apps = []
        
        # Common program directories
        program_dirs = [
            os.environ.get('ProgramFiles', 'C:\\Program Files'),
            os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'),
            os.path.expanduser('~\\AppData\\Local\\Programs'),
            os.path.expanduser('~\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs'),
        ]
        
        for base_dir in program_dirs:
            if os.path.exists(base_dir):
                try:
                    self._scan_directory_for_apps(base_dir, apps, max_depth=3)
                except Exception as e:
                    print(f"Error scanning directory {base_dir}: {e}")
        
        return apps
    
    def _scan_directory_for_apps(self, directory: str, apps: List[SystemApp], max_depth: int = 2, current_depth: int = 0):
        """Recursively scan directory for executable applications"""
        if current_depth > max_depth:
            return
        
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                
                if os.path.isfile(item_path) and item.endswith('.exe'):
                    # Skip obvious installers and system files
                    if any(skip in item.lower() for skip in [
                        'unins', 'setup', 'install', 'update', 'crash', 'error',
                        'helper', 'service', 'background', 'notif'
                    ]):
                        continue
                    
                    app_name = os.path.splitext(item)[0]
                    app_name = app_name.replace('_', ' ').replace('-', ' ').title()
                    
                    app = SystemApp(
                        name=app_name,
                        path=item_path,
                        icon=self._get_app_icon(app_name),
                        category=self._categorize_app(app_name),
                        source="programs"
                    )
                    
                    if self._is_valid_app(app):
                        apps.append(app)
                
                elif os.path.isdir(item_path) and current_depth < max_depth:
                    self._scan_directory_for_apps(item_path, apps, max_depth, current_depth + 1)
        except (PermissionError, OSError):
            pass
    
    def _scan_path_environment(self) -> List[SystemApp]:
        """Scan PATH environment for executables"""
        apps = []
        
        path_env = os.environ.get('PATH', '')
        for path_dir in path_env.split(os.pathsep):
            if path_dir and os.path.exists(path_dir):
                try:
                    for file in os.listdir(path_dir):
                        if file.endswith('.exe'):
                            file_path = os.path.join(path_dir, file)
                            app_name = os.path.splitext(file)[0].replace('_', ' ').title()
                            
                            app = SystemApp(
                                name=app_name,
                                path=file_path,
                                icon=self._get_app_icon(app_name),
                                category="System",
                                source="path"
                            )
                            
                            if self._is_valid_app(app):
                                apps.append(app)
                except (PermissionError, OSError):
                    pass
        
        return apps
    
    def _get_system_apps(self) -> List[SystemApp]:
        """Get common system applications that might not be in registry"""
        system_apps = [
            SystemApp("Notepad", "notepad.exe", "📝", "Text Editors", "system"),
            SystemApp("Calculator", "calc.exe", "🔢", "Utilities", "system"),
            SystemApp("Paint", "mspaint.exe", "🎨", "Graphics", "system"),
            SystemApp("WordPad", "write.exe", "📝", "Text Editors", "system"),
            SystemApp("Command Prompt", "cmd.exe", "💻", "System", "system"),
            SystemApp("PowerShell", "powershell.exe", "💻", "System", "system"),
            SystemApp("Task Manager", "taskmgr.exe", "⚙️", "System", "system"),
            SystemApp("Registry Editor", "regedit.exe", "⚙️", "System", "system"),
            SystemApp("System Information", "msinfo32.exe", "ℹ️", "System", "system"),
            SystemApp("Character Map", "charmap.exe", "🔤", "Utilities", "system"),
            SystemApp("Windows Explorer", "explorer.exe", "📁", "System", "system"),
        ]
        
        # Check for PowerShell Core
        pwsh_paths = [
            "pwsh.exe",
            r"C:\Program Files\PowerShell\7\pwsh.exe",
            r"C:\Program Files (x86)\PowerShell\7\pwsh.exe"
        ]
        
        for pwsh_path in pwsh_paths:
            if self._app_exists(pwsh_path):
                system_apps.append(SystemApp("PowerShell Core", pwsh_path, "💻", "System", "system"))
                break
        
        # Filter to only existing apps
        return [app for app in system_apps if self._app_exists(app.path)]
    
    def _app_exists(self, path: str) -> bool:
        """Check if application exists"""
        if os.path.exists(path):
            return True
        
        # Try to find in PATH
        import shutil
        return shutil.which(path) is not None
    
    def _is_valid_app(self, app: SystemApp) -> bool:
        """Check if app is valid and should be included"""
        # Skip if path doesn't exist
        if not self._app_exists(app.path):
            return False
        
        # Skip system/hidden files
        if any(skip in app.name.lower() for skip in [
            'uninstall', 'setup', 'installer', 'updater', 'helper',
            'service', 'background', 'crash', 'error', 'debug'
        ]):
            return False
        
        # Skip very short names (likely system files)
        if len(app.name) < 3:
            return False
        
        return True
    
    def _get_app_icon(self, name: str) -> str:
        """Get appropriate icon for application"""
        name_lower = name.lower()
        
        icon_map = {
            # Text editors
            'notepad': '📝', 'wordpad': '📝', 'word': '📄', 'write': '📝',
            'code': '💻', 'visual studio': '💻', 'atom': '💻', 'sublime': '💻',
            
            # Browsers
            'chrome': '🌐', 'firefox': '🌐', 'edge': '🌐', 'opera': '🌐',
            'brave': '🌐', 'safari': '🌐', 'internet explorer': '🌐',
            
            # Media
            'vlc': '🎬', 'media player': '🎬', 'spotify': '🎵', 'itunes': '🎵',
            'audacity': '🎵', 'photoshop': '🎨', 'gimp': '🎨', 'paint': '🎨',
            
            # Office
            'excel': '📊', 'powerpoint': '📊', 'outlook': '📧', 'teams': '💬',
            'slack': '💬', 'discord': '💬', 'zoom': '📹', 'skype': '📹',
            
            # Development
            'git': '🔧', 'github': '🔧', 'npm': '📦', 'node': '🟢',
            'python': '🐍', 'java': '☕', 'docker': '🐳',
            
            # System
            'cmd': '💻', 'powershell': '💻', 'terminal': '💻',
            'task manager': '⚙️', 'registry': '⚙️', 'regedit': '⚙️',
            'explorer': '📁', 'file manager': '📁',
            
            # Utilities
            'calculator': '🔢', 'calc': '🔢', 'notepad++': '📝',
            '7-zip': '📦', 'winrar': '📦', 'zip': '📦',
            'steam': '🎮', 'origin': '🎮', 'epic': '🎮',
        }
        
        for key, icon in icon_map.items():
            if key in name_lower:
                return icon
        
        return '📱'  # Default icon
    
    def _categorize_app(self, name: str) -> str:
        """Categorize application based on name"""
        name_lower = name.lower()
        
        categories = {
            'Text Editors': ['notepad', 'wordpad', 'word', 'write', 'code', 'visual studio', 'atom', 'sublime', 'vim', 'emacs'],
            'Web Browsers': ['chrome', 'firefox', 'edge', 'opera', 'brave', 'safari', 'internet explorer', 'browser'],
            'Media': ['vlc', 'media player', 'spotify', 'itunes', 'audacity', 'photoshop', 'gimp', 'paint'],
            'Office': ['excel', 'powerpoint', 'outlook', 'teams', 'slack', 'discord', 'zoom', 'skype', 'office'],
            'Development': ['git', 'github', 'npm', 'node', 'python', 'java', 'docker', 'visual studio', 'code'],
            'System': ['cmd', 'powershell', 'terminal', 'task manager', 'registry', 'regedit', 'explorer', 'control panel'],
            'Utilities': ['calculator', 'calc', '7-zip', 'winrar', 'zip', 'utility'],
            'Games': ['steam', 'origin', 'epic', 'game', 'gaming'],
            'Graphics': ['photoshop', 'gimp', 'paint', 'illustrator', 'inkscape', 'blender']
        }
        
        for category, keywords in categories.items():
            if any(keyword in name_lower for keyword in keywords):
                return category
        
        return 'Other'
    
    def search_apps(self, query: str) -> List[SystemApp]:
        """Search applications by name (fuzzy/partial matching)"""
        if not query:
            return self.get_installed_apps()
        
        query_lower = query.lower()
        apps = self.get_installed_apps()
        
        # Score apps based on how well they match the query
        scored_apps = []
        for app in apps:
            score = self._calculate_match_score(app.name.lower(), query_lower)
            if score > 0:
                scored_apps.append((app, score))
        
        # Sort by score (highest first) and return apps
        scored_apps.sort(key=lambda x: x[1], reverse=True)
        return [app for app, score in scored_apps[:50]]  # Limit to top 50 results
    
    def _calculate_match_score(self, app_name: str, query: str) -> int:
        """Calculate how well an app name matches the query"""
        # Exact match gets highest score
        if query == app_name:
            return 1000
        
        # Starts with query gets high score
        if app_name.startswith(query):
            return 900
        
        # Contains query as whole word gets good score
        if f" {query} " in f" {app_name} " or f" {query}" in f" {app_name}":
            return 800
        
        # Contains query anywhere gets moderate score
        if query in app_name:
            return 700
        
        # Partial matching for individual characters
        score = 0
        app_chars = list(app_name)
        query_chars = list(query)
        
        # Check if all query characters exist in order in app name
        app_idx = 0
        for query_char in query_chars:
            found = False
            for i in range(app_idx, len(app_chars)):
                if app_chars[i] == query_char:
                    score += 50
                    app_idx = i + 1
                    found = True
                    break
            if not found:
                return 0  # Query character not found
        
        return score
    
    def refresh_cache(self):
        """Force refresh of application cache"""
        self.get_installed_apps(force_refresh=True) 