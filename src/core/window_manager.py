"""
Window Management for LockIn
Handles positioning, resizing, and organizing application windows
"""

import win32gui
import win32con
import win32api
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from PySide6.QtCore import QRect
from enum import Enum


class WindowLayout(Enum):
    MAXIMIZED = "maximized"
    TILED_HORIZONTAL = "tiled_horizontal"
    TILED_VERTICAL = "tiled_vertical"
    TILED_QUAD = "tiled_quad"
    FLOATING = "floating"


@dataclass
class WindowArea:
    x: int
    y: int
    width: int
    height: int
    
    def to_rect(self) -> QRect:
        return QRect(self.x, self.y, self.width, self.height)


class WindowManager:
    def __init__(self, main_window_geometry: QRect):
        self.main_window_geometry = main_window_geometry
        self.managed_windows: Dict[int, dict] = {}
        self.current_layout = WindowLayout.MAXIMIZED
        
        # Calculate available area (excluding sidebars)
        self.sidebar_width = 300  # Width of each sidebar
        self.available_area = WindowArea(
            x=main_window_geometry.x() + self.sidebar_width,
            y=main_window_geometry.y(),
            width=main_window_geometry.width() - (2 * self.sidebar_width),
            height=main_window_geometry.height()
        )
    
    def add_window(self, hwnd: int, app_id: str, app_name: str):
        """Add a window to be managed"""
        if not win32gui.IsWindow(hwnd):
            return False
        
        try:
            # Store original window info
            original_rect = win32gui.GetWindowRect(hwnd)
            original_style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            
            self.managed_windows[hwnd] = {
                'app_id': app_id,
                'app_name': app_name,
                'original_rect': original_rect,
                'original_style': original_style,
                'is_managed': True
            }
            
            # Apply current layout
            self.apply_layout()
            return True
            
        except Exception as e:
            print(f"Error adding window {hwnd}: {e}")
            return False
    
    def remove_window(self, hwnd: int):
        """Remove a window from management"""
        if hwnd in self.managed_windows:
            try:
                # Restore original window properties if needed
                window_info = self.managed_windows[hwnd]
                # Could restore original position/size here if desired
                
                del self.managed_windows[hwnd]
                self.apply_layout()  # Reorganize remaining windows
                
            except Exception as e:
                print(f"Error removing window {hwnd}: {e}")
    
    def set_layout(self, layout: WindowLayout):
        """Change the window layout"""
        self.current_layout = layout
        self.apply_layout()
    
    def apply_layout(self):
        """Apply the current layout to all managed windows"""
        visible_windows = self._get_visible_managed_windows()
        
        if not visible_windows:
            return
        
        if self.current_layout == WindowLayout.MAXIMIZED:
            self._apply_maximized_layout(visible_windows)
        elif self.current_layout == WindowLayout.TILED_HORIZONTAL:
            self._apply_tiled_horizontal_layout(visible_windows)
        elif self.current_layout == WindowLayout.TILED_VERTICAL:
            self._apply_tiled_vertical_layout(visible_windows)
        elif self.current_layout == WindowLayout.TILED_QUAD:
            self._apply_tiled_quad_layout(visible_windows)
        elif self.current_layout == WindowLayout.FLOATING:
            self._apply_floating_layout(visible_windows)
    
    def _get_visible_managed_windows(self) -> List[int]:
        """Get list of visible managed windows"""
        visible = []
        for hwnd in list(self.managed_windows.keys()):
            try:
                if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                    if not win32gui.IsIconic(hwnd):
                        visible.append(hwnd)
                else:
                    del self.managed_windows[hwnd]
            except:
                if hwnd in self.managed_windows:
                    del self.managed_windows[hwnd]
        
        return visible
    
    def _apply_maximized_layout(self, windows: List[int]):
        """Apply maximized layout"""
        if not windows:
            return
        
        for i, hwnd in enumerate(windows):
            if i == 0:
                self._position_window(hwnd, self.available_area)
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            else:
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
    
    def _apply_tiled_horizontal_layout(self, windows: List[int]):
        """Apply horizontal tiling"""
        if not windows:
            return
        
        window_width = self.available_area.width // len(windows)
        
        for i, hwnd in enumerate(windows):
            area = WindowArea(
                x=self.available_area.x + (i * window_width),
                y=self.available_area.y,
                width=window_width,
                height=self.available_area.height
            )
            self._position_window(hwnd, area)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    
    def _apply_tiled_vertical_layout(self, windows: List[int]):
        """Apply vertical tiling"""
        if not windows:
            return
        
        window_height = self.available_area.height // len(windows)
        
        for i, hwnd in enumerate(windows):
            area = WindowArea(
                x=self.available_area.x,
                y=self.available_area.y + (i * window_height),
                width=self.available_area.width,
                height=window_height
            )
            self._position_window(hwnd, area)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    
    def _apply_tiled_quad_layout(self, windows: List[int]):
        """Apply quad tiling"""
        if not windows:
            return
        
        quad_width = self.available_area.width // 2
        quad_height = self.available_area.height // 2
        
        positions = [
            (0, 0), (quad_width, 0),
            (0, quad_height), (quad_width, quad_height)
        ]
        
        for i, hwnd in enumerate(windows[:4]):
            pos_x, pos_y = positions[i]
            area = WindowArea(
                x=self.available_area.x + pos_x,
                y=self.available_area.y + pos_y,
                width=quad_width,
                height=quad_height
            )
            self._position_window(hwnd, area)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        
        for hwnd in windows[4:]:
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
    
    def _apply_floating_layout(self, windows: List[int]):
        """Apply floating layout - windows can be freely positioned"""
        for hwnd in windows:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            # Don't force positioning in floating mode
    
    def _position_window(self, hwnd: int, area: WindowArea):
        """Position and resize a window"""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOP,
                area.x, area.y, area.width, area.height,
                win32con.SWP_SHOWWINDOW
            )
        except Exception as e:
            print(f"Error positioning window {hwnd}: {e}")
    
    def focus_window(self, hwnd: int) -> bool:
        """Bring a specific window to focus"""
        if hwnd not in self.managed_windows:
            return False
        
        try:
            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            
            # Bring to foreground
            win32gui.SetForegroundWindow(hwnd)
            
            # If in maximized layout, show only this window
            if self.current_layout == WindowLayout.MAXIMIZED:
                self._apply_maximized_layout([hwnd])
            
            return True
            
        except Exception as e:
            print(f"Error focusing window {hwnd}: {e}")
            return False
    
    def get_window_list(self) -> List[dict]:
        """Get list of managed windows"""
        window_list = []
        
        for hwnd, info in self.managed_windows.items():
            try:
                if win32gui.IsWindow(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    is_visible = win32gui.IsWindowVisible(hwnd)
                    is_minimized = win32gui.IsIconic(hwnd)
                    
                    window_list.append({
                        'hwnd': hwnd,
                        'app_id': info['app_id'],
                        'app_name': info['app_name'],
                        'title': window_title,
                        'is_visible': is_visible,
                        'is_minimized': is_minimized
                    })
            except:
                continue
        
        return window_list
    
    def update_available_area(self, new_geometry: QRect):
        """Update the available area when main window is resized"""
        self.main_window_geometry = new_geometry
        self.available_area = WindowArea(
            x=new_geometry.x() + self.sidebar_width,
            y=new_geometry.y(),
            width=new_geometry.width() - (2 * self.sidebar_width),
            height=new_geometry.height()
        )
        
        # Reapply current layout with new dimensions
        self.apply_layout() 