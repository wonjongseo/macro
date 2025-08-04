
# ---------- 2. 미니맵 위치 추적 ----------
import time

import cv2
import mss
import numpy as np
import pyautogui

from main import END_X, END_Y


class MinimapTracker:
    def __init__(self, top_left_img, bottom_right_img, me_img):
        self.top_left_img = top_left_img
        self.bottom_right_img = bottom_right_img
        self.me_img = me_img
        self.minimap_area = (0, 0, END_X, END_Y)
        self.current_position = None

    def capture_minimap(self):
        tl = pyautogui.locateOnScreen(self.top_left_img, confidence=0.8)
        br = pyautogui.locateOnScreen(self.bottom_right_img, confidence=0.8)
        if not tl or not br:
            print("[ERROR] 미니맵 캡처 실패")
            return
        x1, y1 = tl.left, tl.top
        x2, y2 = br.left + br.width, br.top + br.height
        self.minimap_area = (x1, y1, x2 - x1, y2 - y1)
        with mss.mss() as sct:
            monitor = {"left": int(x1), "top": int(y1), "width": int(x2 - x1), "height": int(y2 - y1)}
            img = np.array(sct.grab(monitor))[:, :, :3]
            cv2.imwrite("minimap_capture.png", img)

    def update_position(self):
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
                # print(f"[INFO] 내 위치: {self.current_position}")
            else:
                self.current_position = None
            time.sleep(0.2)

