import pygetwindow as gw
import pyautogui
import subprocess
import platform
import time
import cv2
import mss
import numpy as np
import os
import random
import math
import threading
from constant import route_ptrol
from collections import deque
from PyQt5.QtGui import QImage

from me import MinimapTracker
from potionManager import PotionManager
from slimeDetector import SlimeDetector
from slimeHunterBot import SlimeHunterBot
END_X = 1280
END_Y = 720
IMG_PATH = 'windows_png'
# ---------- 1. 윈도우/맥 창 조절 ----------
class GameWindowController:

    def __init__(self, title, width, height):
        self.title = title
        self.width = width
        self.height = height

    def resize(self):
        global IMG_PATH, END_X, END_Y
        if platform.system() == "Windows":
            IMG_PATH = "windows_png"
            END_X = self.width = 970
            END_Y = self.height =700
            self.resize_windows()
        elif platform.system() == "Darwin":
            self.resize_mac()

    def resize_windows(self):
        windows = gw.getWindowsWithTitle(self.title)
        if windows:
            win = windows[0]
            win.moveTo(0, 0)
            win.resizeTo(self.width, self.height)
            print(f"[INFO] '{win.title}' 창 크기 설정 완료.")
        else:
            print(f"[ERROR] 창을 찾을 수 없음: {self.title}")

    def resize_mac(self):
        script = f'''
        tell application "System Events"
            set targetApp to first application process whose name contains "{self.title}"
            set frontmost of targetApp to true
            tell window 1 of targetApp
                set size to {{{self.width}, {self.height}}}
                set position to {{0, 0}}
            end tell
        end tell
        '''
        subprocess.run(["osascript", "-e", script])

class RoutePatrol:
    """사용자가 미리 정한 경로를 무한 반복한다."""
    def __init__(self, waypoints):
        """
        waypoints: list of dicts
            [{ "x":100, "y":120, "action":"move"   },
             { "x":300, "y":120, "action":"jump"   },
             { "x": 57, "y":140, "action":"ladder" }]
        """
        self.waypoints = waypoints
        self.index = 0

    def current_wp(self):
        return self.waypoints[self.index]

    def advance(self):
        self.index = (self.index + 1) % len(self.waypoints)




if __name__ == "__main__":
    GameWindowController("MapleStory Worlds", END_X, END_Y).resize()
    time.sleep(0.5)
    bot = SlimeHunterBot()
    
    # bot.minimap.capture_minimap()

    threading.Thread(
        target=PotionManager(
            "windows_png" + "/hp_bar_empty.png",
            "windows_png" + "/mp_bar_empty.png",
            bar_h_margin=2,      # 템플릿이 바 안쪽만 찍혔으면 0~2px 여유
            bar_v_margin=0,
            hp_thresh=0.6,       # 60 % 미만에서 사용
            mp_thresh=0.6
        ).loop,
        daemon=True
    ).start()
    
    bot.run()