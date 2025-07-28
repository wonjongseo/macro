import pyautogui
import cv2
import numpy as np
import mss

def capture_minimap(top_left_img='pngs/minimap_topLeft.png',
                    bottom_right_img='pngs/minimap_bottomRight.png',
                    save_path='pngs/minimap_capture.png',
                    confidence=0.8):
    print("[INFO] 미니맵 영역 감지 시작...")

    top_left = pyautogui.locateOnScreen(top_left_img, confidence=confidence)
    if top_left is None:
        print("[ERROR] top-left 이미지 인식 실패")
        return None, None

    bottom_right = pyautogui.locateOnScreen(bottom_right_img, confidence=confidence)
    if bottom_right is None:
        print("[ERROR] bottom-right 이미지 인식 실패")
        return None, None

    x1, y1 = top_left.left, top_left.top
    x2 = bottom_right.left + bottom_right.width
    y2 = bottom_right.top + bottom_right.height
    width, height = x2 - x1, y2 - y1

    monitor = {"left": x1, "top": y1, "width": width, "height": height}

    with mss.mss() as sct:
        img = np.array(sct.grab(monitor))[:, :, :3]  # BGR
        cv2.imwrite(save_path, img)

    print(f"[INFO] 미니맵 저장 완료 → {save_path}")
    return (x1, y1), (x2, y2)