
# ---------- 5. 지형 판단기 ----------
import pyautogui


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

   