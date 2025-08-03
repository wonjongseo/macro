# worker.py  ── 메인 파일 위(or 별도) 에 두세요
from multiprocessing import Process, Queue
import cv2, mss, numpy as np, time, os

class MinimapWorker(Process):
    """
    미니맵 영역을 계속 캡처해서 (cx,cy) 를 out_q 로 내보내는 전용 프로세스
    """
    def __init__(self, minimap_area, me_img_path, out_q, interval=0.20):
        super().__init__(daemon=True)
        self.area     = minimap_area                 # (left, top, width, height)
        self.me_img   = cv2.imread(me_img_path)
        self.out_q    = out_q
        self.interval = interval

    def run(self):
        left, top, w, h = self.area
        with mss.mss() as sct:
            monitor = {"left": left, "top": top, "width": w, "height": h}
            while True:
                frame = np.array(sct.grab(monitor))[:, :, :3]
                res   = cv2.matchTemplate(frame, self.me_img, cv2.TM_CCOEFF_NORMED)
                _, val, _, loc = cv2.minMaxLoc(res)

                if val >= 0.70:
                    cx = loc[0] + self.me_img.shape[1] // 2 + left
                    cy = loc[1] + self.me_img.shape[0] // 2 + top
                    self.out_q.put((cx, cy))
                else:
                    self.out_q.put(None)            # “지금은 못 찾음”

                time.sleep(self.interval)
