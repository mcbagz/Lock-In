#!/usr/bin/env python3
"""
LockIn - Desktop Application Focus Manager
Main entry point for the application
"""

import sys
import os
import signal
import atexit
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, Qt, QThread, Signal
from PySide6.QtGui import QIcon, QShortcut, QKeySequence
import ctypes
from ctypes import wintypes
import threading

from core.virtual_desktop import VirtualDesktopManager
from core.process_manager import ProcessManager
from utils.config import ConfigManager


class GlobalHotkeyManager(QThread):
    """Manages global hotkeys using Windows API"""
    hotkey_pressed = Signal(int)  # Signal emitted when hotkey is pressed
    
    # Virtual key codes
    VK_T = 0x54
    VK_U = 0x55
    
    # Modifier keys
    MOD_CONTROL = 0x0002
    
    # Hotkey IDs
    HOTKEY_CTRL_T = 1
    HOTKEY_CTRL_U = 2
    
    def __init__(self):
        super().__init__()
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        self.hotkeys_registered = False
        self.should_stop = False
        
    def run(self):
        """Main thread loop for handling hotkey messages"""
        try:
            # Register hotkeys
            if not self.register_hotkeys():
                print("❌ Failed to register global hotkeys")
                return
            
            print("✅ Global hotkeys registered successfully")
            self.hotkeys_registered = True
            
            # Message loop
            msg = wintypes.MSG()
            while not self.should_stop:
                bRet = self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                
                if bRet == 0:  # WM_QUIT
                    break
                elif bRet == -1:  # Error
                    print("❌ Error in hotkey message loop")
                    break
                else:
                    if msg.message == 0x0312:  # WM_HOTKEY
                        hotkey_id = msg.wParam
                        self.hotkey_pressed.emit(hotkey_id)
                    
                    self.user32.TranslateMessage(ctypes.byref(msg))
                    self.user32.DispatchMessageW(ctypes.byref(msg))
                    
        except Exception as e:
            print(f"❌ Error in global hotkey manager: {e}")
        finally:
            self.unregister_hotkeys()
            
    def register_hotkeys(self) -> bool:
        """Register global hotkeys"""
        try:
            # Register Ctrl+T
            if not self.user32.RegisterHotKey(None, self.HOTKEY_CTRL_T, self.MOD_CONTROL, self.VK_T):
                print("❌ Failed to register Ctrl+T hotkey")
                return False
                
            # Register Ctrl+U  
            if not self.user32.RegisterHotKey(None, self.HOTKEY_CTRL_U, self.MOD_CONTROL, self.VK_U):
                print("❌ Failed to register Ctrl+U hotkey")
                self.user32.UnregisterHotKey(None, self.HOTKEY_CTRL_T)
                return False
                
            return True
            
        except Exception as e:
            print(f"❌ Error registering hotkeys: {e}")
            return False
            
    def unregister_hotkeys(self):
        """Unregister global hotkeys"""
        try:
            if self.hotkeys_registered:
                self.user32.UnregisterHotKey(None, self.HOTKEY_CTRL_T)
                self.user32.UnregisterHotKey(None, self.HOTKEY_CTRL_U)
                print("✅ Global hotkeys unregistered")
                self.hotkeys_registered = False
        except Exception as e:
            print(f"❌ Error unregistering hotkeys: {e}")
            
    def stop(self):
        """Stop the hotkey manager"""
        self.should_stop = True
        # Post a quit message to break the message loop
        try:
            thread_id = int(self.currentThreadId())
            self.user32.PostThreadMessageW(thread_id, 0x0012, 0, 0)  # WM_QUIT
        except:
            # If posting thread message fails, we'll rely on should_stop flag
            pass


class LockInApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("LockIn")
        self.app.setApplicationVersion("1.0.0")
        
        # Initialize managers
        self.config = ConfigManager()
        self.virtual_desktop = VirtualDesktopManager()
        self.process_manager = ProcessManager()
        self.main_window = None
        self._cleanup_called = False  # Flag to prevent multiple cleanup calls
        
        # Initialize global hotkey manager
        self.global_hotkeys = None
        
        # Setup cleanup handlers
        self.setup_cleanup_handlers()
        
    def setup_cleanup_handlers(self):
        """Setup cleanup handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        atexit.register(self.cleanup)
        
    def signal_handler(self, signum, frame):
        """Handle system signals for cleanup"""
        print(f"Received signal {signum}, shutting down...")
        if not self._cleanup_called:
            self.cleanup()
        # Don't call sys.exit(0) as it would trigger atexit again
        self.app.quit()
        
    def cleanup(self):
        """Cleanup all resources with proper shutdown sequence"""
        # Prevent multiple cleanup calls
        if self._cleanup_called:
            print("Cleanup already called, skipping...")
            return True
        
        self._cleanup_called = True
        print("Starting LockIn shutdown sequence...")
        
        try:
            # Step 1: Allow all windows to close (but don't close them yet)
            if hasattr(self, 'app_manager') and self.app_manager:
                self.app_manager.allow_closing()
                
            if hasattr(self, 'ai_chat') and self.ai_chat:
                self.ai_chat.allow_closing()
                
            if hasattr(self, 'header_window') and self.header_window:
                self.header_window.allow_closing()
            
            # Step 2: Close all managed applications first
            if hasattr(self, 'process_manager') and self.process_manager:
                self.process_manager.close_all_applications()
            
            print("All applications closed. Proceeding with window cleanup...")
            
            # Step 3: Close floating windows
            if hasattr(self, 'app_manager') and self.app_manager:
                print("Closing app manager window...")
                self.app_manager.close()
                
            if hasattr(self, 'ai_chat') and self.ai_chat:
                print("Closing AI chat window...")
                self.ai_chat.close()
            
            # Step 4: Close header window
            if hasattr(self, 'header_window') and self.header_window:
                print("Closing header window...")
                self.header_window.close()
            
            # Step 5: Stop global hotkeys
            if hasattr(self, 'global_hotkeys') and self.global_hotkeys:
                print("Stopping global hotkeys...")
                self.global_hotkeys.stop()
                self.global_hotkeys.wait(3000)  # Wait up to 3 seconds
            
            # Step 6: Clean up virtual desktop
            if hasattr(self, 'virtual_desktop') and self.virtual_desktop:
                print("Cleaning up virtual desktop...")
                self.virtual_desktop.cleanup()
                
        except Exception as e:
            print(f"Error during cleanup: {e}")
        
        print("LockIn shutdown completed.")
        
        # Delay app termination to allow Qt event loop to process cleanup
        print("Scheduling app termination in 1 second...")
        QTimer.singleShot(1000, self.app.quit)
        
        return True
    

    def run(self):
        """Main application entry point"""
        try:
            print("Starting LockIn...")
            
            # Create and switch to virtual desktop
            if not self.virtual_desktop.create_virtual_desktop():
                print("Warning: Could not create virtual desktop, continuing with current desktop")
            
            # Create the three separate windows
            self.create_windows()
            
            print("LockIn started successfully!")
            return self.app.exec()
            
        except Exception as e:
            print(f"Error starting LockIn: {e}")
            self.cleanup()
            return 1
    
    def create_windows(self):
        """Create and show the three separate windows"""
        from ui.header_window import HeaderWindow
        from ui.floating_app_manager import FloatingAppManager
        from ui.floating_ai_chat import FloatingAIChat
        
        # Connect process manager to virtual desktop for proper isolation
        self.process_manager.set_virtual_desktop(self.virtual_desktop)
        
        # Create header window (spans top of screen, stays behind)
        self.header_window = HeaderWindow(
            self.config,
            self.virtual_desktop,
            self.process_manager
        )
        self.header_window.close_requested.connect(self.cleanup_and_exit)
        self.header_window.show()
        
        # Create floating app manager (left side, always on top)
        self.app_manager = FloatingAppManager(
            self.config,
            self.virtual_desktop,
            self.process_manager
        )
        self.app_manager.show()
        
        # Create floating AI chat (right side, always on top)
        self.ai_chat = FloatingAIChat(
            self.config,
            self.virtual_desktop,
            self.process_manager
        )
        self.ai_chat.show()
        
        # Store references to prevent garbage collection
        self.main_window = None  # No longer using a main window
        self.windows = [self.header_window, self.app_manager, self.ai_chat]
        
        # Setup global keyboard shortcuts
        self.setup_keyboard_shortcuts()
    
    def setup_keyboard_shortcuts(self):
        """Setup true global keyboard shortcuts using Windows API"""
        try:
            self.global_hotkeys = GlobalHotkeyManager()
            self.global_hotkeys.hotkey_pressed.connect(self.handle_global_hotkey)
            self.global_hotkeys.start()
            print("🎯 Setting up true global hotkeys: Ctrl+T (App Manager), Ctrl+U (AI Chat)")
        except Exception as e:
            print(f"❌ Failed to setup global hotkeys: {e}")
            # Fallback to Qt shortcuts
            self._setup_fallback_shortcuts()
    
    def _setup_fallback_shortcuts(self):
        """Setup fallback Qt shortcuts if global hotkeys fail"""
        print("⚠️ Using fallback Qt shortcuts (only work when LockIn has focus)")
        # Ctrl+T for App Manager
        self.app_manager_shortcut = QShortcut(QKeySequence("Ctrl+T"), self.app)
        self.app_manager_shortcut.setContext(Qt.ApplicationShortcut)
        self.app_manager_shortcut.activated.connect(self.toggle_app_manager)
        
        # Ctrl+U for AI Chat
        self.ai_chat_shortcut = QShortcut(QKeySequence("Ctrl+U"), self.app)
        self.ai_chat_shortcut.setContext(Qt.ApplicationShortcut)
        self.ai_chat_shortcut.activated.connect(self.toggle_ai_chat)
    
    def handle_global_hotkey(self, hotkey_id):
        """Handle global hotkey presses"""
        if hotkey_id == GlobalHotkeyManager.HOTKEY_CTRL_T:
            self.toggle_app_manager()
        elif hotkey_id == GlobalHotkeyManager.HOTKEY_CTRL_U:
            self.toggle_ai_chat()
    
    def toggle_app_manager(self):
        """Toggle app manager window and focus input field"""
        if self.app_manager:
            self.app_manager.toggle_minimize_with_focus()
    
    def toggle_ai_chat(self):
        """Toggle AI chat window and focus input field"""
        if self.ai_chat:
            self.ai_chat.toggle_minimize_with_focus()
    
    def cleanup_and_exit(self):
        """Cleanup and exit the application"""
        if self.cleanup():
            # Exit if cleanup was successful
            self.app.quit()
        else:
            # This shouldn't happen anymore since cleanup always returns True
            print("Cleanup completed with some issues")


if __name__ == "__main__":
    app = LockInApp()
    exit_code = app.run()
    sys.exit(exit_code) 