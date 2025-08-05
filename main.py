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
import pygame
from potionManager import PotionManager

LOG_FMT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d ▶ %(message)s"
logging.basicConfig(
    level=logging.INFO,                  # 전체 기본레벨
    format=LOG_FMT,
    handlers=[
        logging.FileHandler("bot_debug.log", mode="w", encoding="utf-8"),
        logging.StreamHandler()
    ]
)


pygame.mixer.init()
pygame.mixer.music.load("alerts/siren.mp3")
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
        self.waypoints = waypoints
        self.index = 0

    def current_wp(self):
        return self.waypoints[self.index]

    def advance(self):
        self.index = (self.index + 1) % len(self.waypoints)

# ---------- 2. 미니맵 위치 추적 ----------

class MinimapTracker:
    def __init__(self, top_left_img, bottom_right_img, me_img,
                 minimap_emitter=None,    # QImage 를 받을 콜백
                 pos_emitter=None):
        self.top_left_img = top_left_img
        self.bottom_right_img = bottom_right_img
        self.me_img = me_img
        self.minimap_area = (0, 0, Config.END_X,Config.END_Y)
        self.current_position = None

        # UI 로 보낼 콜백
        self._emit_minimap_img = minimap_emitter
        self._emit_position    = pos_emitter

        self.other_detected = False
        self.cnt_found_other = 0

    
    def capture_minimap(self):
        tl = pyautogui.locateOnScreen(self.top_left_img, confidence=0.8)
        br = pyautogui.locateOnScreen(self.bottom_right_img, confidence=0.8)
        if not tl or not br:
            print("[ERROR] 미니맵 캡처 실패")
            return
        x1, y1 = int(tl.left), int(tl.top)
        x2, y2 = int(br.left + br.width), int(br.top + br.height)
        
        self.minimap_area = (
            x1,
            y1,
            int(x2 - x1),
            int(y2 - y1)
        )
        
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

            if self._emit_position:
                # emit None or (x,y)
                self._emit_position(self.current_position)
            time.sleep(0.2)

    def find_other_position(self):
        other_img = cv2.imread("windows_png/other.png")
        if other_img is None:
            print("Error: other_img 파일을 읽을 수 없습니다.")
            return
        
        while True:
            with mss.mss() as sct:
                x, y, w, h = self.minimap_area
                monitor = {"left": x, "top": y, "width": w, "height": h}
                screen = np.array(sct.grab(monitor))[:, :, :3]  # BGR 컬러

            # 이미지 타입과 채널 맞추기
            if other_img.shape[2] != 3:
                other_img = cv2.cvtColor(other_img, cv2.COLOR_GRAY2BGR)
            
            if screen.dtype != other_img.dtype:
                other_img = other_img.astype(screen.dtype)

            result = cv2.matchTemplate(screen, other_img, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val >= 0.7:
                self.cnt_found_other += 1
                if self.cnt_found_other == 3:
                    pygame.mixer.music.play(-1)
                self.other_detected = True
            else:
                if self.cnt_found_other > 0:
                    self.cnt_found_other -= 1
                else:
                    pygame.mixer.music.stop()
                if self.cnt_found_other == 0:
                    self.other_detected = False
            time.sleep(3)

    def capturing_minimap(self):
        tl = pyautogui.locateOnScreen(self.top_left_img, confidence=0.8)
        br = pyautogui.locateOnScreen(self.bottom_right_img, confidence=0.8)
        if not tl or not br:
            print("[ERROR] 미니맵 캡처 실패")
            return

        x1, y1 = int(tl.left), int(tl.top)
        x2, y2 = int(br.left + br.width), int(br.top + br.height)
        self.minimap_area = (x1, y1, x2 - x1, y2 - y1)

        with mss.mss() as sct:
            left, top, w, h = self.minimap_area
            monitor = {"left": left, "top": top, "width": w, "height": h}
            img = np.array(sct.grab(monitor))[:, :, :3]   # BGR

        # 파일로 저장 대신, UI 로 전송
        if self._emit_minimap_img:
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            height, width, ch = rgb.shape
            qimg = QImage(rgb.data, width, height, ch*width, QImage.Format_RGB888)
            # copy() 해서 안전하게 넘기기
            self._emit_minimap_img(qimg.copy())

# ---------- 3. 물약 매니저 ----------


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
        self.minimap.capture_minimap()
        self.route = RoutePatrol(route_ptrol)
     
        self.shift_down = self.left_down = self.up_down = self.right_down = self.z_down = False
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
        for k in ('shift', 'left', 'right', 'up', 'down', 'z'):
            pyautogui.keyUp(k)
        self.shift_down = self.left_down = self.right_down = self.up_down = False     
    def _ensure_key(self, key, flag_attr, value):
        if value:  
            pyautogui.keyDown(key)
            setattr(self, flag_attr, True)
        else:
            pyautogui.keyUp(key)
            setattr(self, flag_attr, False)
        
    # ----------------------------------------------------------------
    def move_toward(self, target_x, action):
        """목표 x 로 이동. action='ladder' 면 1픽셀, 나머지는 5픽셀 오차로 멈춘다"""
        cur_x = self.minimap.current_position[0]
        dx = target_x - cur_x
        
        self.loger.debug(f"[MOVE] cur_x={cur_x:3}  target_x={target_x:3}  dx={dx:+3}")
        thresh = 1 if action == "ladder" else 5   # ★ 차별화
        
        self._ensure_key('z',  'z_down', True)
        
        if dx < -thresh:
            self._ensure_key('left',  'left_down', True)
            if self.right_down:
                self._ensure_key('right',  'right_down', False)
        elif dx > thresh:
            self._ensure_key('right', 'right_down', True)
            if self.left_down:
                self._ensure_key('left',  'left_down', False)

        # ── 오차 범위 안(정지) ───────────────
        else:
            if self.left_down or self.right_down:
                self.loger.debug("  → STOP (x 오차 허용범위)")
            if self.left_down:  self._ensure_key('left',  'left_down', False)
            if self.right_down: self._ensure_key('right',  'right_down', False)

        

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
            if self.shift_down:
                self._ensure_key('shift',  'shift_down', False)
                return
            if self.left_down:  
                self._ensure_key('left',  'left_down', True)
            else:
                self._ensure_key('right',  'right_down', True)
            
            pyautogui.press("alt")        # 사다리 붙기용 점프
            self._ensure_key('up',  'up_down', True)

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
                self._ensure_key('up',  'up_down', False)
                self._ensure_key('left',  'left_down', False)
                self._ensure_key('right',  'right_down', False)
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
        threading.Thread(target=self.minimap.find_other_position, daemon=True).start()
        last_search, targets = 0, []
        while self.running:
            if self.paused or self.minimap.other_detected:
                time.sleep(0.1)
                self._release_all_keys()
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

                if dist <= 220:         # 사정거리 안
                    # ── (1) 몬스터 쪽으로 캐릭터 방향 고정 ──
                    if dx < 0:        # 왼쪽
                        self._ensure_key('left',  'left_down', True)
                        time.sleep(0.1)
                        self._ensure_key('left',  'left_down', False)
                       
                    else: 
                        self._ensure_key('right',  'right_down', True)
                        time.sleep(0.1)
                        self._ensure_key('right',  'right_down', False)

                    # (2) 공격키 유지
                    if not self.shift_down:
                        self._ensure_key('z',  'z_down', False)
                        self._ensure_key('up',  'up_down', False)
                        self._ensure_key('shift',  'shift_down', True)
                        attack_now = True
                        print("[INFO] 공격")

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
                        self._ensure_key('right',  'right_down', True)
                        pyautogui.keyDown('alt'); time.sleep(0.4)
                        self._ensure_key('right',  'right_down', False)
                        pyautogui.keyUp('alt')
                        self._ensure_key('z',  'z_down', False)
                        self.sync_waypoint_to_y()
                        # self.reselect_waypoint()
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
                        self._ensure_key('shift',  'shift_down', False)
                        self._ensure_key('z',  'z_down', True)
                        print("[INFO] 공격 중지")
            # (1) 공격 → 비공격 전환 순간에 WP 재선택
            if  self.was_attacking and not attack_now and not self.up_down:
                # self.reselect_waypoint()
                self.sync_waypoint_to_y()

            self.was_attacking = attack_now
            if not attack_now and self.shift_down:
                self._ensure_key('shift',  'shift_down', False)
                self._ensure_key('z',  'z_down', True)
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

          
            else:
                self.move_toward(target_x, act)
             
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