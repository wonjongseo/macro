import threading
from PyQt5.QtCore import QThread
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import  QApplication, QWidget, QPushButton, QVBoxLayout, QLabel
import sys, time
from PyQt5.QtCore import Qt, QTimer
from main import END_X, END_Y, GameWindowController, SlimeHunterBot
from PyQt5.QtCore import QThread, pyqtSignal   # pyqtSignal 추가
from PyQt5.QtGui import QImage 

class BotThread(QThread):
    frame_ready = pyqtSignal(QImage)           # ▶ 메인 스레드로 보낼 신호

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.bot.set_frame_emitter(self.frame_ready)  # ← emitter 등록

    def run(self):
        self.bot.run()

class HunterUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Slime Hunter Controller")
        self.bot = None
        self.thread = None
        # ----- 버튼 -----
        self.start_btn  = QPushButton("▶ Start")
        self.pause_btn  = QPushButton("Ⅱ Pause")
        self.stop_btn   = QPushButton("■ Stop")
        self.status     = QLabel("상태: 대기 중")

        self.start_btn.clicked.connect(self.start_bot)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.stop_btn.clicked.connect(self.stop_bot)

        layout = QVBoxLayout(self)
        for w in (self.start_btn, self.pause_btn, self.stop_btn, self.status):
            layout.addWidget(w)

        self.is_paused = False
       

        self.debug_label = QLabel("Debug View")
        self.debug_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        # self.debug_label.setFixedSize(240, 135)   # 필요하면 크기 조정
        layout.addWidget(self.debug_label)        # 버튼·상태 아래에 추가

         # ─── 항상 위에 표시 ───────────────────────────────
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        # ─── 레이아웃·위젯 구성 끝난 뒤 한 틱 늦게 위치 이동 ─
        QTimer.singleShot(0, self.move_to_top_right)



    def move_to_top_right(self):
        screen_rect = QApplication.primaryScreen().availableGeometry()
        win_rect    = self.frameGeometry()  # 창 전체 크기(프레임 포함)
        x = screen_rect.right() - win_rect.width()
        y = screen_rect.top()
        self.move(x, y)
    # ---------- 슬롯 ----------
    def start_bot(self):
        # 이미 실행 중이면 무시
        if self.thread and self.thread.isRunning():
            self.status.setText("이미 실행 중")
            return

        # --- 1) 게임 창 사이즈 조정 ---------------------------------
        GameWindowController("MapleStory Worlds", END_X, END_Y).resize()
        time.sleep(0.5)

        # --- 2) 봇 인스턴스 생성 ------------------------------------
        self.bot = SlimeHunterBot()

        # 필요하면 한 번만 미니맵 캡처
        # self.bot.minimap.capture_minimap()

        # --- 3) 보조 스레드들 ---------------------------------------
        threading.Thread(target=self.bot.minimap.update_position,
                         daemon=True).start()

        # 포션 관리자 켜려면 ↓ 주석 해제
        # PotionManagerPath = "windows_png"
        # threading.Thread(target=PotionManager(
        #         PotionManagerPath + "/hp_bar_empty.png",
        #         PotionManagerPath + "/mp_bar_empty.png"
        #     ).loop,
        #     daemon=True).start()

        # --- 4) 메인 루프 스레드 시작 -------------------------------
        self.thread = BotThread(self.bot)   # BotThread 는 self.bot.run() 호출
        # ▶ 디버그 프레임 수신 슬롯 연결
        self.thread.frame_ready.connect(self.update_debug_view)
        self.thread.finished.connect(
            lambda: self.status.setText("상태: 종료됨"))
        self.thread.start() 

        # --- 5) UI 표시 --------------------------------------------
        self.is_paused = False
        self.pause_btn.setText("Ⅱ Pause")
        self.status.setText("상태: 실행 중")

    def update_debug_view(self, img: QImage):
        """디버그 프레임을 width-50 으로 줄여서 표시"""
        target_w = img.width() - 50                # 원본보다 50px 작게
        # 새 height 는 종횡비 유지
        target_h = int(img.height() * (target_w / img.width()))

        pix = QPixmap.fromImage(img).scaled(
            target_w, target_h,
            Qt.KeepAspectRatio,        # 세로가 더 작으면 그대로 둠
            Qt.SmoothTransformation    # 보간 품질
        )
        self.debug_label.setPixmap(pix)
        self.debug_label.setFixedSize(pix.size())   # 라벨 크기도 맞춤
        QTimer.singleShot(0, self.move_to_top_right)

    def toggle_pause(self):
        if not (self.bot and self.thread and self.thread.isRunning()):
            return
        self.is_paused = not self.is_paused
        self.bot.pause(self.is_paused)
        self.pause_btn.setText("▶ Resume" if self.is_paused else "Ⅱ Pause")
        self.status.setText("상태: 일시정지" if self.is_paused else "상태: 실행 중")

    def stop_bot(self):
        if self.bot:
            self.bot.stop()
            self.status.setText("정지 명령 전송")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = HunterUI()
    ui.show()
    sys.exit(app.exec_())
