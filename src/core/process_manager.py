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
        self._cleanup_lock = threading.Lock()
        
    def set_window_manager(self, window_manager):
        """Set the window manager reference"""
        self.window_manager = window_manager
    
    def launch_application(self, app_path: str, app_name: str = None, args: List[str] = None) -> bool:
        """Launch an application and add it to managed apps"""
        try:
            print(f"Launching application: {app_path}")
            
            # Prepare command
            cmd = [app_path]
            if args:
                cmd.extend(args)
            
            # Launch process with proper flags
            process_handle = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )
            
            # Wait for process to start
            time.sleep(0.5)
            
            # Verify process is running
            if process_handle.poll() is not None:
                print(f"Process {app_path} exited immediately with code {process_handle.returncode}")
                return False
            
            # Get psutil process object
            try:
                psutil_process = psutil.Process(process_handle.pid)
            except psutil.NoSuchProcess:
                print(f"Process {process_handle.pid} not found in psutil")
                return False
            
            # Generate app name if not provided
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
                                    
                                    # Choose main window (prefer windows with meaningful titles)
                                    if title and len(title) > 1 and not main_window:
                                        main_window = hwnd
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
                    
                    print(f"✅ Found {len(windows)} windows for {managed_app.name} (main: {managed_app.main_window})")
                    return  # Success, exit the loop
                else:
                    print(f"No windows found for {managed_app.name} (attempt {attempt + 1}/15) - PIDs checked: {target_pids}")
            
            # Final check - one more attempt with broader search
            print(f"Final attempt: Searching for any windows with '{managed_app.name}' in title...")
            final_windows = []
            
            def final_enum_callback(hwnd, lParam):
                try:
                    if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        class_name = win32gui.GetClassName(hwnd)
                        
                        # Look for windows that might match this app by name or common window classes
                        app_name_lower = managed_app.name.lower()
                        title_lower = title.lower()
                        
                        # Check for Notepad specifically
                        if (app_name_lower == "notepad" and 
                            (class_name == "Notepad" or "notepad" in title_lower)):
                            print(f"Found {managed_app.name} window by title match: '{title}' ({class_name})")
                            final_windows.append(hwnd)
                            return True
                            
                        # Check for other apps by title containing app name
                        if (app_name_lower in title_lower and 
                            len(title) > 1 and
                            class_name not in ['IME', 'MSCTFIME UI', 'Default IME']):
                            print(f"Found potential {managed_app.name} window by title: '{title}' ({class_name})")
                            final_windows.append(hwnd)
                            
                except Exception as e:
                    pass
                return True
            
            try:
                win32gui.EnumWindows(final_enum_callback, None)
            except Exception as e:
                print(f"Error in final window search for {managed_app.name}: {e}")
            
            if final_windows:
                managed_app.windows = final_windows
                managed_app.main_window = final_windows[0]
                print(f"✅ Final search found {len(final_windows)} windows for {managed_app.name}")
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
                # Close main window if available
                if app.main_window and win32gui.IsWindow(app.main_window):
                    win32gui.PostMessage(app.main_window, win32con.WM_CLOSE, 0, 0)
                    print(f"Sent close message to {app.name}")
                    
                    # Give app more time to handle save dialogs and cleanup
                    time.sleep(3)  # Increased from 1 to 3 seconds
                
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
                    # Send close message to all windows, not just main window
                    windows_to_close = []
                    if app.main_window and win32gui.IsWindow(app.main_window):
                        windows_to_close.append(app.main_window)
                    
                    # Also send to other windows
                    for window_hwnd in app.windows:
                        if window_hwnd != app.main_window and win32gui.IsWindow(window_hwnd):
                            windows_to_close.append(window_hwnd)
                    
                    if windows_to_close:
                        for window_hwnd in windows_to_close:
                            win32gui.PostMessage(window_hwnd, win32con.WM_CLOSE, 0, 0)
                        print(f"Sent close message to {len(windows_to_close)} windows of {app.name}")
                    else:
                        print(f"No valid windows found for {app.name}")
                        
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
            return False
        
        try:
            app = self.managed_apps[app_id]
            if app.main_window and win32gui.IsWindow(app.main_window):
                # Restore if minimized
                if win32gui.IsIconic(app.main_window):
                    win32gui.ShowWindow(app.main_window, win32con.SW_RESTORE)
                
                # Bring to foreground
                win32gui.SetForegroundWindow(app.main_window)
                print(f"Focused {app.name}")
                return True
        except Exception as e:
            print(f"Error focusing application {app_id}: {e}")
        
        return False
    
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
        """Get all window handles of managed applications"""
        all_windows = []
        
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
        
        return all_windows
    
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