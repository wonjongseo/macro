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

from helper import in_rect


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
            time.sleep(0.3)


# ---------- 3. 물약 매니저 ----------
class PotionManager:
    def __init__(self, hp_img, mp_img, interval=1.5):
        self.hp_img = cv2.imread(hp_img)
        self.mp_img = cv2.imread(mp_img)
        self.interval = interval

    def check(self):
        with mss.mss() as sct:
            screen = np.array(sct.grab({"left": int(0), "top": int(0), "width": int(END_X), "height": int(END_Y)}))[:, :, :3]

        for img, key, label in [(self.hp_img, 'd', 'HP'), (self.mp_img, 'h', 'MP')]:
            if img is not None:
                res = cv2.matchTemplate(screen, img, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                if max_val > 0.8:
                    pyautogui.press(key)
                    print(f"[INFO] {label} 낮음 → 물약 사용")

    def loop(self):
        while True:
            self.check()
            time.sleep(self.interval)


# ---------- 4. 슬라임 탐지기 ----------
class SlimeDetector:
    def __init__(self, folder):
        self.folder = folder
        self.templates = self.load_templates()

    def load_templates(self):
        temp = []
        for f in os.listdir(self.folder):
            path = os.path.join(self.folder, f)
            img = cv2.imread(path)
            if img is not None:
                temp.append(img)
                temp.append(cv2.flip(img, 1))
        return temp

    def find(self):
        with mss.mss() as sct:
            screen = np.array(sct.grab({"left": 0, "top": 0, "width": END_X, "height": END_Y}))[:, :, :3]
        found = []
        for template in self.templates:
            res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= 0.7)
            h, w = template.shape[:2]
            for pt in zip(*loc[::-1]):
                found.append((pt[0] + w // 2, pt[1] + h // 2))
        return self.remove_duplicates(found)

    def remove_duplicates(self, pts, threshold=20):
        unique = []
        for p in pts:
            if all(math.hypot(p[0] - u[0], p[1] - u[1]) > threshold for u in unique):
                unique.append(p)
        return unique


# ---------- 5. 지형 판단기 ----------
class TerrainNavigator:
    def __init__(self):
        self.jump_zones = []
        self.ladder_zones = [(57, 140, ), ]
        self.fall_zones = [(1000, 1050)]

    def in_zone(self, x, zone): return any(start <= x <= end for (start, end) in zone)
    
    def act(self, pos):
        if not pos: return
        x, y = pos
        
        if self.in_zone(x, self.fall_zones):
            print("[ACT] 낙사 방지 → 정지")
            for k in ['left', 'right', 'z']:
                pyautogui.keyUp(k)
        elif self.in_zone(x, self.ladder_zones):
            print("[ACT] 사다리 오름")
            pyautogui.press('altleft') 
            pyautogui.press('altright') 
            pyautogui.keyDown('up'); time.sleep(1.5); pyautogui.keyUp('up')
        elif self.in_zone(x, self.jump_zones):
            print("[ACT] 점프!")
            pyautogui.keyDown('right')
            pyautogui.press('alt')
            time.sleep(0.6)
            pyautogui.keyUp('right')
        # else:
        #     d = random.choice(['left', 'right'])
        #     print(f"[ACT] 슬라임 없음 → {d}으로 순찰")
        #     pyautogui.keyDown(d)
        #     time.sleep(random.uniform(0.5, 1.0))
        #     pyautogui.keyUp(d)


# ---------- 6. 메인 봇 ----------
class SlimeHunterBot:
    def __init__(self):
        print('IMG_PATH' + IMG_PATH)
        self.detector = SlimeDetector(IMG_PATH + "/monsters/henesisu")
        # self.minimap = MinimapTracker("windows_png" + "/minimap_topLeft.png","windows_png" + "/minimap_bottomRight.png", "windows_png" + "/me.png")
        self.minimap = MinimapTracker(
            "windows_png" + "/minimap_topLeft.png",
            "windows_png" + "/minimap_bottomRight.png",
            "windows_png" + "/me.png"
        )
        self.terrain = TerrainNavigator()

        self.shift_down = self.left_down = self.right_down = self.z_down = False
        self.current_dir = None
    def visualize(self, detections):
        with mss.mss() as sct:
            monitor = {"top": int(0), "left": int(0), "width": int(END_X), "height": int(END_Y)}
            screen = np.array(sct.grab(monitor))[:, :, :3].copy()
        for (x, y) in detections:
            cv2.rectangle(screen, (x-25, y-25), (x+25, y+25), (0, 0, 255), 2)
        cv2.imwrite("debug_screen.png", screen)
        print("[INFO] debug_screen.png 저장됨")
        

    def run(self):

        while True:
            self.terrain.act(self.minimap.current_position)
            time.sleep(0.5)
        last_search = 0
        targets = []

        while True:
            char_pos = pyautogui.locateCenterOnScreen("windows_png" + "/charactor.png", confidence=0.6)
            if time.time() - last_search > 0.8:
                targets = self.detector.find()
                last_search = time.time()
                if targets:
                    self.visualize(targets)

            if not char_pos or not targets:
                print("[INFO] 캐릭터 또는 슬라임 없음")
                print(self.minimap.current_position)
                self.terrain.act(self.minimap.current_position)
                time.sleep(0.5)
                continue

            # 기본 전투 로직은 기존 유지
            closest = min(targets, key=lambda t: math.hypot(t[0] - char_pos[0], t[1] - char_pos[1]))
            dx = closest[0] - char_pos[0]
            dist = math.hypot(dx, closest[1] - char_pos[1])
            dir = 'right' if dx > 0 else 'left'
            print(f"[INFO] 거리: {dist:.1f}, 방향: {dir}")

            if dist <= 220:
                if dir == self.current_dir:
                    if self.z_down:
                        pyautogui.keyUp('z')
                        self.z_down = False
                    if not self.shift_down:
                        pyautogui.keyDown('shift')
                        self.shift_down = True
                else:
                    print("[INFO] 방향 안 맞음 → 재조정 필요")
            else:
                if self.shift_down:
                    pyautogui.keyUp('shift')
                    self.shift_down = False
                if dir == 'left':
                    if not self.left_down:
                        pyautogui.keyDown('left')
                        self.left_down = True
                        self.current_dir = 'left'
                    if self.right_down:
                        pyautogui.keyUp('right')
                        self.right_down = False
                else:
                    if not self.right_down:
                        pyautogui.keyDown('right')
                        self.right_down = True
                        self.current_dir = 'right'
                    if self.left_down:
                        pyautogui.keyUp('left')
                        self.left_down = False
                if not self.z_down:
                    pyautogui.keyDown('z')
                    self.z_down = True

            time.sleep(0.2)


if __name__ == "__main__":
    GameWindowController("MapleStory Worlds", END_X, END_Y).resize()
    time.sleep(0.5)
    bot = SlimeHunterBot()
    
    # bot.minimap.capture_minimap()
    threading.Thread(target=bot.minimap.update_position, daemon=True).start()
    # threading.Thread(target=MinimapTracker(
    #     "windows_png" + "/minimap_topLeft.png",
    #     "windows_png" + "/minimap_bottomRight.png",
    #     "windows_png" + "/me.png"
    # ).update_position, daemon=True).start()

    # threading.Thread(target=PotionManager(
    #     "windows_png" + "/hp_bar_empty.png",
    #     "windows_png" + "/mp_bar_empty.png"
    # ).loop, daemon=True).start()
    
    bot.run()