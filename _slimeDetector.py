import math
import os
import cv2
import mss
import numpy as np



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
