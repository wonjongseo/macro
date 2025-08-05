import sys
import threading
import time

from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QImage, QPixmap

from main import MinimapTracker  # 필요에 맞게 경로 조정하세요

class MainWindow(QMainWindow):
    # QImage 와 (x,y) 위치 정보를 메인 스레드로 안전하게 전달하기 위한 시그널
    minimap_updated = pyqtSignal(QImage)
    pos_updated      = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("매크로 미니맵 모니터")
        self.resize(250, 300)

        # --- UI 위젯 세팅 ---
        self.minimap_label = QLabel("미니맵 로딩 중...")
        self.minimap_label.setFixedSize(200, 200)
        self.minimap_label.setStyleSheet("border:1px solid #666;")

        self.pos_label = QLabel("내 위치: ?")
        self.pos_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.minimap_label)
        layout.addWidget(self.pos_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # --- 시그널 ↔ 슬롯 연결 ---
        self.minimap_updated.connect(self.on_minimap_update)
        self.pos_updated.connect(self.on_pos_update)

#         # --- 트래커 생성 & 스레드 시작 ---
#        top_left_img=
# bottom_right_img=
# me_img=
        self.tracker = MinimapTracker(
            "windows_png" + "/minimap_topLeft.png",
            "windows_png" + "/minimap_bottomRight.png",
            "windows_png" + "/me.png",
             minimap_emitter=self.minimap_updated.emit,
            pos_emitter=self.pos_updated.emit
        )
        threading.Thread(target=self._capture_loop,     daemon=True).start()
        threading.Thread(target=self.tracker.update_position, daemon=True).start()

    def _capture_loop(self):
        """1초마다 미니맵 캡처를 호출해서 화면에 뿌려 줍니다."""
        while True:
            self.tracker.capture_minimap()
            time.sleep(1)

    def on_minimap_update(self, qimg: QImage):
        """minimap_updated 시그널이 emit 될 때 실행"""
        pix = QPixmap.fromImage(qimg)
        self.minimap_label.setPixmap(
            pix.scaled(
                self.minimap_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

    def on_pos_update(self, pos):
        """pos_updated 시그널이 emit 될 때 실행"""
        if pos:
            self.pos_label.setText(f"내 위치: {pos[0]}, {pos[1]}")
        else:
            self.pos_label.setText("내 위치: 미검출")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
