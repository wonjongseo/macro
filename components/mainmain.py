# main.py


import os, sys

# 이 파일(components/mainmain.py) 기준으로 한 단계 상위 디렉토리를 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config

import threading
import time
import json
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QFileDialog, QComboBox, QSpinBox, QFormLayout,
    QLineEdit, QRadioButton, QButtonGroup, QLabel
)
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from app_config import AppConfig
from main import GameWindowController, MinimapTracker


class RouteEditor(QWidget):
    minimap_updated = pyqtSignal(QImage)
    pos_updated      = pyqtSignal(object)

    def connect_minimap(self):
        """미니맵 스레드 실행 및 시그널 연결"""
        # 시그널 연결
        self.minimap_updated.connect(self.on_minimap_update)
        self.pos_updated.connect(self.on_pos_update)

        # 윈도우 리사이즈
        GameWindowController("MapleStory Worlds", Config.END_X, Config.END_Y).resize()
        time.sleep(0.5)

        # 트래커 생성
        self.tracker = MinimapTracker(
            "windows_png/minimap_topLeft.png",
            "windows_png/minimap_bottomRight.png",
            "windows_png/me.png",
            minimap_emitter=self.minimap_updated.emit,
            pos_emitter=self.pos_updated.emit
        )

        # 스레드 제어 플래그 켜기
        self._running = True

        # 스레드 시작
        threading.Thread(target=self._capture_loop, daemon=True).start()
        threading.Thread(target=self._pos_loop, daemon=True).start()

    def disconnect_minimap(self):
        """미니맵 스레드 정지"""
        # 스레드가 보는 플래그 내리기
        self._running = False

        # 시그널 연결 해제
        self.minimap_updated.disconnect(self.on_minimap_update)
        self.pos_updated.disconnect(self.on_pos_update)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Route Patrol Editor')
        self.resize(500, 400)

        self.route_list = []
        layout = QVBoxLayout()
        form = QFormLayout()

        # 미니맵 표시 여부 플래그
        self.is_show_minimap = False
        # 캡처 루프 제어 플래그
        self._running = False

        self.current_position= (0, 0)

        self.toggle_show_minimap_btn = QPushButton("미니맵 열기")
        self.toggle_show_minimap_btn.clicked.connect(self.toggle_show_minimap)
        layout.addWidget(self.toggle_show_minimap_btn)

        self.minimap_label = QLabel("미니맵 로딩중...")
        self.minimap_label.setFixedSize(300,300)
        self.minimap_label.setAlignment(Qt.AlignCenter)
        self.minimap_label.hide()
        
        self.pos_label = QLabel("내 위치: (x, y)")
        self.pos_label.setAlignment(Qt.AlignCenter)
        self.pos_label.hide()      

        # layout.addWidget(self.minimap_label)
        # layout.addWidget(self.pos_label)
        self.minimap_row = QHBoxLayout()
