import pygetwindow as gw
import subprocess
import platform
import time
import cv2
import mss
import numpy as np
import threading



END_X = 1280
END_Y = 720
IMG_PATH = 'windows_png'
# ---------- 1. 윈도우/맥 창 조절 ----------
class GameWindowController:
    global IMG_PATH, END_X, END_Y

    def __init__(self, title, width, height):
        self.title = title
        self.width = width
        self.height = height

    def resize(self):
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


# ---------- 2. 미니맵 위치 추적 ----------
class MinimapTracker:
    def __init__(self, top_left_img, bottom_right_img, me_img):
        self.top_left_img = top_left_img
        self.bottom_right_img = bottom_right_img
        self.me_img = me_img
        self.minimap_area = (0, 0, END_X, END_Y)
        self.current_position = None

    
    def update_position(self):
        print("update_position")
        while True:
            with mss.mss() as sct:
                x, y, w, h = self.minimap_area
                monitor = {"left": x, "top": y, "width": w, "height": h}
                screen = np.array(sct.grab(monitor))[:, :, :3]

            me = cv2.imread(self.me_img)
            result = cv2.matchTemplate(screen, me, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val >= 0.7:
                cx = max_loc[0] + me.shape[1] // 2 + x
                cy = max_loc[1] + me.shape[0] // 2 + y
                self.current_position = (cx, cy)
                print(f"[INFO] 내 위치: {self.current_position}")
            else:
                self.current_position = None
            time.sleep(1)


if __name__ == "__main__":
    GameWindowController("MapleStory Worlds", END_X, END_Y).resize()
    time.sleep(0.5)
    # bot.minimap.capture_minimap()
    # threading.Thread(target=bot.minimap.update_position, daemon=True).start()
    threading.Thread(target=MinimapTracker(
        "windows_png" + "/minimap_topLeft.png",
        "windows_png" + "/minimap_bottomRight.png",
        "windows_png" + "/me.png"
    ).update_position, daemon=True).start()

    while True:
        pass

    