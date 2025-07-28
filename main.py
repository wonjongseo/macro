from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QTextEdit
from PyQt5.QtCore import QThread, pyqtSignal
import sys
import traceback

# --- 기존에 정의한 capture_minimap 불러오기 ---
from maple_core import capture_minimap  # 당신의 capture_minimap 함수가 있는 파일명으로 수정

class WorkerThread(QThread):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, task_function):
        super().__init__()
        self.task_function = task_function

    def run(self):
        try:
            self.task_function()
            self.log_signal.emit("[INFO] 작업 완료")
        except Exception as e:
            error_msg = f"[ERROR] {str(e)}\n{traceback.format_exc()}"
            self.error_signal.emit(error_msg)

class MapleGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MapleStory Auto GUI")
        self.setGeometry(200, 200, 400, 300)

        self.capture_button = QPushButton("🗺️ 미니맵 캡처", self)
        self.capture_button.clicked.connect(self.run_capture_minimap)

        self.log_output = QTextEdit(self)
        self.log_output.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(self.capture_button)
        layout.addWidget(self.log_output)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    def run_capture_minimap(self):
        self.log_output.append("[INFO] 미니맵 캡처 시작...")
        self.capture_thread = WorkerThread(capture_minimap)
        self.capture_thread.log_signal.connect(self.log_output.append)
        self.capture_thread.error_signal.connect(self.log_output.append)
        self.capture_thread.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MapleGUI()
    window.show()
    sys.exit(app.exec_())