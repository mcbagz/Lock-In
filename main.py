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
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon

from core.virtual_desktop import VirtualDesktopManager
from core.process_manager import ProcessManager
from utils.config import ConfigManager


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
            
            # Step 5: Clean up virtual desktop
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