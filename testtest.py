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
from config import Config
import logging

LOG_FMT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d ▶ %(message)s"
logging.basicConfig(
    level=logging.INFO,                  # 전체 기본레벨
    format=LOG_FMT,
    handlers=[
        logging.FileHandler("bot_debug.log", mode="w", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ---------- 1. 윈도우/맥 창 조절 ----------
class GameWindowController:
    def __init__(self, title, width, height):
        self.title = title
        self.width = width
        self.height = height

    def resize(self):
        
        if platform.system() == "Windows":
            Config.IMG_PATH = "windows_png"
            Config.END_X = self.width = 970
            Config.END_Y = self.height =700
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
        self.minimap_area = (0, 0, Config.END_X,Config.END_Y)
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


# ---------- 3. 물약 매니저 ----------
class PotionManager:
    """
    hp_bar.png / mp_bar.png :  바 안쪽(색이 채워지는 영역)을 포함한
                              '한 덩어리' 템플릿.
    bar_color(BGR)          :  HP=(  0,  0,255)  MP=(255,128, 0) 등
    """
    def __init__(self,
                 hp_bar_png, mp_bar_png,
                 bar_h_margin=0, bar_v_margin=0,
                 hp_thresh=0.55, mp_thresh=0.55,
                 interval=0.8):

        self.hp_tpl = cv2.imread(hp_bar_png)
        self.mp_tpl = cv2.imread(mp_bar_png)
        if self.hp_tpl is None or self.mp_tpl is None:
            raise FileNotFoundError("HP/MP 템플릿을 읽지 못했습니다")
        self.hp_roi = None
        self.mp_roi = None
        self.margin_h = bar_h_margin   # ROI 좌우 여유(픽셀)
        self.margin_v = bar_v_margin   # ROI 상하 여유(픽셀)
        self.hp_th  = hp_thresh
        self.mp_th  = mp_thresh
        self.interval = interval
    def _debug_save_match(self, roi, name):
        """
        roi = (x1,y1,x2,y2)를 빨간 박스로 표시해 debug_<name>_*.png 저장
        """
        x1, y1, x2, y2 = roi
        with mss.mss() as sct:
            raw = np.array(sct.grab(
                {"left": 0, "top": 0, "width": Config.END_X, "height": Config.END_Y}
            ))[:, :, :3]

        frame = np.ascontiguousarray(raw)     # OpenCV 호환 레이아웃으로 변환
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

        fn = f"debug_{name}.png"
        cv2.imwrite(fn, frame)
        print(f"[DEBUG] '{fn}' 저장됨 (ROI 시각화)")
    # ──────────────────────────────────────────────
    def _locate_bar_single(self, tpl, label):
        """tpl 위치 한 번 찾고 ROI 반환"""
        with mss.mss() as sct:
            frame = np.array(sct.grab(
                {"left":0, "top":0, "width":Config.END_X, "height": Config.END_Y}
            ))[:, :, :3]

        res = cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        if max_val < 0.65:
            print(f"[WARN] {label} 템플릿 max_val={max_val:.2f} (0.65 미만)")
            return None                 # 매칭 신뢰도 부족

        tx, ty = max_loc
        h, w   = tpl.shape[:2]

        # ROI = 템플릿 + margin
        x1 = max(0, tx - self.margin_h)
        y1 = max(0, ty - self.margin_v)
        x2 = min(Config.END_X, tx + w + self.margin_h)
        y2 = min(Config.END_Y, ty + h + self.margin_v)

        # 디버그 PNG
        self._debug_save_match((x1,y1,x2,y2), label)

        return (x1, y1, x2, y2)

    # ──────────────────────────────────────────────
    def _ensure_rois(self):
        if self.hp_roi is None:
            self.hp_roi = self._locate_bar_single(self.hp_tpl, 'hp')
        if self.mp_roi is None:
            self.mp_roi = self._locate_bar_single(self.mp_tpl, 'mp')

    # ──────────────────────────────────────────────
    @staticmethod
    def _fill_ratio(roi_bgr, filled_color, tol=60):
        """가운데 1 px 라인에서 target 색상 비율"""
        h, w, _ = roi_bgr.shape
        line = roi_bgr[h//2, :, :]
        diff = np.linalg.norm(line.astype(int) - filled_color, axis=1)
        return (diff < tol).mean()

    # ──────────────────────────────────────────────
    def check(self):
        self._ensure_rois()
        if not (self.hp_roi and self.mp_roi):
            return

        with mss.mss() as sct:
            rois = {}
            for name, (x1,y1,x2,y2) in {"hp":self.hp_roi, "mp":self.mp_roi}.items():
                rois[name] = np.array(sct.grab(
                    {"left":x1, "top":y1, "width":x2-x1, "height":y2-y1}
                ))[:, :, :3]

        hp_pct = self._fill_ratio(rois["hp"], (0,0,255))       # HP: 빨강
        mp_pct = self._fill_ratio(rois["mp"], (255,128,0))     # MP: 주황/파랑

        if hp_pct < self.hp_th:
            pyautogui.press('delete')
            print(f"[POTION] HP {hp_pct*100:.0f}% → Del 사용")
        if mp_pct < self.mp_th:
            pyautogui.press('end')
            print(f"[POTION] MP {mp_pct*100:.0f}% → End 사용")

    # ──────────────────────────────────────────────
    def loop(self):
        while True:
            self.check()
            time.sleep(self.interval)




class SlimeDetector:
    def __init__(self, folder):
        self.folder = folder
        self.templates = self._load_templates()

    def _load_templates(self):
        """템플릿을 그레이스케일로만 읽어 두고, 좌우 반전본도 함께 저장"""
        temps = []
        for f in os.listdir(self.folder):
            img = cv2.imread(os.path.join(self.folder, f), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            temps.append(img)
            temps.append(cv2.flip(img, 1))   # 좌우 반전
        return temps
    def find(self):
        with mss.mss() as sct:
            raw = np.array(sct.grab({
                "left": 0, "top": 0,
                "width": Config.END_X,
                "height": Config.END_Y
            }))[:, :, :3]                        # BGR 컬러
        screen = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)  # → 그레이스케일

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
        self.detector = SlimeDetector(Config.IMG_PATH + "/monsters/henesisu")
        self.minimap = MinimapTracker(
            "windows_png" + "/minimap_topLeft.png",
            "windows_png" + "/minimap_bottomRight.png",
            "windows_png" + "/me.png"
        )
        # self.terrain = TerrainNavigator()
        self.route = RoutePatrol(route_ptrol)
         # 키 상태
        self.shift_down = self.left_down = self.right_down = self.z_down = False
        self.running = True   
        self.paused  = False
        self.frame_emitter = None
        self.last_z_refresh = time.time()
        self.was_attacking = False

        self.char_tpl  = cv2.imread(Config.IMG_PATH + "/charactor.png")
        self.char_thresh  = 0.55

        self.stuck_attack_cnt = 0
        self.prev_char_pos    = None
        self.loger = logging.getLogger("SlimeBot")      # 전역 로거 하나 잡아두기
# 예: 더 자세히 보고 싶을 때
        self.loger.setLevel(logging.DEBUG)      # DEBUG / INFO / WARNING / ERROR


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
        self.loger.info(f"[WP] Reselect → #{nearest}  (cur=({mx},{my}))")
        print(f"[INFO] WP 재선택 → #{nearest}")

    def _ensure_key(self, key, flag_attr):
        """flag 값과 무관하게 매 사이클 keyDown을 한 번 더 보내 안전하게 유지"""
        pyautogui.keyDown(key)
        setattr(self, flag_attr, True)
    # ----------------------------------------------------------------
    def move_toward(self, target_x, action):
        """목표 x 로 이동. action='ladder' 면 1픽셀, 나머지는 5픽셀 오차로 멈춘다"""
        cur_x = self.minimap.current_position[0]
        dx = target_x - cur_x
        
        self.loger.debug(f"[MOVE] cur_x={cur_x:3}  target_x={target_x:3}  dx={dx:+3}")
        thresh = 1 if action == "ladder" else 5   # ★ 차별화

        # ── 왼쪽 이동 ───────────────────────
        # if dx < -thresh:
        #     if not self.left_down:
        #         pyautogui.keyDown('up');
        #         pyautogui.keyDown('left'); self.left_down = True
        #         pyautogui.keyDown('z');    self.z_down   = True   # ★ 추가
        #         self.loger.debug("  → LEFT Down")
        #     if self.right_down:
        #         pyautogui.keyUp('up');
        #         pyautogui.keyUp('right'); self.right_down = False
                

        # # ── 오른쪽 이동 ─────────────────────
        # elif dx > thresh:
        #     if not self.right_down:
        #         pyautogui.keyDown('up');
        #         pyautogui.keyDown('right'); self.right_down = True
        #         pyautogui.keyDown('z');    self.z_down   = True   # ★ 추가
        #         self.loger.debug("  → RIGHT Down")
        #     if self.left_down:
        #         pyautogui.keyUp('up');
        #         pyautogui.keyUp('left');  self.left_down = False

        if dx < -thresh:
            pyautogui.keyDown('up');
            self._ensure_key('left',  'left_down')
            if self.right_down:
                pyautogui.keyUp('right'); self.right_down = False
        elif dx > thresh:
            pyautogui.keyDown('up');
            self._ensure_key('right', 'right_down')
            if self.left_down:
                pyautogui.keyUp('left');  self.left_down  = False

        # ── 오차 범위 안(정지) ───────────────
        else:
            if self.left_down or self.right_down:
                self.loger.debug("  → STOP (x 오차 허용범위)")
            if self.left_down:  pyautogui.keyUp('left');  self.left_down  = False
            if self.right_down: pyautogui.keyUp('right'); self.right_down = False

        # 대시(z) 유지
        if not self.z_down:
            pyautogui.keyDown('z'); self.z_down = True

    # ----------------------------------------------------------------
    def do_action(self,  wp=None):
        me_x = self.minimap.current_position[0]

        if wp["action"] == "jump":
            print(f"[점프] 나의 X값: {me_x}, Target X값: {wp["x"]}")
            count = wp.get("count") if wp else 1
            
            for _ in range(count):
                pyautogui.press("alt")
                time.sleep(0.5)  
            return True


        if wp["action"] == "ladder":
            self.loger.info(f"[LADDER] from y={self.minimap.current_position[1]} "
                     f"→ end_y={wp.get('end_y')}")
            
            pyautogui.keyUp("shift")

            if self.left_down:  
                pyautogui.keyDown("left")
            else:
                pyautogui.keyDown("right")
            print(f"[사다리-점프] 나의 X값: {me_x}, Target X값: {wp["x"]}")
            pyautogui.press("alt")        # 사다리 붙기용 점프
            pyautogui.keyDown("up")

            try:
                target_y  = wp.get("end_y") if wp else None
                start_t   = time.time()
                max_wait  = 2.5           # ← 전역 타임아웃(초)
                prev_cy   = None
                stall_t   = time.time()

                while True:
                    pos = self.minimap.current_position
                    if not pos:
                        time.sleep(0.05)
                        continue

                    _, cy = pos

                    # ── ① 목표 y 도달 ─────────────────────────
                    if target_y is not None and cy <= target_y :
                        return True

                    # ── ② y 값이 변했는가? (정체 감지) ───────
                    if prev_cy is None or abs(cy - prev_cy) > 1:
                        prev_cy = cy
                        stall_t = time.time()        # 움직임이 있으면 리셋

                    # 0.6 s 동안 y 변화가 없으면 실패로 간주
                    if time.time() - stall_t > 0.6:
                        print("[WARN] 사다리 정체 → 중단")
                        return False

                    # ── ③ 전역 타임아웃 ──────────────────────
                    if time.time() - start_t > max_wait:
                        print("[WARN] 사다리 타임아웃 → 중단")
                        self.loger.warning("    ↳ time-out while climbing")
                        return False

                    time.sleep(0.05)

            finally:
                pyautogui.keyUp("up")
                pyautogui.keyUp("left")
                pyautogui.keyUp("right")
    def visualize(self, detections):
    # ── 1. 현재 전체 화면 캡처 ───────────────────────────
        with mss.mss() as sct:
            monitor = {"top":0, "left":0, "width": Config.END_X, "height": Config.END_Y}
            frame = np.array(sct.grab(monitor))[:, :, :3].copy()   # BGR

        # ── 2. 슬라임 감지 결과 사각형 ------------------------
        for (x, y) in detections:
            cv2.rectangle(frame, (x-25, y-25), (x+25, y+25), (0, 0, 255), 2)

        # ── 3. 경로 웨이포인트 표시 ---------------------------
        for i, wp in enumerate(self.route.waypoints):
            color = (0, 0, 255)                   # 전체: 빨간 점
            radius = 2
            if i == self.route.index:             # 현재 목표 WP
                color = (0, 255, 255)             # 노란 점
                radius = 4
            cv2.circle(frame, (wp["x"], wp["y"]), radius, color, -1)

        # ── 4. PyQt 라벨로 전송 -------------------------------
        if self.frame_emitter is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
            self.frame_emitter.emit(qimg.copy())   # copy() 로 안전 전송

    def reached(self, wp):
        """웨이포인트에 도달했는지 여부를 반환"""
        cx, cy = self.minimap.current_position
        dx = abs(cx - wp["x"])
        dy = abs(cy - wp["y"])
        hit = False
        if wp["action"] == "ladder":
            # 사다리는 x 정밀도만 중요 (+/-1px)
            tol = 1 if not (self.left_down or self.right_down) else 7
            hit=  dx <= tol
        else:
            # 나머지는 x, y 모두 여유 있게
            hit=  dx <= 6 and dy <= 6
        self.loger.debug(f"[REACHED?] wp#{self.route.index} "
                  f"dx={dx:.1f} dy={dy:.1f}  → {hit}")
        return hit
        
    def sync_waypoint_to_y(self):
        print("sync_waypoint_to_y")
        """
        현재 y와 가장 가까운 WP를 찾아 index를 재설정한다.
        ① |y차|가 가장 작은 WP
        ② (동점이면) |x차|가 더 작은 WP
        """
        if not self.minimap.current_position:
            return

        cx, cy = self.minimap.current_position

        best_i = min(
            range(len(self.route.waypoints)),
            key=lambda i: (
                abs(self.route.waypoints[i]["y"] - cy),   # ① y 차
                abs(self.route.waypoints[i]["x"] - cx)    # ② x 차
            )
        )

        if best_i != self.route.index:
            self.route.index = best_i
            self.loger.info(f"[WP] Y-sync → #{best_i}  cur_y={cy}")
            print(f"[INFO] WP 재동기화(Y 기준) → #{best_i} (x:{cx}, y:{cy})")


    def find_char_pos(self):
        """찾으면 (x,y) 반환, 없으면 None"""
        with mss.mss() as sct:
            scr = np.array(sct.grab({
                "left": 0, "top": 0, "width": Config.END_X, "height": Config.END_Y
            }))[:, :, :3]
        res = cv2.matchTemplate(scr, self.char_tpl, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        if max_val < self.char_thresh:
            return None
        h, w = self.char_tpl.shape[:2]
        cx = max_loc[0] + w // 2
        cy = max_loc[1] + h // 2
        return (cx, cy)

    def run(self):
        threading.Thread(target=self.minimap.update_position, daemon=True).start()
        last_search, targets = 0, []
        while self.running:
            if self.paused:
                time.sleep(0.1)
                continue
            if time.time() - last_search > 0.15:
                targets = self.detector.find()
                last_search = time.time()
                if targets:
                    self.visualize(targets)
           
            try: 
                char_pos = self.find_char_pos()
            except:
                print("ERROR char_pos is not found")

            attack_now = False        # ★
            
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
                        attack_now = True
                        print("[INFO] 공격")

                    # (3) 대시(z)는 필요하면 취향대로 유지/해제
                    if self.z_down:
                        pyautogui.keyUp('z'); self.z_down = False

                    # ────── ❶ 같은 자리 연속 공격 카운트 ───────────
                    if self.prev_char_pos and char_pos:
                        if math.hypot(char_pos[0]-self.prev_char_pos[0],
                                    char_pos[1]-self.prev_char_pos[1]) < 3:
                            self.stuck_attack_cnt += 1
                        else:
                            self.stuck_attack_cnt = 1
                    else:
                        self.stuck_attack_cnt = 1
                    self.prev_char_pos = char_pos

                    if self.stuck_attack_cnt >= 3:
                        print("[INFO] 같은 자리 3회 공격 → 강제 이동")
                        self.loger.info("[ATTACK] Same spot 3× → reselection")
                        self._release_all_keys()
                        # (2) 0.4초간 오른쪽으로 대시
                        pyautogui.keyDown('right');
                        pyautogui.keyDown('alt'); time.sleep(0.4)
                        pyautogui.keyUp('right')
                        pyautogui.keyUp('alt')
                        self.reselect_waypoint()
                        self.stuck_attack_cnt = 0
                        # ↑ 강제 이동 결정 후 곧바로 다음 루프
                        time.sleep(0.1)
                        continue
                    # ───────────────────────────────────────────────

                    time.sleep(0.1)
                    continue          # ← 기존 continue (공격 유지 상태)
                else:
                    # 사거리 밖 → 공격키 해제
                    if self.shift_down:
                        pyautogui.keyUp('shift'); self.shift_down = False
                        print("[INFO] 공격 중지")
            # (1) 공격 → 비공격 전환 순간에 WP 재선택
            if self.was_attacking and not attack_now:
                self.reselect_waypoint()

            self.was_attacking = attack_now
            if not attack_now and self.shift_down:
                pyautogui.keyUp('shift')
                self.shift_down = False
                self.stuck_attack_cnt = 0 
            
            # 3) 경로 순찰
            if not self.minimap.current_position:
                time.sleep(0.1); continue      # 내 위치 못 찾으면 대기

            wp = self.route.current_wp()
           
            target_x, target_y, act = wp["x"], wp["y"], wp["action"]
            _, cur_y = self.minimap.current_position

            if target_y > cur_y + 6:          # 목표 y 가 내 y 보다 충분히 더 큼(=아래)
                self.drop_down()
                time.sleep(0.25)              # 낙하 안정화
                continue                      # 다음 loop 에서 다시 판단

            elif target_y + 6 < cur_y :          
                self.sync_waypoint_to_y()

            if self.reached(wp):
                self.do_action(wp)
                self.route.advance()

                if act == "ladder":
                    # 사다리 탄 뒤 충분히 대기 → 좌표 업데이트
                    # time.sleep(0.3)

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
                        time.sleep(0.1)
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
    GameWindowController("MapleStory Worlds", Config.END_X, Config.END_Y).resize()
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