# 2. 각 레이블을 HBox에 추가
        self.minimap_row.addWidget(self.minimap_label)
        self.minimap_row.addWidget(self.pos_label)
        # 3. 메인 레이아웃에 이 HBox를 추가
        layout.addLayout(self.minimap_row)

        
        # action
        self.action_combo = QComboBox()
        self.action_combo.addItems(['move', 'jump', 'ladder'])
        form.addRow('액션:', self.action_combo)

        # start x,y
        self.start_x = QSpinBox(); self.start_x.setRange(0, 2000)    
        self.start_x_layout = QHBoxLayout()
        self.copy_x_button = QPushButton("내 좌표 x 복사")
        self.copy_x_button.clicked.connect(lambda: self.on_click_copy_xy(True))

        self.start_x_layout.addWidget(self.start_x)
        self.start_x_layout.addWidget(self.copy_x_button)

        self.start_y = QSpinBox(); self.start_y.setRange(0, 2000)
        self.start_y_layout = QHBoxLayout()
        self.copy_y_button = QPushButton("내 좌표 y 복사")
        self.copy_y_button.clicked.connect(lambda: self.on_click_copy_xy(False))

        self.start_y_layout.addWidget(self.start_y)
        self.start_y_layout.addWidget(self.copy_y_button)

        form.addRow('시작 X:', self.start_x_layout)
        form.addRow('시작 Y:', self.start_y_layout)

        # ladder end y
        self.end_y = QSpinBox(); self.end_y.setRange(0, 2000)
        form.addRow('끝 Y:', self.end_y)
        self.end_y.hide()

        # jump count
        self.jump_count = QSpinBox(); self.jump_count.setRange(1, 10)
        form.addRow('점프 횟수:', self.jump_count)
        self.jump_count.hide()

        self.action_combo.currentTextChanged.connect(self._toggle_fields)

        layout.addLayout(form)

        btn_add = QPushButton('루틴 추가')
        btn_add.clicked.connect(self._add)
        layout.addWidget(btn_add)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.InternalMove)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        btn_save = QPushButton('저장')
        btn_save.clicked.connect(self._save)
        btn_load = QPushButton('불러오기')
        btn_load.clicked.connect(self._load)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_load)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def on_click_copy_xy(self, isX) :
        if self.current_position is None:
            print("self.current_position is NONE")
        (x,y) =  self.current_position
        if isX: 
            self.start_x.setValue(x)
        else:
            self.start_y.setValue(y)
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

    def _capture_loop(self):
        """반복적으로 캡처만 수행"""
        while self._running:
            self.tracker.capturing_minimap()
            time.sleep(0.5)

    def _pos_loop(self):
        """반복적으로 위치 업데이트만 수행"""
        while self._running:
            self.tracker.update_position()
            time.sleep(0.5)
    def on_pos_update(self, pos):
        """pos_updated 시그널이 emit 될 때 실행"""
        if pos: 
            self.current_position = pos         
            self.pos_label.setText(f"내 위치: {pos[0], pos[1]}")
        else:
            self.pos_label.setText("내 위치: (?, ?)")

    def toggle_show_minimap(self):
        if not self.is_show_minimap:
            # 켜기
            self.is_show_minimap = True
            self.toggle_show_minimap_btn.setText("미니맵 닫기")
            self.minimap_label.show()
            self.pos_label.show()
            self.connect_minimap()
        else:
            # 끄기
            self.is_show_minimap = False
            self.toggle_show_minimap_btn.setText("미니맵 열기")
            self.disconnect_minimap()
            self.minimap_label.hide()
            self.pos_label.hide()
    
    
    def _toggle_fields(self, action):
        self.end_y.setVisible(action == 'ladder')
        self.jump_count.setVisible(action == 'jump')

    def _add(self):
        act = self.action_combo.currentText()
        entry = {'action': act, 'x': self.start_x.value(), 'y': self.start_y.value()}
        text = f'[{act.upper()}] ({entry["x"]},{entry["y"]})'
        if act == 'ladder':
            entry['end_y'] = self.end_y.value()
            text += f' → 끝 Y:{entry["end_y"]}'
        elif act == 'jump':
            entry['jump_count'] = self.jump_count.value()
            text += f', 횟수:{entry["jump_count"]}'
        self.route_list.append(entry)
        self.list_widget.addItem(text)

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, '루틴 저장', '', 'JSON Files (*.json);;All Files (*)'
        )
        if not path:
            return
        # 드래그 순서 반영
        ordered = []
        for i in range(self.list_widget.count()):
            idx = self.list_widget.row(self.list_widget.item(i))
            ordered.append(self.route_list[idx])
        with open(path, 'w', encoding='utf-8') as f:
            import json; json.dump(ordered, f, ensure_ascii=False, indent=2)

    def _load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '루틴 불러오기', '', 'JSON Files (*.json);;All Files (*)'
        )
        if not path:
            return
        import json
        with open(path, 'r', encoding='utf-8') as f:
            self.route_list = json.load(f)
        self.list_widget.clear()
        for r in self.route_list:
            text = f'[{r["action"].upper()}] ({r["x"]},{r["y"]})'
            if r['action'] == 'ladder':
                text += f' → 끝 Y:{r["end_y"]}'
            if r['action'] == 'jump':
                text += f', 횟수:{r["jump_count"]}'
            self.list_widget.addItem(text)


