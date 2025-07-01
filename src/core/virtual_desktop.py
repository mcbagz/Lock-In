"""
Virtual Desktop Management for Windows 10/11
Uses VirtualDesktopAccessor.dll for TRUE Windows 10/11 virtual desktop creation
"""

import ctypes
import ctypes.wintypes
from ctypes import wintypes, byref, c_void_p, c_ulong, POINTER, Structure, c_uint, c_char_p, c_int, c_wchar_p
import win32api
import win32gui
import win32con
import win32process
import os
import time
from typing import Optional, List
import psutil


class VirtualDesktopManager:
    def __init__(self):
        self.original_desktop_number = None
        self.virtual_desktop_number = None
        self.desktop_created = False
        self.original_taskbar_state = None
        self.real_virtual_desktop = False
        
        # Load the VirtualDesktopAccessor.dll
        self.vda_dll = None
        self.dll_loaded = False
        
        self._load_virtual_desktop_dll()
        
    def _load_virtual_desktop_dll(self):
        """Load the VirtualDesktopAccessor.dll and setup function signatures"""
        try:
            # Get the full path to the DLL
            dll_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                  "VirtualDesktopAccessor.dll")
            
            if not os.path.exists(dll_path):
                print(f"❌ VirtualDesktopAccessor.dll not found at: {dll_path}")
                return False
            
            # Load the DLL
            self.vda_dll = ctypes.CDLL(dll_path)
            print(f"✅ Loaded VirtualDesktopAccessor.dll from: {dll_path}")
            
            # Setup function signatures for all the DLL functions
            
            # fn GetCurrentDesktopNumber() -> i32
            self.vda_dll.GetCurrentDesktopNumber.argtypes = []
            self.vda_dll.GetCurrentDesktopNumber.restype = c_int
            
            # fn GetDesktopCount() -> i32
            self.vda_dll.GetDesktopCount.argtypes = []
            self.vda_dll.GetDesktopCount.restype = c_int
            
            # fn GoToDesktopNumber(desktop_number: i32) -> i32
            self.vda_dll.GoToDesktopNumber.argtypes = [c_int]
            self.vda_dll.GoToDesktopNumber.restype = c_int
            
            # fn CreateDesktop() -> i32
            self.vda_dll.CreateDesktop.argtypes = []
            self.vda_dll.CreateDesktop.restype = c_int
            
            # fn RemoveDesktop(remove_desktop_number: i32, fallback_desktop_number: i32) -> i32
            self.vda_dll.RemoveDesktop.argtypes = [c_int, c_int]
            self.vda_dll.RemoveDesktop.restype = c_int
            
            # fn MoveWindowToDesktopNumber(hwnd: HWND, desktop_number: i32) -> i32
            self.vda_dll.MoveWindowToDesktopNumber.argtypes = [wintypes.HWND, c_int]
            self.vda_dll.MoveWindowToDesktopNumber.restype = c_int
            
            # fn IsWindowOnCurrentVirtualDesktop(hwnd: HWND) -> i32
            self.vda_dll.IsWindowOnCurrentVirtualDesktop.argtypes = [wintypes.HWND]
            self.vda_dll.IsWindowOnCurrentVirtualDesktop.restype = c_int
            
            # fn GetWindowDesktopNumber(hwnd: HWND) -> i32
            self.vda_dll.GetWindowDesktopNumber.argtypes = [wintypes.HWND]
            self.vda_dll.GetWindowDesktopNumber.restype = c_int
            
            # fn IsWindowOnDesktopNumber(hwnd: HWND, desktop_number: i32) -> i32
            self.vda_dll.IsWindowOnDesktopNumber.argtypes = [wintypes.HWND, c_int]
            self.vda_dll.IsWindowOnDesktopNumber.restype = c_int
            
            # Test if the DLL is working
            current_desktop = self.vda_dll.GetCurrentDesktopNumber()
            desktop_count = self.vda_dll.GetDesktopCount()
            
            if current_desktop >= 0 and desktop_count > 0:
                print(f"✅ VirtualDesktopAccessor.dll is working!")
                print(f"   Current desktop: {current_desktop}")
                print(f"   Total desktops: {desktop_count}")
                self.dll_loaded = True
                return True
            else:
                print(f"❌ VirtualDesktopAccessor.dll functions returned invalid values")
                return False
                
        except Exception as e:
            print(f"❌ Failed to load VirtualDesktopAccessor.dll: {e}")
            return False
    
    def create_virtual_desktop(self) -> bool:
        """Create a new virtual desktop and switch to it"""
        if not self.dll_loaded:
            print("❌ VirtualDesktopAccessor.dll not loaded, falling back to kiosk mode")
            return self._fallback_to_kiosk_mode()
        
        try:
            print("🚀 Creating REAL Windows 10/11 virtual desktop...")
            
            # Get current desktop info
            self.original_desktop_number = self.vda_dll.GetCurrentDesktopNumber()
            original_count = self.vda_dll.GetDesktopCount()
            
            print(f"📊 Current state:")
            print(f"   Original desktop: {self.original_desktop_number}")
            print(f"   Desktop count: {original_count}")
            
            # Create new virtual desktop
            new_desktop_number = self.vda_dll.CreateDesktop()
            
            if new_desktop_number < 0:
                print(f"❌ Failed to create virtual desktop (returned {new_desktop_number})")
                return self._fallback_to_kiosk_mode()
            
            print(f"✅ Virtual desktop created! Desktop number: {new_desktop_number}")
            self.virtual_desktop_number = new_desktop_number
            
            # Switch to the new desktop
            switch_result = self.vda_dll.GoToDesktopNumber(new_desktop_number)
            
            if switch_result < 0:
                print(f"❌ Failed to switch to virtual desktop (returned {switch_result})")
                # Try to clean up the created desktop
                self.vda_dll.RemoveDesktop(new_desktop_number, self.original_desktop_number)
                return self._fallback_to_kiosk_mode()
            
            print(f"✅ Successfully switched to virtual desktop {new_desktop_number}!")
            
            # Verify we're on the new desktop
            current_desktop = self.vda_dll.GetCurrentDesktopNumber()
            new_count = self.vda_dll.GetDesktopCount()
            
            print(f"📊 New state:")
            print(f"   Current desktop: {current_desktop}")
            print(f"   Desktop count: {new_count}")
            
            if current_desktop == new_desktop_number and new_count > original_count:
                self.real_virtual_desktop = True
                self.desktop_created = True
                
                # Setup clean environment on the new desktop
                self._setup_clean_environment()
                
                print("🎉 REAL Windows 10/11 virtual desktop created and active!")
                print("   👀 Check Task View (Win+Tab) - you should see multiple desktops!")
                return True
            else:
                print(f"❌ Virtual desktop creation verification failed")
                return self._fallback_to_kiosk_mode()
                
        except Exception as e:
            print(f"❌ Error creating virtual desktop: {e}")
            return self._fallback_to_kiosk_mode()
    
    def _fallback_to_kiosk_mode(self) -> bool:
        """Fallback to kiosk-like mode with hidden taskbar"""
        try:
            print("⚠️ Falling back to kiosk mode (not a real virtual desktop)")
            
            # Hide taskbar and other UI elements
            self._hide_taskbar()
            self._hide_desktop_icons()
            self._set_clean_wallpaper()
            self._hide_start_menu()
            
            self.real_virtual_desktop = False
            self.desktop_created = True
            print("✅ Kiosk mode setup completed")
            return True
            
        except Exception as e:
            print(f"❌ Kiosk mode fallback failed: {e}")
            return False
    
    def _setup_clean_environment(self):
        """Setup a clean desktop environment"""
        try:
            # Apply clean environment settings
            self._hide_taskbar()
            self._hide_desktop_icons()
            self._set_clean_wallpaper()
            self._hide_start_menu()
            
            if self.real_virtual_desktop:
                print("✅ Clean environment setup on REAL virtual desktop")
            else:
                print("⚠️ Clean environment setup in kiosk mode")
            
        except Exception as e:
            print(f"❌ Error setting up clean environment: {e}")
    
    def move_window_to_virtual_desktop(self, hwnd: int) -> bool:
        """Move a window to the virtual desktop"""
        if not self.dll_loaded or not self.real_virtual_desktop or self.virtual_desktop_number is None:
            return False
        
        try:
            result = self.vda_dll.MoveWindowToDesktopNumber(hwnd, self.virtual_desktop_number)
            if result >= 0:
                print(f"✅ Moved window {hwnd} to virtual desktop {self.virtual_desktop_number}")
                return True
            else:
                print(f"❌ Failed to move window {hwnd} to virtual desktop")
                return False
        except Exception as e:
            print(f"❌ Error moving window to virtual desktop: {e}")
            return False
    
    def is_window_on_virtual_desktop(self, hwnd: int) -> bool:
        """Check if a window is on our virtual desktop"""
        if not self.dll_loaded or not self.real_virtual_desktop or self.virtual_desktop_number is None:
            return False
        
        try:
            result = self.vda_dll.IsWindowOnDesktopNumber(hwnd, self.virtual_desktop_number)
            return result > 0
        except Exception as e:
            print(f"❌ Error checking window desktop: {e}")
            return False
    
    def _hide_taskbar(self):
        """Hide the taskbar"""
        try:
            # Find and hide main taskbar
            taskbar = win32gui.FindWindow("Shell_TrayWnd", None)
            if taskbar:
                self.original_taskbar_state = win32gui.IsWindowVisible(taskbar)
                win32gui.ShowWindow(taskbar, win32con.SW_HIDE)
                print("Main taskbar hidden")
            
            # Hide secondary taskbars on multiple monitors
            def enum_windows_callback(hwnd, lParam):
                try:
                    class_name = win32gui.GetClassName(hwnd)
                    if class_name == "Shell_SecondaryTrayWnd":
                        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                except:
                    pass
                return True
            
            win32gui.EnumWindows(enum_windows_callback, None)
            
        except Exception as e:
            print(f"Error hiding taskbar: {e}")
    
    def _hide_desktop_icons(self):
        """Hide desktop icons"""
        try:
            # Find the desktop listview and hide it
            progman = win32gui.FindWindow("Progman", None)
            if progman:
                # Try to hide the desktop icons using the toggle command
                from win32con import WM_COMMAND
                win32gui.SendMessage(progman, WM_COMMAND, 0x7402, 0)
                print("Desktop icons hidden")
            
            # Also try to hide the desktop listview directly
            def enum_child_windows(hwnd, lParam):
                try:
                    class_name = win32gui.GetClassName(hwnd)
                    if class_name == "SysListView32":
                        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                except:
                    pass
                return True
            
            if progman:
                win32gui.EnumChildWindows(progman, enum_child_windows, None)
                
        except Exception as e:
            print(f"Error hiding desktop icons: {e}")
    
    def _hide_start_menu(self):
        """Hide start menu and start button"""
        try:
            # Hide start button
            start_button = win32gui.FindWindowEx(
                win32gui.FindWindow("Shell_TrayWnd", None),
                None, "Start", None
            )
            if start_button:
                win32gui.ShowWindow(start_button, win32con.SW_HIDE)
                print("Start button hidden")
                
        except Exception as e:
            print(f"Error hiding start menu: {e}")
    
    def _set_clean_wallpaper(self):
        """Set a clean dark wallpaper"""
        try:
            # Set wallpaper to solid dark color
            import winreg
            
            # Registry path for wallpaper
            key_path = r"Control Panel\Desktop"
            
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                # Set wallpaper to none (solid color)
                winreg.SetValueEx(key, "Wallpaper", 0, winreg.REG_SZ, "")
                # Set background color to dark
                winreg.SetValueEx(key, "BackgroundColor", 0, winreg.REG_SZ, "0 0 0")
                
            # Apply changes immediately
            ctypes.windll.user32.SystemParametersInfoW(20, 0, "", 3)
            print("Clean dark wallpaper set")
            
        except Exception as e:
            print(f"Error setting clean wallpaper: {e}")
    
    def _restore_taskbar(self):
        """Restore the taskbar"""
        try:
            taskbar = win32gui.FindWindow("Shell_TrayWnd", None)
            if taskbar and self.original_taskbar_state is not None:
                if self.original_taskbar_state:
                    win32gui.ShowWindow(taskbar, win32con.SW_SHOW)
                    print("Main taskbar restored")
            
            # Restore secondary taskbars
            def enum_windows_callback(hwnd, lParam):
                try:
                    class_name = win32gui.GetClassName(hwnd)
                    if class_name == "Shell_SecondaryTrayWnd":
                        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                except:
                    pass
                return True
            
            win32gui.EnumWindows(enum_windows_callback, None)
            
        except Exception as e:
            print(f"Error restoring taskbar: {e}")
    
    def _restore_desktop_icons(self):
        """Restore desktop icons"""
        try:
            progman = win32gui.FindWindow("Progman", None)
            if progman:
                from win32con import WM_COMMAND
                # Toggle desktop icons back on
                win32gui.SendMessage(progman, WM_COMMAND, 0x7402, 0)
                print("Desktop icons restored")
                
        except Exception as e:
            print(f"Error restoring desktop icons: {e}")
    
    def cleanup(self):
        """Cleanup virtual desktop and restore original state"""
        try:
            if self.desktop_created:
                if self.real_virtual_desktop:
                    print("🔄 Cleaning up REAL virtual desktop...")
                    
                    # CRITICAL: Ensure we're on the virtual desktop before removing it
                    # This prevents applications from escaping to the original desktop
                    if self.virtual_desktop_number is not None:
                        print(f"🔒 Ensuring we're on virtual desktop {self.virtual_desktop_number} for cleanup...")
                        current_desktop = self.vda_dll.GetCurrentDesktopNumber()
                        if current_desktop != self.virtual_desktop_number:
                            print(f"Switching to virtual desktop {self.virtual_desktop_number} for cleanup...")
                            self.vda_dll.GoToDesktopNumber(self.virtual_desktop_number)
                            time.sleep(0.3)  # Ensure switch is complete
                    
                    # Wait a bit longer for applications to fully terminate
                    print("⏳ Waiting for applications to fully terminate...")
                    time.sleep(2.0)  # Give applications more time to close completely
                    
                    # Double-check that no windows remain on our virtual desktop
                    remaining_windows = self._get_windows_on_virtual_desktop()
                    if remaining_windows:
                        print(f"⚠️ Found {len(remaining_windows)} remaining windows, force closing...")
                        self._force_close_remaining_windows(remaining_windows)
                        time.sleep(1.0)  # Wait after force closing
                    
                    # Now switch back to original desktop
                    if self.original_desktop_number is not None:
                        print(f"🔄 Switching back to original desktop {self.original_desktop_number}...")
                        switch_result = self.vda_dll.GoToDesktopNumber(self.original_desktop_number)
                        if switch_result >= 0:
                            print("✅ Switched back to original desktop")
                        else:
                            print(f"⚠️ Failed to switch back to original desktop")
                        
                        # Wait to ensure switch is complete before removing virtual desktop
                        time.sleep(0.5)
                    
                    # Finally remove the virtual desktop (should be empty now)
                    if self.virtual_desktop_number is not None and self.original_desktop_number is not None:
                        print(f"🗑️ Removing empty virtual desktop {self.virtual_desktop_number}...")
                        remove_result = self.vda_dll.RemoveDesktop(
                            self.virtual_desktop_number, 
                            self.original_desktop_number
                        )
                        if remove_result >= 0:
                            print("✅ Virtual desktop removed successfully")
                        else:
                            print(f"⚠️ Failed to remove virtual desktop")
                else:
                    print("🔄 Cleaning up kiosk mode...")
                
                # Restore UI elements
                self._restore_taskbar()
                self._restore_desktop_icons()
                
                self.desktop_created = False
                print("✅ Virtual desktop cleanup completed")
                
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
    
    def _get_windows_on_virtual_desktop(self) -> List[int]:
        """Get list of windows still on our virtual desktop"""
        if not self.dll_loaded or self.virtual_desktop_number is None:
            return []
        
        windows = []
        
        def enum_windows_callback(hwnd, lParam):
            try:
                if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                    # Check if window is on our virtual desktop
                    window_desktop = self.vda_dll.GetWindowDesktopNumber(hwnd)
                    if window_desktop == self.virtual_desktop_number:
                        # Skip certain system windows
                        class_name = win32gui.GetClassName(hwnd)
                        title = win32gui.GetWindowText(hwnd)
                        
                        # Skip system/shell windows
                        skip_classes = ['Shell_TrayWnd', 'Shell_SecondaryTrayWnd', 'Progman', 
                                       'WorkerW', 'DV2ControlHost', 'ForegroundStaging']
                        if class_name not in skip_classes and title:
                            windows.append(hwnd)
                            print(f"Found window on virtual desktop: {title} ({class_name})")
            except:
                pass
            return True
        
        win32gui.EnumWindows(enum_windows_callback, None)
        return windows
    
    def _force_close_remaining_windows(self, windows: List[int]):
        """Force close any remaining windows on the virtual desktop"""
        for hwnd in windows:
            try:
                if win32gui.IsWindow(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    print(f"🔨 Force closing window: {title}")
                    
                    # Try graceful close first
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    time.sleep(0.5)
                    
                    # If still exists, destroy it
                    if win32gui.IsWindow(hwnd):
                        # Get the process and terminate it
                        try:
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            process = psutil.Process(pid)
                            process.terminate()
                            print(f"🔨 Terminated process {pid} for window: {title}")
                        except:
                            # Last resort - destroy window
                            win32gui.DestroyWindow(hwnd)
                            print(f"🔨 Destroyed window: {title}")
            except Exception as e:
                print(f"Error force closing window: {e}")
    
    def is_virtual_desktop_active(self) -> bool:
        """Check if we're currently on the virtual desktop"""
        if not self.dll_loaded or not self.real_virtual_desktop:
            return self.desktop_created
        
        try:
            current_desktop = self.vda_dll.GetCurrentDesktopNumber()
            return current_desktop == self.virtual_desktop_number
        except:
            return self.desktop_created
    
    def get_desktop_info(self) -> dict:
        """Get information about current desktop state"""
        info = {
            "desktop_created": self.desktop_created,
            "virtual_desktop_active": self.is_virtual_desktop_active(),
            "method_used": "real_virtual_desktop" if self.real_virtual_desktop else "kiosk_mode",
            "is_real_virtual_desktop": self.real_virtual_desktop,
            "taskbar_hidden": self.original_taskbar_state is not None,
            "dll_loaded": self.dll_loaded,
            "original_desktop_number": self.original_desktop_number,
            "virtual_desktop_number": self.virtual_desktop_number
        }
        
        # Add current desktop info if DLL is loaded
        if self.dll_loaded:
            try:
                info["current_desktop_number"] = self.vda_dll.GetCurrentDesktopNumber()
                info["total_desktop_count"] = self.vda_dll.GetDesktopCount()
            except:
                pass
        
        return info 