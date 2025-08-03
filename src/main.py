
from multiprocessing import Queue
from worker import MinimapWorker 

from multiprocessing import Process, Queue
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
from PyQt5.QtGui import QImage
from helper import in_rect
from constant import route_ptrol
from collections import deque
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
            time.sleep(0.2)


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


# ---------- 6. 메인 봇 ----------
class SlimeHunterBot:
    def __init__(self):
        self.detector = SlimeDetector(IMG_PATH + "/monsters/henesisu")
        # self.minimap = MinimapTracker("windows_png" + "/minimap_topLeft.png","windows_png" + "/minimap_bottomRight.png", "windows_png" + "/me.png")
        self.minimap = MinimapTracker(
            "windows_png" + "/minimap_topLeft.png",
            "windows_png" + "/minimap_bottomRight.png",
            "windows_png" + "/me.png"
        )
        # self.terrain = TerrainNavigator()
        self.route = RoutePatrol(route_ptrol)
         # 키 상태
        self.shift_down = self.left_down = self.right_down = self.z_down = False
        self.current_dir = None
        self.running = True   
        self.paused  = False
        self.frame_emitter = None
        self.last_z_refresh = time.time()

    def drop_down(self):
        """↓+Alt 로 아래 플랫폼으로 내려가기"""
        pyautogui.keyDown('down')
        pyautogui.press('alt')       # 점프키 → 드랍
        time.sleep(0.12)             # 짧게 눌렀다 떼기
        pyautogui.keyUp('down')

    def set_frame_emitter(self, emitter):
        self.frame_emitter = emitter   # UI/스레드에서 연결해 줌

    def stop(self):
        self.running = False
        self._release_all_keys()

    def pause(self, flag: bool):
        """True → 일시정지, False → 재개"""
        self.paused = flag
        if flag:
            self._release_all_keys()

    def _release_all_keys(self):
        for k in ('left', 'right', 'up', 'down', 'z', 'shift'):
            pyautogui.keyUp(k)
        self.left_down = self.right_down = self.z_down = False
    def keep_z_alive(self):
        if not self.paused and time.time() - self.last_z_refresh >= 0.5:
            pyautogui.keyDown('z'); self.z_down = True
            self.last_z_refresh = time.time()

    # ---------------- 새 함수 ----------------
    def reselect_waypoint(self):
        """현재 좌표에 가장 가까운 WP로 index 재설정"""
        if not self.minimap.current_position:
            return
        mx, my = self.minimap.current_position
        nearest = min(
            range(len(self.route.waypoints)),
            key=lambda i: math.hypot(
                self.route.waypoints[i]["x"] - mx,
                self.route.waypoints[i]["y"] - my
            )
        )
        self.route.index = nearest
        print(f"[INFO] WP 재선택 → #{nearest}")
    # ----------------------------------------------------------------
    def move_toward(self, target_x, action):
        """목표 x 로 이동. action='ladder' 면 1픽셀, 나머지는 5픽셀 오차로 멈춘다"""
        cur_x = self.minimap.current_position[0]
        dx = target_x - cur_x

        thresh = 1 if action == "ladder" else 5   # ★ 차별화

        # ── 왼쪽 이동 ───────────────────────
        if dx < -thresh:
            if not self.left_down:
                pyautogui.keyDown('left'); self.left_down = True
                pyautogui.keyDown('z');    self.z_down   = True   # ★ 추가
            if self.right_down:
                pyautogui.keyUp('right'); self.right_down = False

        # ── 오른쪽 이동 ─────────────────────
        elif dx > thresh:
            if not self.right_down:
                pyautogui.keyDown('right'); self.right_down = True
                pyautogui.keyDown('z');    self.z_down   = True   # ★ 추가
            if self.left_down:
                pyautogui.keyUp('left');  self.left_down = False

        # ── 오차 범위 안(정지) ───────────────
        else:
            if self.left_down:  pyautogui.keyUp('left');  self.left_down  = False
            if self.right_down: pyautogui.keyUp('right'); self.right_down = False

        # 대시(z) 유지
        if not self.z_down:
            pyautogui.keyDown('z'); self.z_down = True

    # ----------------------------------------------------------------
    def do_action(self, action):
        print("엑션: ", action)
        if action == "jump":
            pyautogui.press('alt')              # 단순 점프
        elif action == "ladder":
            self.do_action('jump')              # 단순 점프
            pyautogui.keyDown('up');
            time.sleep(2);
            pyautogui.keyUp('up')

    # def visualize(self, detections):
    #     with mss.mss() as sct:
    #         monitor = {"top": int(0), "left": int(0), "width": int(END_X), "height": int(END_Y)}
    #         screen = np.array(sct.grab(monitor))[:, :, :3].copy()
    #     for (x, y) in detections:
    #         cv2.rectangle(screen, (x-25, y-25), (x+25, y+25), (0, 0, 255), 2)
    #     cv2.imwrite("debug_screen.png", screen)
    #     print("[INFO] debug_screen.png 저장됨")
    
    def visualize(self, detections):
        with mss.mss() as sct:
            monitor = {"top": int(0), "left": int(0), "width": int(END_X), "height": int(END_Y)}
            frame = np.array(sct.grab(monitor))[:, :, :3].copy()    # BGR

        for (x, y) in detections:
            cv2.rectangle(frame, (x-25, y-25), (x+25, y+25), (0, 0, 255), 2)

        # ----- PyQt 라벨로 전송 -----
        if self.frame_emitter is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch*w, QImage.Format_RGB888)
            self.frame_emitter.emit(qimg.copy())   # copy() 로 안전 전송
    def reached(self, wp):
        """웨이포인트에 도달했는지 여부를 반환"""
        cx, cy = self.minimap.current_position
        dx = abs(cx - wp["x"])
        dy = abs(cy - wp["y"])

        if wp["action"] == "ladder":
            # 사다리는 x 정밀도만 중요 (+/-1px)
            return dx == 0
        else:
            # 나머지는 x, y 모두 여유 있게
            return dx <= 6 and dy <= 6

    def run(self):
        threading.Thread(target=self.minimap.update_position, daemon=True).start()
        last_search, targets = 0, []

        while self.running:
            if self.paused:
                time.sleep(0.1)
                continue
            if time.time() - last_search > 0.5:
                targets = self.detector.find()
                last_search = time.time()
                # if targets:
                #     self.visualize(targets)
            char_pos = pyautogui.locateCenterOnScreen(IMG_PATH + "/charactor.png", confidence=0.55)
            if char_pos and targets:
                closest = min(targets, key=lambda t: math.hypot(t[0]-char_pos[0],
                                                                t[1]-char_pos[1]))
                dx = closest[0] - char_pos[0]
                dy = closest[1] - char_pos[1]
                dist = math.hypot(dx, dy)

                if dist <= 220:                       # 사정거리 안
                    # ── (1) 몬스터 쪽으로 캐릭터 방향 고정 ──
                    if dx < 0:        # 왼쪽
                        if not self.left_down:
                            pyautogui.keyDown('left');  self.left_down  = True
                        if self.right_down:
                            pyautogui.keyUp('right');   self.right_down = False
                    else:              # 오른쪽
                        if not self.right_down:
                            pyautogui.keyDown('right'); self.right_down = True
                        if self.left_down:
                            pyautogui.keyUp('left');    self.left_down  = False
                    # ───────────────────────────────────────

                    # (2) 공격키 유지
                    if not self.shift_down:
                        pyautogui.keyDown('shift'); self.shift_down = True
                        print("[INFO] 공격")

                    # (3) 대시(z)는 필요하면 취향대로 유지/해제
                    if self.z_down:
                        pyautogui.keyUp('z'); self.z_down = False

                    time.sleep(0.1)
                    continue
                else:
                    # 사거리 밖 → 공격키 해제
                    if self.shift_down:
                        pyautogui.keyUp('shift'); self.shift_down = False
                        print("[INFO] 공격 중지")
            # (1) 공격 → 비공격 전환 순간에 WP 재선택

            # 3) 경로 순찰
            if not self.minimap.current_position:
                time.sleep(0.1); continue      # 내 위치 못 찾으면 대기

            wp = self.route.current_wp()
           
            target_x, target_y, act = wp["x"], wp["y"], wp["action"]
            cur_x, cur_y = self.minimap.current_position
            if target_y > cur_y + 6:          # 목표 y 가 내 y 보다 충분히 더 큼(=아래)
                self.drop_down()
                time.sleep(0.25)              # 낙하 안정화
                continue                      # 다음 loop 에서 다시 판단
            # 목표점에 도달했는지 확인 (오차 6픽셀)
            if self.reached(wp):
                print('목표점에 도달')
                # 이동키 해제
                if self.left_down:  pyautogui.keyUp('left');  self.left_down  = False
                if self.right_down: pyautogui.keyUp('right'); self.right_down = False
                if self.z_down:     pyautogui.keyUp('z');     self.z_down     = False
                
                # 정점 액션 수행
                self.do_action(act)
                self.route.advance()

                if act == "ladder":
                    # 사다리 탄 뒤 충분히 대기 → 좌표 업데이트
                    time.sleep(0.5)

                    # 다음 WP 와 내 y 좌표 비교
                    next_wp = self.route.current_wp()           # advance() 이후라 이미 다음 WP
                    cy = self.minimap.current_position[1]
                    dy = abs(cy - next_wp["y"])

                    if dy > 6:          # y 차이가 크면 아직 못 올라간 것
                        print("[WARN] 사다리 실패, 재시도")
                        # index 를 이전 WP(사다리)로 되돌림
                        self.route.index = (self.route.index - 1) % len(self.route.waypoints)
                        # 키 상태 초기화(혹시 up 키가 남아 있으면)
                        pyautogui.keyUp('up')
                        # 살짝 쉬고 다음 loop 에서 다시 ladder 시도
                        time.sleep(0.2)
                        continue

                time.sleep(0.2)
            else:
                print("목표 x 쪽으로 걷기, ", target_x)
                self.move_toward(target_x, act)
                self.keep_z_alive()
                # 지형(낙사·사다리·점프) 즉시 대응
                # self.terrain.act(self.minimap.current_position)
           
            time.sleep(0.15)
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