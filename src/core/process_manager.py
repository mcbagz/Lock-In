"""
Process Management for LockIn
Handles launching, monitoring, and controlling applications
"""

import subprocess
import psutil
import win32gui
import win32process
import win32api
import win32con
from typing import Dict, List, Optional, Tuple
import time
import os
from dataclasses import dataclass, field
import threading


@dataclass
class ManagedApp:
    name: str
    process: psutil.Process
    main_window: Optional[int] = None
    windows: List[int] = field(default_factory=list)
    launch_time: float = field(default_factory=time.time)
    subprocess_handle: Optional[subprocess.Popen] = None


class ProcessManager:
    def __init__(self):
        self.managed_apps: Dict[str, ManagedApp] = {}
        self.window_manager = None
        self.virtual_desktop = None
        self._cleanup_lock = threading.Lock()
        
    def set_window_manager(self, window_manager):
        """Set the window manager reference"""
        self.window_manager = window_manager
    
    def set_virtual_desktop(self, virtual_desktop):
        """Set the virtual desktop manager reference"""
        self.virtual_desktop = virtual_desktop
    
    def launch_application(self, app_path: str, app_name: str = None, args: List[str] = None) -> bool:
        """Launch an application and add it to managed apps"""
        try:
            print(f"Launching application: {app_path}")
            
            # Handle special cases for PowerShell
            if 'powershell' in app_path.lower():
                app_path = self._resolve_powershell_path(app_path)
                if not app_path:
                    print("PowerShell not found")
                    return False
            
            # Prepare command
            cmd = [app_path]
            if args:
                cmd.extend(args)
            
            # Special handling for terminal applications
            is_terminal = any(term in app_path.lower() for term in ['cmd', 'powershell', 'pwsh', 'terminal'])
            
            if is_terminal:
                # For terminals, use minimal flags to ensure they start properly
                print(f"Launching terminal with command: {cmd}")
                process_handle = subprocess.Popen(
                    cmd,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    shell=False
                )
            else:
                # For regular apps, hide output
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                process_handle = subprocess.Popen(
                    cmd,
                    creationflags=creation_flags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )
            
            # Wait for process to start
            time.sleep(0.5)
            
            # Check if process is still running or if it spawned children
            if process_handle.poll() is not None:
                exit_code = process_handle.returncode
                print(f"Process {app_path} exited with code {exit_code}")
                
                # For modern apps (browsers, etc.), the launcher may exit successfully (code 0)
                # after spawning child processes - check for children before failing
                if exit_code == 0:
                    print("Launcher exited successfully, checking for child processes...")
                    time.sleep(1.5)  # Give children time to start
                    
                    # Look for child processes with similar names
                    app_base_name = os.path.splitext(os.path.basename(app_path))[0].lower()
                    child_processes = []
                    
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            proc_name = proc.info['name'].lower()
                            if app_base_name in proc_name or proc_name in app_base_name:
                                # Check if this process started recently (within last 5 seconds)
                                if hasattr(proc, 'create_time') and time.time() - proc.create_time() < 5:
                                    child_processes.append(proc)
                                    print(f"Found potential child process: {proc.info['name']} (PID: {proc.info['pid']})")
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    
                    if child_processes:
                        # Use the first child process as our main process
                        main_child = child_processes[0]
                        print(f"Using child process as main: {main_child.info['name']} (PID: {main_child.info['pid']})")
                        psutil_process = main_child
                        
                        # Update the app name if not provided
                        if not app_name:
                            app_name = os.path.splitext(main_child.info['name'])[0]
                    else:
                        print("No child processes found, launcher may have failed")
                        return False
                else:
                    # Non-zero exit code means actual failure
                    print(f"Process failed with exit code {exit_code}")
                    return False
            else:
                # Process is still running normally
                try:
                    psutil_process = psutil.Process(process_handle.pid)
                except psutil.NoSuchProcess:
                    print(f"Process {process_handle.pid} not found in psutil")
                    return False
            
            # Generate app name if not provided (may have been set above for child processes)
            if not app_name:
                app_name = os.path.splitext(os.path.basename(app_path))[0]
            
            # Create managed app object
            managed_app = ManagedApp(
                name=app_name,
                process=psutil_process,
                subprocess_handle=process_handle
            )
            
            # Store managed app immediately
            app_id = f"{app_name}_{process_handle.pid}"
            self.managed_apps[app_id] = managed_app
            
            # Find windows in background thread to avoid blocking
            threading.Thread(
                target=self._find_app_windows_delayed,
                args=(managed_app, app_id),
                daemon=True
            ).start()
            
            print(f"Launched application: {app_name} (PID: {process_handle.pid})")
            return True
            
        except FileNotFoundError:
            print(f"Application not found: {app_path}")
            return False
        except Exception as e:
            print(f"Error launching application {app_path}: {e}")
            return False
    
    def _resolve_powershell_path(self, app_path: str) -> Optional[str]:
        """Resolve PowerShell path with fallbacks"""
        app_path_lower = app_path.lower()
        
        # If it's just "powershell.exe", try different paths
        if app_path_lower == "powershell.exe" or "powershell" in app_path_lower:
            powershell_paths = [
                r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",  # Most common location
                "powershell.exe",  # Try PATH
                r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe",
                app_path  # Original path if different
            ]
        elif app_path_lower == "pwsh.exe" or "pwsh" in app_path_lower:
            powershell_paths = [
                r"C:\Program Files\PowerShell\7\pwsh.exe",
                "pwsh.exe",  # Try PATH
                r"C:\Program Files (x86)\PowerShell\7\pwsh.exe",
                app_path  # Original path if different
            ]
        else:
            # Use the provided path as-is, but still try fallbacks
            powershell_paths = [
                app_path,
                r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
            ]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_paths = []
        for path in powershell_paths:
            if path.lower() not in seen:
                seen.add(path.lower())
                unique_paths.append(path)
        
        for path in unique_paths:
            if self._app_exists(path):
                print(f"✅ Using PowerShell path: {path}")
                return path
        
        print(f"❌ PowerShell not found in any of these paths: {unique_paths}")
        return None
    
    def _app_exists(self, path: str) -> bool:
        """Check if application exists"""
        if os.path.exists(path):
            return True
        
        # Try to find in PATH
        import shutil
        return shutil.which(path) is not None
    
    def _is_window_on_our_desktop(self, window_hwnd: int) -> bool:
        """Check if window is on our virtual desktop (or return True if no virtual desktop)"""
        if not self.virtual_desktop or not self.virtual_desktop.real_virtual_desktop:
            # If no virtual desktop or not using real virtual desktop, consider all windows
            return True
        
        # Check if window is on our virtual desktop
        return self.virtual_desktop.is_window_on_virtual_desktop(window_hwnd)
    
    def _find_app_windows_delayed(self, managed_app: ManagedApp, app_id: str):
        """Find windows for the app after giving it time to start"""
        try:
            print(f"Starting window detection for {managed_app.name} (PID: {managed_app.process.pid})")
            
            # Wait for application to fully start and create windows
            for attempt in range(15):  # Try for up to 15 seconds
                time.sleep(1)
                
                # Check if process is still running
                try:
                    if not managed_app.process.is_running():
                        print(f"Process {managed_app.name} died during window detection (attempt {attempt + 1})")
                        # Don't return immediately, the process might be restarting
                        if attempt < 5:  # Give it a few more chances early on
                            continue
                        else:
                            return
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    print(f"Can't access process {managed_app.name} during window detection (attempt {attempt + 1})")
                    continue
                
                # Look for windows - include child processes
                windows = []
                main_window = None
                target_pids = [managed_app.process.pid]
                
                # For some apps like Notepad, check child processes too
                try:
                    for child in managed_app.process.children(recursive=True):
                        target_pids.append(child.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                
                def enum_windows_callback(hwnd, lParam):
                    try:
                        if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                            if found_pid in target_pids:
                                # Get window title and class to filter out non-main windows
                                title = win32gui.GetWindowText(hwnd)
                                class_name = win32gui.GetClassName(hwnd)
                                
                                print(f"Found potential window for {managed_app.name}: '{title}' ({class_name}) PID:{found_pid}")
                                
                                # Skip certain types of windows
                                skip_classes = ['IME', 'MSCTFIME UI', 'Default IME', 'tooltips_class32']
                                skip_titles = ['', 'Program Manager', 'Desktop Window Manager']
                                
                                if class_name not in skip_classes and title not in skip_titles:
                                    windows.append(hwnd)
                                    print(f"✅ Added window for {managed_app.name}: '{title}' ({class_name})")
                                    
                                    # Choose main window with better logic
                                    if not main_window:
                                        main_window = hwnd  # First valid window as fallback
                                    
                                    # Prefer windows with meaningful titles and app-specific classes
                                    if title and len(title) > 1:
                                        # For specific apps, look for their characteristic window classes
                                        app_name_lower = managed_app.name.lower()
                                        if ("notepad" in app_name_lower and class_name == "Notepad") or \
                                           ("powershell" in app_name_lower and "ConsoleWindowClass" in class_name) or \
                                           ("cmd" in app_name_lower and "ConsoleWindowClass" in class_name) or \
                                           ("edge" in app_name_lower and "Chrome_WidgetWin" in class_name):
                                            main_window = hwnd
                                            print(f"🎯 Set as main window (app-specific): '{title}' ({class_name})")
                                        elif title and len(title) > 1 and title != "Program Manager":
                                            main_window = hwnd
                                            print(f"🎯 Set as main window (title-based): '{title}' ({class_name})")
                                else:
                                    print(f"⏭️ Skipped window: '{title}' ({class_name}) - filtered out")
                    except Exception as e:
                        # Don't let individual window enumeration errors stop the whole process
                        print(f"Error checking window {hwnd}: {e}")
                        pass
                    return True
                
                try:
                    win32gui.EnumWindows(enum_windows_callback, None)
                except Exception as e:
                    print(f"Error enumerating windows for {managed_app.name}: {e}")
                    continue
                
                # Update the managed app if we found windows
                if windows:
                    managed_app.windows = windows
                    if main_window:
                        managed_app.main_window = main_window
                    elif windows:
                        managed_app.main_window = windows[0]
                    
                    # Move windows to virtual desktop if available
                    if self.virtual_desktop and self.virtual_desktop.real_virtual_desktop:
                        for window_hwnd in windows:
                            if self.virtual_desktop.move_window_to_virtual_desktop(window_hwnd):
                                print(f"Moved window {window_hwnd} to virtual desktop")
                            else:
                                print(f"Failed to move window {window_hwnd} to virtual desktop")
                    
                    print(f"✅ Found {len(windows)} windows for {managed_app.name} (main: {managed_app.main_window})")
                    return  # Success, exit the loop
                else:
                    print(f"No windows found for {managed_app.name} (attempt {attempt + 1}/15) - PIDs checked: {target_pids}")
            
            # Final check - STRICT process-based search only
            print(f"Final attempt: Strict PID-based search for {managed_app.name} (PID: {managed_app.process.pid})")
            final_windows = []
            
            # Get all PIDs related to our process (including children)
            all_related_pids = [managed_app.process.pid]
            try:
                for child in managed_app.process.children(recursive=True):
                    all_related_pids.append(child.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            
            print(f"Checking PIDs: {all_related_pids}")
            
            def strict_enum_callback(hwnd, lParam):
                try:
                    if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                        _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                        
                        # ONLY accept windows that belong to our exact process or its children
                        if window_pid in all_related_pids:
                            title = win32gui.GetWindowText(hwnd)
                            class_name = win32gui.GetClassName(hwnd)
                            
                            # Skip system windows
                            skip_classes = ['IME', 'MSCTFIME UI', 'Default IME', 'tooltips_class32']
                            skip_titles = ['', 'Program Manager', 'Desktop Window Manager']
                            
                            if class_name not in skip_classes and title not in skip_titles:
                                print(f"✅ Found window belonging to our process: '{title}' ({class_name}) PID:{window_pid}")
                                final_windows.append(hwnd)
                            else:
                                print(f"⏭️ Skipped system window: '{title}' ({class_name}) PID:{window_pid}")
                            
                except Exception as e:
                    pass
                return True
            
            try:
                win32gui.EnumWindows(strict_enum_callback, None)
            except Exception as e:
                print(f"Error in strict window search for {managed_app.name}: {e}")
            
            if final_windows:
                managed_app.windows = final_windows
                
                # Choose the best main window from final_windows
                main_window = final_windows[0]  # Default to first
                
                for hwnd in final_windows:
                    try:
                        title = win32gui.GetWindowText(hwnd)
                        class_name = win32gui.GetClassName(hwnd)
                        
                        # App-specific main window detection
                        app_name_lower = managed_app.name.lower()
                        if ("notepad" in app_name_lower and class_name == "Notepad") or \
                           ("powershell" in app_name_lower and "ConsoleWindowClass" in class_name) or \
                           ("cmd" in app_name_lower and "ConsoleWindowClass" in class_name) or \
                           ("edge" in app_name_lower and "Chrome_WidgetWin" in class_name):
                            main_window = hwnd
                            print(f"🎯 Selected main window (app-specific): '{title}' ({class_name})")
                            break
                        elif title and len(title) > 1 and title != "Program Manager":
                            main_window = hwnd
                            print(f"🎯 Selected main window (title-based): '{title}' ({class_name})")
                    except:
                        continue
                
                managed_app.main_window = main_window
                
                # Move windows to virtual desktop if available
                if self.virtual_desktop and self.virtual_desktop.real_virtual_desktop:
                    for window_hwnd in final_windows:
                        if self.virtual_desktop.move_window_to_virtual_desktop(window_hwnd):
                            print(f"Moved window {window_hwnd} to virtual desktop")
                        else:
                            print(f"Failed to move window {window_hwnd} to virtual desktop")
                
                print(f"✅ Strict search found {len(final_windows)} windows for {managed_app.name}")
                return
            
            print(f"⚠️ No windows found for {managed_app.name} after exhaustive search")
                
        except Exception as e:
            print(f"Error finding windows for {managed_app.name}: {e}")
            import traceback
            traceback.print_exc()
    
    def get_managed_apps(self) -> Dict[str, ManagedApp]:
        """Get all currently managed applications"""
        with self._cleanup_lock:
            self._cleanup_dead_processes()
            return self.managed_apps.copy()
    
    def _cleanup_dead_processes(self):
        """Remove dead processes from managed apps"""
        dead_apps = []
        current_time = time.time()
        
        for app_id, app in self.managed_apps.items():
            try:
                # Give newly launched apps at least 30 seconds before considering them dead
                app_age = current_time - app.launch_time
                if app_age < 30:  # Don't cleanup apps younger than 30 seconds
                    continue
                
                # Check if process is still running
                if not app.process.is_running():
                    dead_apps.append(app_id)
                    continue
                
                # Check subprocess handle if available
                if app.subprocess_handle and app.subprocess_handle.poll() is not None:
                    dead_apps.append(app_id)
                    continue
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Only mark as dead if the app is older than 30 seconds
                app_age = current_time - app.launch_time
                if app_age >= 30:
                    dead_apps.append(app_id)
        
        # Remove dead processes
        for app_id in dead_apps:
            app = self.managed_apps.get(app_id)
            if app:
                print(f"Removing dead process: {app.name} (age: {current_time - app.launch_time:.1f}s)")
                del self.managed_apps[app_id]
    
    def close_application(self, app_id: str) -> bool:
        """Close a specific managed application"""
        if app_id not in self.managed_apps:
            print(f"App {app_id} not found in managed apps")
            return False
        
        try:
            app = self.managed_apps[app_id]
            print(f"Closing application: {app.name} (PID: {app.process.pid})")
            
            # Try graceful termination first
            try:
                # Close windows that are on our virtual desktop (or all if no virtual desktop)
                windows_to_close = []
                
                # Check main window
                if app.main_window and win32gui.IsWindow(app.main_window):
                    if self._is_window_on_our_desktop(app.main_window):
                        windows_to_close.append(app.main_window)
                
                # Check other windows
                for window_hwnd in app.windows:
                    if (window_hwnd != app.main_window and 
                        win32gui.IsWindow(window_hwnd) and 
                        self._is_window_on_our_desktop(window_hwnd)):
                        windows_to_close.append(window_hwnd)
                
                # Send close messages
                for window_hwnd in windows_to_close:
                    win32gui.PostMessage(window_hwnd, win32con.WM_CLOSE, 0, 0)
                
                if windows_to_close:
                    print(f"Sent close message to {len(windows_to_close)} windows of {app.name}")
                    # Give app more time to handle save dialogs and cleanup
                    time.sleep(3)  # Increased from 1 to 3 seconds
                else:
                    print(f"No windows found on our desktop for {app.name}")
                
                # If still running, try terminate
                if app.process.is_running():
                    app.process.terminate()
                    print(f"Terminated {app.name}")
                    
                    # Wait for process to terminate
                    try:
                        app.process.wait(timeout=5)  # Wait up to 5 seconds
                        print(f"Process {app.name} terminated gracefully")
                    except psutil.TimeoutExpired:
                        # Force kill if it doesn't terminate gracefully
                        print(f"Force killing {app.name}")
                        app.process.kill()
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process already gone
                print(f"Process {app.name} already terminated")
                pass
            
            # Clean up subprocess handle
            if app.subprocess_handle:
                try:
                    if app.subprocess_handle.poll() is None:
                        app.subprocess_handle.terminate()
                except:
                    pass
            
            # Remove from managed apps only after confirmed closed
            with self._cleanup_lock:
                if app_id in self.managed_apps:
                    del self.managed_apps[app_id]
            
            print(f"Successfully closed application: {app.name}")
            return True
            
        except Exception as e:
            print(f"Error closing application {app_id}: {e}")
            return False
    
    def close_all_applications(self):
        """Close all managed applications"""
        print("Closing all managed applications...")
        
        # Get list of app IDs to avoid modification during iteration
        with self._cleanup_lock:
            app_ids = list(self.managed_apps.keys())
        
        if not app_ids:
            print("No managed applications to close")
            return
        
        print(f"Found {len(app_ids)} managed applications to close")
        
        # First pass: Send close messages to all apps
        for app_id in app_ids:
            if app_id in self.managed_apps:
                app = self.managed_apps[app_id]
                try:
                    # Send close message to windows on our virtual desktop only
                    windows_to_close = []
                    
                    # Check main window
                    if app.main_window and win32gui.IsWindow(app.main_window):
                        if self._is_window_on_our_desktop(app.main_window):
                            windows_to_close.append(app.main_window)
                    
                    # Check other windows
                    for window_hwnd in app.windows:
                        if (window_hwnd != app.main_window and 
                            win32gui.IsWindow(window_hwnd) and 
                            self._is_window_on_our_desktop(window_hwnd)):
                            windows_to_close.append(window_hwnd)
                    
                    if windows_to_close:
                        for window_hwnd in windows_to_close:
                            win32gui.PostMessage(window_hwnd, win32con.WM_CLOSE, 0, 0)
                        print(f"Sent close message to {len(windows_to_close)} windows of {app.name}")
                    else:
                        print(f"No windows found on our desktop for {app.name}")
                        
                except Exception as e:
                    print(f"Error sending close message to {app.name}: {e}")
        
        # Give apps time to handle save dialogs and cleanup
        print("Waiting for applications to close gracefully...")
        time.sleep(5)  # Give apps 5 seconds to show save dialogs and close
        
        # Second pass: Check which apps are still running and handle them
        remaining_apps = []
        with self._cleanup_lock:
            for app_id in list(self.managed_apps.keys()):
                app = self.managed_apps[app_id]
                try:
                    if app.process.is_running():
                        remaining_apps.append(app_id)
                    else:
                        # App closed successfully, remove it
                        print(f"Application {app.name} closed successfully")
                        del self.managed_apps[app_id]
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process is gone, remove it
                    print(f"Application {app.name} process not found, removing")
                    del self.managed_apps[app_id]
        
        # Third pass: Force close remaining apps
        for app_id in remaining_apps:
            if app_id in self.managed_apps:
                app = self.managed_apps[app_id]
                try:
                    print(f"Force closing stubborn app: {app.name}")
                    if app.process.is_running():
                        app.process.terminate()
                        try:
                            app.process.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            app.process.kill()
                            print(f"Force killed {app.name}")
                    
                    # Clean up subprocess handle
                    if app.subprocess_handle:
                        try:
                            if app.subprocess_handle.poll() is None:
                                app.subprocess_handle.terminate()
                        except:
                            pass
                    
                    # Remove from managed apps
                    with self._cleanup_lock:
                        if app_id in self.managed_apps:
                            del self.managed_apps[app_id]
                            
                except Exception as e:
                    print(f"Error force closing {app.name}: {e}")
        
        print("All managed applications closed")
    
    def minimize_application(self, app_id: str) -> bool:
        """Minimize a managed application"""
        if app_id not in self.managed_apps:
            return False
        
        try:
            app = self.managed_apps[app_id]
            if app.main_window and win32gui.IsWindow(app.main_window):
                win32gui.ShowWindow(app.main_window, win32con.SW_MINIMIZE)
                print(f"Minimized {app.name}")
                return True
        except Exception as e:
            print(f"Error minimizing application {app_id}: {e}")
        
        return False
    
    def restore_application(self, app_id: str) -> bool:
        """Restore a minimized application"""
        if app_id not in self.managed_apps:
            return False
        
        try:
            app = self.managed_apps[app_id]
            if app.main_window and win32gui.IsWindow(app.main_window):
                win32gui.ShowWindow(app.main_window, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(app.main_window)
                print(f"Restored {app.name}")
                return True
        except Exception as e:
            print(f"Error restoring application {app_id}: {e}")
        
        return False
    
    def focus_application(self, app_id: str) -> bool:
        """Bring an application to the foreground"""
        if app_id not in self.managed_apps:
            print(f"App {app_id} not found in managed apps")
            return False
        
        app = self.managed_apps[app_id]
        
        # Try main window first
        if app.main_window and win32gui.IsWindow(app.main_window):
            try:
                print(f"Attempting to focus main window {app.main_window} for {app.name}")
                
                # Restore if minimized
                if win32gui.IsIconic(app.main_window):
                    win32gui.ShowWindow(app.main_window, win32con.SW_RESTORE)
                
                # Bring to foreground
                win32gui.SetForegroundWindow(app.main_window)
                print(f"✅ Focused {app.name} via main window")
                return True
            except Exception as e:
                print(f"Failed to focus main window: {e}")
        
        # Fallback: try any valid window
        for window_hwnd in app.windows:
            if win32gui.IsWindow(window_hwnd):
                try:
                    title = win32gui.GetWindowText(window_hwnd)
                    print(f"Attempting to focus fallback window: '{title}' ({window_hwnd})")
                    
                    # Restore if minimized
                    if win32gui.IsIconic(window_hwnd):
                        win32gui.ShowWindow(window_hwnd, win32con.SW_RESTORE)
                    
                    # Bring to foreground
                    win32gui.SetForegroundWindow(window_hwnd)
                    print(f"✅ Focused {app.name} via fallback window")
                    return True
                except Exception as e:
                    print(f"Failed to focus window {window_hwnd}: {e}")
                    continue
        
        print(f"❌ Could not focus any window for {app.name}")
        return False
    
    def focus_window_by_handle(self, window_hwnd: int) -> bool:
        """Focus any window by its handle (for virtual desktop windows)"""
        try:
            if not win32gui.IsWindow(window_hwnd):
                print(f"Window handle {window_hwnd} is not valid")
                return False
            
            title = win32gui.GetWindowText(window_hwnd)
            print(f"Attempting to focus window: '{title}' ({window_hwnd})")
            
            # Restore if minimized
            if win32gui.IsIconic(window_hwnd):
                win32gui.ShowWindow(window_hwnd, win32con.SW_RESTORE)
            
            # Bring to foreground
            win32gui.SetForegroundWindow(window_hwnd)
            print(f"✅ Focused window: '{title}'")
            return True
            
        except Exception as e:
            print(f"❌ Failed to focus window {window_hwnd}: {e}")
            return False
    
    def minimize_all_virtual_desktop_windows(self) -> int:
        """Minimize ALL windows on the virtual desktop"""
        if not self.virtual_desktop or not self.virtual_desktop.real_virtual_desktop:
            print("No virtual desktop available for minimize all")
            return 0
        
        minimized_count = 0
        all_windows = self._get_all_windows_on_virtual_desktop()
        
        print(f"Minimizing {len(all_windows)} windows on virtual desktop...")
        
        for hwnd in all_windows:
            try:
                if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                    print(f"✅ Minimized: '{title}'")
                    minimized_count += 1
            except Exception as e:
                print(f"❌ Failed to minimize window {hwnd}: {e}")
        
        print(f"Minimized {minimized_count} windows")
        return minimized_count
    
    def get_application_info(self, app_id: str) -> Optional[dict]:
        """Get detailed information about a managed application"""
        if app_id not in self.managed_apps:
            return None
        
        try:
            app = self.managed_apps[app_id]
            
            # Get process info safely
            try:
                process_info = app.process.as_dict(attrs=[
                    'pid', 'name', 'status', 'cpu_percent', 'memory_info'
                ])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_info = {
                    'pid': app.process.pid,
                    'name': app.name,
                    'status': 'dead',
                    'cpu_percent': 0,
                    'memory_info': None
                }
            
            return {
                'app_id': app_id,
                'name': app.name,
                'launch_time': app.launch_time,
                'uptime': time.time() - app.launch_time,
                'main_window': app.main_window,
                'window_count': len(app.windows),
                'process_info': process_info
            }
        except Exception as e:
            print(f"Error getting application info for {app_id}: {e}")
            return None
    
    def get_all_managed_windows(self) -> List[int]:
        """Get all window handles - both managed apps AND all windows on virtual desktop"""
        all_windows = []
        
        # First, add windows from managed applications
        with self._cleanup_lock:
            for app_id, app in self.managed_apps.items():
                try:
                    # Verify process is still running before adding windows
                    if app.process.is_running():
                        # Add main window if valid
                        if app.main_window and win32gui.IsWindow(app.main_window):
                            all_windows.append(app.main_window)
                        
                        # Add other windows if valid
                        for window_hwnd in app.windows:
                            if window_hwnd != app.main_window and win32gui.IsWindow(window_hwnd):
                                all_windows.append(window_hwnd)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        # Also add ALL windows on our virtual desktop (broader tracking)
        if self.virtual_desktop and self.virtual_desktop.real_virtual_desktop:
            desktop_windows = self._get_all_windows_on_virtual_desktop()
            for hwnd in desktop_windows:
                if hwnd not in all_windows:
                    all_windows.append(hwnd)
                    print(f"📍 Added virtual desktop window: {win32gui.GetWindowText(hwnd)}")
        
        return all_windows
    
    def _get_all_windows_on_virtual_desktop(self) -> List[int]:
        """Get ALL windows currently on our virtual desktop"""
        if not self.virtual_desktop or not self.virtual_desktop.real_virtual_desktop:
            return []
        
        desktop_windows = []
        
        def enum_desktop_windows(hwnd, lParam):
            try:
                if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                    # Check if window is on our virtual desktop
                    if self.virtual_desktop.is_window_on_virtual_desktop(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        class_name = win32gui.GetClassName(hwnd)
                        
                        # Skip LockIn's own windows and system windows
                        skip_classes = ['Shell_TrayWnd', 'Shell_SecondaryTrayWnd', 'Progman', 
                                       'WorkerW', 'DV2ControlHost', 'ForegroundStaging']
                        skip_titles = ['LockIn - App Manager', 'LockIn - AI Chat', 'LockIn - Header']
                        
                        if (class_name not in skip_classes and 
                            title not in skip_titles and
                            title and len(title) > 0):
                            desktop_windows.append(hwnd)
                            print(f"🎯 Found window on virtual desktop: '{title}' ({class_name})")
            except:
                pass
            return True
        
        try:
            win32gui.EnumWindows(enum_desktop_windows, None)
        except Exception as e:
            print(f"Error enumerating virtual desktop windows: {e}")
        
        return desktop_windows
    
    def is_window_managed(self, window_hwnd: int) -> bool:
        """Check if a window handle belongs to a managed application"""
        try:
            _, window_pid = win32process.GetWindowThreadProcessId(window_hwnd)
        except:
            return False
        
        with self._cleanup_lock:
            for app_id, app in self.managed_apps.items():
                try:
                    if app.process.is_running() and app.process.pid == window_pid:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        return False 