class ConfigEditor(QWidget):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.setWindowTitle('Config Editor')
        self.resize(400, 500)
        self.config = config

        # 라디오 버튼: 폴더 모드 / 개별 모드
        self.radio_folder = QRadioButton("폴더 지정")
        self.radio_indiv  = QRadioButton("개별 지정")
        self.radio_folder.setChecked(self.config.mode_folder)
        self.radio_indiv.setChecked(not self.config.mode_folder)
        rg = QButtonGroup(self)
        rg.addButton(self.radio_folder)
        rg.addButton(self.radio_indiv)

        layout = QFormLayout()
        layout.addRow(self.radio_folder, self.radio_indiv)

        # 공통 필드
        self.endx = QSpinBox(); self.endx.setRange(0,2000)
        self.endy = QSpinBox(); self.endy.setRange(0,2000)
        self.hp_thr = QSpinBox(); self.hp_thr.setRange(0,100)
        self.mp_thr = QSpinBox(); self.mp_thr.setRange(0,100)
        layout.addRow('END_X:', self.endx)
        layout.addRow('END_Y:', self.endy)
        layout.addRow('HP% 임계:', self.hp_thr)
        layout.addRow('MP% 임계:', self.mp_thr)

        # 폴더 모드: 폴더 선택
        self.folder_field = QLineEdit()
        btn_f = QPushButton("...")
        btn_f.clicked.connect(self._pick_folder)
        h_f = QHBoxLayout(); h_f.addWidget(self.folder_field); h_f.addWidget(btn_f)
        layout.addRow('템플릿 폴더:', h_f)

        # 개별 모드: 파일별 선택
        def make_file_row(label):
            le = QLineEdit()
            btn = QPushButton("...")
            btn.clicked.connect(lambda _, l=le: self._pick_file(l))
            h = QHBoxLayout(); h.addWidget(le); h.addWidget(btn)
            layout.addRow(label, h)
            return le

        self.hp_img    = make_file_row('HP 템플릿:')
        self.mp_img    = make_file_row('MP 템플릿:')
        self.mm_tl     = make_file_row('미니맵 TL:')
        self.mm_br     = make_file_row('미니맵 BR:')
        self.mm_self   = make_file_row('미니맵 본인:')
        self.mm_others = make_file_row('미니맵 타인:')
        self.death_warn= make_file_row('사망 경고:')

        btns = QHBoxLayout()
        b_save = QPushButton('저장'); b_save.clicked.connect(self._save)
        b_load = QPushButton('불러오기'); b_load.clicked.connect(self._load)
        btns.addWidget(b_save); btns.addWidget(b_load)
        layout.addRow(btns)

        self.setLayout(layout)

        # 초기값 로드 및 모드 토글
        self._apply_to_ui()
        self.radio_folder.toggled.connect(self._toggle_mode)
        self._toggle_mode()

    def _toggle_mode(self):
        folder_mode = self.radio_folder.isChecked()
        # 폴더 란만 보이고, 나머지는 숨김
        self.folder_field.parentWidget().setVisible(folder_mode)
        for w in (self.hp_img, self.mp_img, self.mm_tl,
                  self.mm_br, self.mm_self, self.mm_others,
                  self.death_warn):
            w.parentWidget().setVisible(not folder_mode)

    def _apply_to_ui(self):
        c = self.config
        self.endx.setValue(c.END_X)
        self.endy.setValue(c.END_Y)
        self.hp_thr.setValue(c.HP_thr)
        self.mp_thr.setValue(c.MP_thr)
        self.folder_field.setText(c.template_folder or "")
        self.hp_img.setText(c.hp_img or "")
        self.mp_img.setText(c.mp_img or "")
        self.mm_tl.setText(c.mm_tl or "")
        self.mm_br.setText(c.mm_br or "")
        self.mm_self.setText(c.mm_self or "")
        self.mm_others.setText(c.mm_others or "")
        self.death_warn.setText(c.death_warn or "")

    def _update_from_ui(self):
        c = self.config
        c.END_X = self.endx.value()
        c.END_Y = self.endy.value()
        c.HP_thr = self.hp_thr.value()
        c.MP_thr = self.mp_thr.value()
        c.mode_folder = self.radio_folder.isChecked()
        c.template_folder = self.folder_field.text()
        c.hp_img     = self.hp_img.text()
        c.mp_img     = self.mp_img.text()
        c.mm_tl      = self.mm_tl.text()
        c.mm_br      = self.mm_br.text()
        c.mm_self    = self.mm_self.text()
        c.mm_others  = self.mm_others.text()
        c.death_warn = self.death_warn.text()

    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, '폴더 선택')
        if d: self.folder_field.setText(d)

    def _pick_file(self, line_edit: QLineEdit):
        p, _ = QFileDialog.getOpenFileName(self, '파일 선택', '', 'Images (*.png *.jpg)')
        if p: line_edit.setText(p)

    def _save(self):
        self._update_from_ui()
        path, _ = QFileDialog.getSaveFileName(
            self, 'Config 저장', '', 'JSON Files (*.json);;All Files (*)'
        )
        if path:
            self.config.save_to_file(path)

    def _load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Config 불러오기', '', 'JSON Files (*.json);;All Files (*)'
        )
        if not path:
            return
        self.config = AppConfig.load_from_file(path)
        self._apply_to_ui()
        self._toggle_mode()

