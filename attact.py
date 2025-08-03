
import pygetwindow as gw
import pyautogui
import time
import platform
import pygetwindow as gw
import os
import cv2
import mss
import time
import numpy as np
import math
import time
import subprocess
import random  # 상단에 추가 필요
import threading
TARGET_TITLE = "MapleStory Worlds"  # 창 제목에 포함되는 문자열
SCREEN_X_START = 0
SCREEN_X_END = 1280
SCREEN_Y_START = 0
SCREEN_Y_END = 720

def resize_window_windows(title_keyword="MapleStory Worlds", x=0, y=0, width=1280, height=720):
    try:
        windows = gw.getWindowsWithTitle(title_keyword)
        if not windows:
            print(f"[ERROR] '{title_keyword}'를 포함하는 창을 찾을 수 없습니다.")
            return

        win = windows[0]  # 가장 첫 번째 창 사용
        win.moveTo(x, y)
        win.resizeTo(width, height)
        print(f"[INFO] '{win.title}' 창을 {width}x{height} 크기로 이동 및 최상단으로 이동 완료.")
    except Exception as e:
        print(f"[ERROR] 창 크기 조절 중 예외 발생: {e}")
def resize_mac_window(app_name="MapleStory Worlds MapleStory Worlds", x=0, y=0, width=1280, height=720):
    script = f'''
    tell application "System Events"
        set targetApp to first application process whose name contains "{app_name}"
        set frontmost of targetApp to true -- 창을 최상단으로 가져오기
        tell window 1 of targetApp
            set size to {{{width}, {height}}}
            set position to {{{x}, {y}}}
        end tell
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"[INFO] '{app_name}' 창을 {width}x{height} 크기로 이동 및 최상단으로 이동 완료.")
    else:
        print(f"[ERROR] AppleScript 실행 실패:\n{result.stderr}")



MINIMAP_TOP_LEFT = (SCREEN_X_START, SCREEN_Y_START)   # x, y
MINIMAP_BOTTOM_RIGHT = (SCREEN_X_END, SCREEN_Y_END)  # x, y

ME_IMAGE_PATH = "pngs/me.png"
ME_CONFIDENCE = 0.7
current_me_position = None  # (x, y) 형태로 저장됨ddd

def capture_minimap(top_left_img='windows_png/minimap_topLeft.png', bottom_right_img='windows_png/minimap_bottomRight.png', save_path='windows_png/minimap_capture.png'):
    print("[INFO] 미니맵 영역 감지 시작...")

    # top-left 찾기
    top_left = pyautogui.locateOnScreen(top_left_img, confidence=0.8)
    if not top_left:
        print("[ERROR] top-left 이미지 인식 실패")
        return
    
    # bottom-right 찾기
    bottom_right = pyautogui.locateOnScreen(bottom_right_img, confidence=0.8)
    if not bottom_right:
        print("[ERROR] bottom-right 이미지 인식 실패")
        return

    # 좌표 계산
    x1, y1 = top_left.left, top_left.top
    x2, y2 = bottom_right.left + bottom_right.width, bottom_right.top + bottom_right.height

    MINIMAP_TOP_LEFT = (x1, y1)
    MINIMAP_BOTTOM_RIGHT = (x2,y2)
    width, height = x2 - x1, y2 - y1

    print(f"[INFO] 미니맵 영역: ({x1}, {y1}, {width}, {height})")

    # mss로 캡처
    with mss.mss() as sct:
        monitor = {
            "left": int(x1),
            "top": int(y1),
            "width": int(width),
            "height": int(height)
        }
        img = np.array(sct.grab(monitor))[:, :, :3]  # BGR
        cv2.imwrite(save_path, img)
        print(f"[INFO] 미니맵 저장 완료 → {save_path}")

def find_me_in_minimap():
    global current_me_position  # 전역 변수 사용

    # 미니맵 영역 정의
    monitor = {
        "top": MINIMAP_TOP_LEFT[1],
        "left": MINIMAP_TOP_LEFT[0],
        "width": MINIMAP_BOTTOM_RIGHT[0] - MINIMAP_TOP_LEFT[0],
        "height": MINIMAP_BOTTOM_RIGHT[1] - MINIMAP_TOP_LEFT[1]
    }

    me_img = cv2.imread(ME_IMAGE_PATH)
    if me_img is None:
        print("[ERROR] me.png 파일을 찾을 수 없습니다.")
        current_me_position = None
        return None

    with mss.mss() as sct:
        screen = np.array(sct.grab(monitor))[:, :, :3]

    result = cv2.matchTemplate(screen, me_img, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= ME_CONFIDENCE:
        center_x = max_loc[0] + me_img.shape[1] // 2 + MINIMAP_TOP_LEFT[0]
        center_y = max_loc[1] + me_img.shape[0] // 2 + MINIMAP_TOP_LEFT[1]
        current_me_position = (center_x, center_y)  # 전역 변수에 저장
        print(f"[INFO] 미니맵에서 내 위치 발견: {current_me_position}, 정확도: {max_val:.2f}")
        return current_me_position
    else:
        print("[INFO] 미니맵에서 내 위치를 찾을 수 없습니다.")
        current_me_position = None
        return None
# 사용 예시
def update_me_position_loop():
    while True:
        find_me_in_minimap()
        time.sleep(1)  # 1초마다 갱신

# 시작 시


# 예시 실행



HP_BAR_IMAGE = "pngs/hp_bar_empty.png"
MP_BAR_IMAGE = "pngs/mp_bar_empty.png"
POTION_HOTKEY_HP = 'd'   # HP 물약 단축키
POTION_HOTKEY_MP = 'h'   # MP 물약 단축키
POTION_CHECK_INTERVAL = 1.5  # 몇 초마다 체크할지

def check_and_use_potion():
    with mss.mss() as sct:
        screen = np.array(sct.grab({
            "top": SCREEN_Y_START, "left": SCREEN_X_START,
            "width": SCREEN_X_END, "height": SCREEN_Y_END
        }))[:, :, :3]

    # HP 체크
    hp_img = cv2.imread(HP_BAR_IMAGE)
    if hp_img is not None:
        res = cv2.matchTemplate(screen, hp_img, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val > 0.8:
            pyautogui.press(POTION_HOTKEY_HP)
            print("[INFO] HP 낮음 → 물약 사용")

    # MP 체크
    mp_img = cv2.imread(MP_BAR_IMAGE)
    if mp_img is not None:
        res = cv2.matchTemplate(screen, mp_img, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val > 0.8:
            pyautogui.press(POTION_HOTKEY_MP)
            print("[INFO] MP 낮음 → 물약 사용")

def potion_monitor_loop():
    while True:
        check_and_use_potion()
        time.sleep(POTION_CHECK_INTERVAL)


TEMPLATE_FOLDER = "windows_png/monsters/henesisu/"
CHAR_IMAGE_PATH = "windows_png/charactor.png"
CONFIDENCE = 0.7
ATTACK_RANGE = 220
SEARCH_INTERVAL = 0.8

def euclidean_distance(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def remove_duplicates(points, threshold=20):
    unique = []
    for p in points:
        if all(euclidean_distance(p, u) > threshold for u in unique):
            unique.append(p)
    return unique

def load_templates():
    templates = []
    for file in os.listdir(TEMPLATE_FOLDER):
        path = os.path.join(TEMPLATE_FOLDER, file)
        img = cv2.imread(path)
        if img is not None:
            templates.append(img)
            flipped = cv2.flip(img, 1)
            templates.append(flipped)
        else:
            print(f"[WARN] 이미지 로드 실패: {path}")
    return templates

def find_char_center():
    try:
        return pyautogui.locateCenterOnScreen(CHAR_IMAGE_PATH, confidence=0.6)
    except Exception:
        return None

def find_slimes(templates):
    with mss.mss() as sct:
        monitor = {"top": 0, "left": 0, "width": 1280, "height": 720}
        screen = np.array(sct.grab(monitor))[:, :, :3].copy()
        detections = []
        for template in templates:
            res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= CONFIDENCE)
            h, w = template.shape[:2]
            for pt in zip(*loc[::-1]):
                center = (pt[0] + w // 2, pt[1] + h // 2)
                detections.append(center)
        return remove_duplicates(detections)

def visualize(detections):
    with mss.mss() as sct:
        monitor = {"top": 0, "left": 0, "width": 1280, "height": 720}
        screen = np.array(sct.grab(monitor))[:, :, :3].copy()
    for (x, y) in detections:
        cv2.rectangle(screen, (x-25, y-25), (x+25, y+25), (0, 0, 255), 2)
    cv2.imwrite("debug_screen.png", screen)
    print("[INFO] debug_screen.png 저장됨")


def main():
    print("[INFO] 슬라임 자동 감지 시작")
    templates = load_templates()
    shift_down = left_down = right_down = False
    z_down = False
    current_direction = None
    last_search = 0
    targets = []

    try:
        while True:
            char_pos = find_char_center()

            # 주기적으로 슬라임 다시 찾기
            if time.time() - last_search > SEARCH_INTERVAL:
                targets = find_slimes(templates)
                last_search = time.time()
                if targets:
                    visualize(targets)

            if not char_pos or not targets:
                print("[INFO] 캐릭터 또는 슬라임 없음")

                # 공격 키가 눌려 있다면 해제
                if shift_down:
                    pyautogui.keyUp('shift')
                    shift_down = False
                    print("[INFO] 공격 키 (shift) 해제")
                time.sleep(0.2)
                continue

                # 이동 방향 랜덤 선택
                # direction = random.choice(['left', 'right'])
                # duration = random.uniform(0.5, 1.2)  # 0.5~1.2초 정도 이동

                # # 이동 실행
                # print(f"[INFO] 랜덤 이동 시작 → 방향: {direction}, {duration:.2f}초 이동")

            # 가장 가까운 슬라임 찾기
            distances = [euclidean_distance(char_pos, t) for t in targets]
            closest = targets[np.argmin(distances)]
            dist = min(distances)
            dx = closest[0] - char_pos[0]
            direction = 'right' if dx > 0 else 'left'

            print(f"[INFO] 거리 {dist:.1f}, 방향 {direction}")

            if dist <= ATTACK_RANGE:
                # 슬라임이 공격 사거리 안에 있음
                if direction == current_direction:
                    if z_down:
                        pyautogui.keyUp('z')
                        z_down = False
                        print("[INFO] 이동 키 (z) 해제")
                    if not shift_down:
                        pyautogui.keyDown('shift')
                        shift_down = True
                        print("[INFO] 공격 시작 (shift ↓)")
                else:
                    # 방향만 안 맞았던 것이므로 방향 업데이트하고 바로 공격
                    current_direction = direction
                    print(f"[INFO] 방향 재조정: {direction} → current_direction 업데이트")
                    # 여기선 굳이 이동하지 않고 방향만 기억하게 설정
            else:
                # 공격 사거리 밖 → 이동만 수행
                if shift_down:
                    pyautogui.keyUp('shift')
                    shift_down = False
                    print("[INFO] 공격 중단 (shift ↑)")

                if direction == 'left':
                    if not left_down:
                        pyautogui.keyDown('left')
                        left_down = True
                        current_direction = 'left'
                        print("[INFO] ← 이동 시작")
                    if right_down:
                        pyautogui.keyUp('right')
                        right_down = False
                else:
                    if not right_down:
                        pyautogui.keyDown('right')
                        right_down = True
                        current_direction = 'right'
                        print("[INFO] → 이동 시작")
                    if left_down:
                        pyautogui.keyUp('left')
                        left_down = False

                if not z_down:
                    pyautogui.keyDown('z')
                    z_down = True
                    print("[INFO] 이동 키 (z) 누름")

            time.sleep(0.2)

    except KeyboardInterrupt:
        print("\n[INFO] 수동 종료됨 (Ctrl+C)")
    finally:
        for k in ['shift', 'left', 'right', 'z']:
            pyautogui.keyUp(k)
if __name__ == "__main__":
    if platform.system() == "Darwin":  # macOS
        resize_mac_window(TARGET_TITLE, 0, 0, SCREEN_X_END, SCREEN_Y_END)
    elif platform.system() == "Windows":
        resize_window_windows(TARGET_TITLE, 0, 0, SCREEN_X_END, SCREEN_Y_END)
    capture_minimap()
    # find_me_in_minimap()
    threading.Thread(target=update_me_position_loop, daemon=True).start()
    threading.Thread(target=potion_monitor_loop, daemon=True).start()
    main()

    # try:
    #     while True:
    #         time.sleep(.5)
    # except KeyboardInterrupt:
    #     print("\n[INFO] 수동 종료됨 (Ctrl+C)")
    main()

    
    # 45, 206)