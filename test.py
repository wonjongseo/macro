# import pyautogui

# while True:
#     pyautogui.press("alt")

    
# import cv2
# import mss
# import numpy as np

# from main import END_X, END_Y


# def visualize( ):
#         with mss.mss() as sct:
#             monitor = {"top": int(0), "left": int(0), "width": int(END_X), "height": int(END_Y)}
#             screen = np.array(sct.grab(monitor))[:, :, :3].copy()

#         # 박스 그리기
       

#         cv2.imshow("SlimeHunter – Debug", screen)
#         # waitKey(1) : 1ms 동안 이벤트 처리 → 창 유지
#         if cv2.waitKey(1) & 0xFF == 27:     # ESC 누르면 숨김
#             cv2.destroyWindow("SlimeHunter – Debug")


# visualize() 

import os, cv2, pathlib

fname = "windows_png/hp_bar_empty.png"

print("① 현재 워킹 디렉터리  :", os.getcwd())
print("② 상대 경로 존재 여부 :", os.path.isfile(fname))
print("③ 절대 경로           :", pathlib.Path(fname).resolve())
print("④ cv2.imread 결과     :", cv2.imread(fname))