class PlayConfigEditor(QWidget):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.setWindowTitle('Play Config Editor')
        self.resize(400, 400)
        self.config = config

        layout = QFormLayout()

        # 1. 몬스터 템플릿 폴더
        self.tpl_folder = QLineEdit()
        btn_folder = QPushButton("...")
        btn_folder.clicked.connect(self._pick_folder)
        h_folder = QHBoxLayout(); h_folder.addWidget(self.tpl_folder); h_folder.addWidget(btn_folder)
        layout.addRow('몬스터 템플릿 폴더:', h_folder)

        # 2. 공격 최대 거리
        self.atk_range = QSpinBox(); self.atk_range.setRange(0, 5000)
        layout.addRow('공격 최대 거리:', self.atk_range)

        # 3. 루틴 JSON 불러오기
        self.btn_load_route = QPushButton('루틴 불러오기')
        self.btn_load_route.clicked.connect(self._load_route)
        layout.addRow(self.btn_load_route)

        # 불러온 루틴을 보여줄 리스트
        self.route_list_widget = QListWidget()
        layout.addRow(self.route_list_widget)

        self.setLayout(layout)

        # 초기값 세팅
        self.tpl_folder.setText(self.config.template_folder or "")
        self.atk_range.setValue(getattr(self.config, 'attack_range', 100))

    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, '폴더 선택')
        if d:
            self.tpl_folder.setText(d)
            self.config.template_folder = d

    def _load_route(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '루틴 파일 열기', '', 'JSON Files (*.json);;All Files (*)'
        )
        if not path:
            return

        with open(path, 'r', encoding='utf-8') as f:
            routes = json.load(f)

        self.route_list_widget.clear()
        for r in routes:
            text = f'[{r["action"].upper()}] ({r["x"]},{r["y"]})'
            if r['action'] == 'ladder':
                text += f' → 끝 Y:{r.get("end_y", "")}'
            if r['action'] == 'jump':
                text += f', 횟수:{r.get("jump_count", "")}'
            self.route_list_widget.addItem(text)

class MacroMonitor(QWidget):
    """AppConfig 값을 실시간으로 보여주는 탭"""
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.setWindowTitle('매크로 모니터')
        self.resize(400, 400)

        self.layout = QVBoxLayout()
        self.labels = {}
        self._build_ui()
        self.setLayout(self.layout)

        # 1초마다 갱신
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_labels)
        self.timer.start(1000)

    def _build_ui(self):
        form = QFormLayout()
        for field in vars(self.config):
            lbl = QLabel()
            form.addRow(field + ":", lbl)
            self.labels[field] = lbl
        self.layout.addLayout(form)

    def _update_labels(self):
        for key, lbl in self.labels.items():
            val = getattr(self.config, key)
            lbl.setText(str(val))


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # 기본 설정 로드
    try:
        cfg = AppConfig.load_from_file('default_config.json')
    except Exception:
        cfg = AppConfig()

    tabs = QTabWidget()
    tabs.addTab(RouteEditor(), 'Route')
    tabs.addTab(ConfigEditor(cfg), 'Config')
    tabs.addTab(PlayConfigEditor(cfg), 'Play Config')
    tabs.addTab(MacroMonitor(cfg), '매크로')

    tabs.setWindowTitle('Macro Configurator')
    tabs.resize(600, 700)
    tabs.show()

    sys.exit(app.exec_())