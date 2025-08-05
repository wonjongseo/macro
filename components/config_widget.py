import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QLabel, QFileDialog, QMessageBox, QComboBox, QSpinBox, QFormLayout,
    QLineEdit, QRadioButton
)
from PyQt5.QtCore import Qt

from components.app_config import AppConfig

class RouteEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Route Patrol Editor')
        self.resize(500, 400)
        self.layout = QVBoxLayout()
        self.route_list = []
        form_layout = QFormLayout()

        self.action_combo = QComboBox()
        self.action_combo.addItems(['move', 'jump', 'ladder'])
        form_layout.addRow('액션 선택:', self.action_combo)

        self.start_x_spin = QSpinBox(); self.start_x_spin.setRange(0, 2000)
        form_layout.addRow('시작 X:', self.start_x_spin)
        self.start_y_spin = QSpinBox(); self.start_y_spin.setRange(0, 2000)
        form_layout.addRow('시작 Y:', self.start_y_spin)

        self.end_y_spin = QSpinBox(); self.end_y_spin.setRange(0, 2000)
        form_layout.addRow('끝 Y:', self.end_y_spin); self.end_y_spin.hide()

        self.jump_count_spin = QSpinBox(); self.jump_count_spin.setRange(1, 10)
        form_layout.addRow('점프 횟수:', self.jump_count_spin); self.jump_count_spin.hide()

        self.action_combo.currentTextChanged.connect(self.toggle_fields)
        self.layout.addLayout(form_layout)

        self.add_btn = QPushButton('루틴 추가하기')
        self.add_btn.clicked.connect(self.add_routine)
        self.layout.addWidget(self.add_btn)

        self.route_display = QListWidget()
        self.route_display.setDragDropMode(QListWidget.InternalMove)
        self.layout.addWidget(self.route_display)

        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton('루틴 저장')
        self.save_btn.clicked.connect(self.save_route)
        btn_layout.addWidget(self.save_btn)
        self.load_btn = QPushButton('루틴 불러오기')
        self.load_btn.clicked.connect(self.load_route)
        btn_layout.addWidget(self.load_btn)
        self.layout.addLayout(btn_layout)

        self.setLayout(self.layout)

    def toggle_fields(self, action):
        # self.end_x_spin.setVisible(action=='ladder')
        self.end_y_spin.setVisible(action=='ladder')
        self.jump_count_spin.setVisible(action=='jump')

    def add_routine(self):
        action = self.action_combo.currentText()
        routine = {'action':action,'x':self.start_x_spin.value(),'y':self.start_y_spin.value()}
        text = f'[{action.upper()}] 시작:({routine["x"]},{routine["y"]})'
        if action=='ladder':
            # routine['end_x']=self.end_x_spin.value(); 
            routine['end_y']=self.end_y_spin.value()
            text+=f' → 끝:({routine["end_x"]},{routine["end_y"]})'
        if action=='jump':
            routine['jump_count']=self.jump_count_spin.value()
            text+=f', 횟수:{routine["jump_count"]}'
        self.route_list.append(routine)
        self.route_display.addItem(text)

    def save_route(self):
        path, _=QFileDialog.getSaveFileName(self,'루틴 저장','','.json')
        if path:
            order=[]
            for i in range(self.route_display.count()):
                idx=self.route_display.row(self.route_display.item(i))
                order.append(self.route_list[idx])
            with open(path,'w',encoding='utf-8') as f: json.dump(order,f,ensure_ascii=False,indent=2)

    def load_route(self):
        path,_=QFileDialog.getOpenFileName(
            self, 
            'Config 불러오기', 
            '', 
            'JSON Files (*.json);;All Files (*)'
        )
        if path:
            with open(path,'r',encoding='utf-8') as f: self.route_list=json.load(f)
            self.route_display.clear()
            for r in self.route_list:
                text=f'[{r["action"].upper()}] 시작:({r["x"]},{r["y"]})'
                if r['action']=='ladder': text+=f' → 끝:({r["end_x"]},{r["end_y"]})'
                if r['action']=='jump': text+=f', 횟수:{r["jump_count"]}'
                self.route_display.addItem(text)


class ConfigEditor(QWidget):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Config Editor'); self.resize(400, 500)
        self.config = AppConfig()
        layout=QFormLayout()
        # 1. END_X, END_Y
        self.endx=QSpinBox();self.endx.setRange(0,2000);layout.addRow('END_X:',self.endx)
        self.endy=QSpinBox();self.endy.setRange(0,2000);layout.addRow('END_Y:',self.endy)
        
        self.hp_thr=QSpinBox();self.hp_thr.setRange(0,100);layout.addRow('HP% 임계:',self.hp_thr)
        self.mp_thr=QSpinBox();self.mp_thr.setRange(0,100);layout.addRow('MP% 임계:',self.mp_thr)

        self.endx.setValue(970) ; self.endy.setValue(700)
        self.hp_thr.setValue(55); self.mp_thr.setValue(55);

        # 3-8 image paths
        def make_path_field(label):
            le=QLineEdit(); btn=QPushButton('...')
            btn.clicked.connect(lambda: self.select_file(le))
            h=QHBoxLayout(); h.addWidget(le); h.addWidget(btn)
            layout.addRow(label,h)
            return le
        
        self.hp_img=make_path_field('HP 템플릿:')
        self.mp_img=make_path_field('MP 템플릿:')
        self.mm_tl=make_path_field('미니맵 TL:')
        self.mm_br=make_path_field('미니맵 BR:')
        self.mm_self=make_path_field('미니맵 본인:')
        self.mm_others=make_path_field('미니맵 타인:')
        self.death_warn=make_path_field('사망 경고:')
        # save/load
        btns=QHBoxLayout()
        s=QPushButton('저장'); s.clicked.connect(self.save); btns.addWidget(s)
        l=QPushButton('불러오기'); l.clicked.connect(self.load); btns.addWidget(l)
        layout.addRow(btns)
        self.setLayout(layout)

    def select_file(self, line_edit):
        p,_=QFileDialog.getOpenFileName(self,'파일 선택','','Images (*.png *.jpg)')
        if p: line_edit.setText(p)

    def save(self):
        cfg={
            'END_X':self.endx.value(),'END_Y':self.endy.value(),
            'HP_thr':self.hp_thr.value(),'MP_thr':self.mp_thr.value(),
            'hp_img':self.hp_img.text(),'mp_img':self.mp_img.text(),
            'mm_tl':self.mm_tl.text(),'mm_br':self.mm_br.text(),
            'mm_self':self.mm_self.text(),'mm_others':self.mm_others.text(),
            'death_warn':self.death_warn.text()
        }
        p,_=QFileDialog.getSaveFileName(self,'Config 저장','','.json')
        if p: open(p,'w',encoding='utf-8').write(json.dumps(cfg,ensure_ascii=False,indent=2))

    def load(self):
        p,_=QFileDialog.getOpenFileName(
            self, 
            'Config 불러오기', 
            '', 
            'JSON Files (*.json);;All Files (*)'
        )
        if p:
            cfg=json.load(open(p,'r',encoding='utf-8'))
            self.endx.setValue(cfg.get('END_X',0)); self.endy.setValue(cfg.get('END_Y',0))
            self.hp_thr.setValue(cfg.get('HP_thr',0)); self.mp_thr.setValue(cfg.get('MP_thr',0))
            self.hp_img.setText(cfg.get('hp_img','')); self.mp_img.setText(cfg.get('mp_img',''))
            self.mm_tl.setText(cfg.get('mm_tl','')); self.mm_br.setText(cfg.get('mm_br',''))
            self.mm_self.setText(cfg.get('mm_self','')); self.mm_others.setText(cfg.get('mm_others',''))
            self.death_warn.setText(cfg.get('death_warn',''))


class PlayConfigEditor(QWidget):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Play Config Editor'); self.resize(400,300)
        layout=QFormLayout()
        # 1. template folder
        self.tpl_folder=QLineEdit(); fbtn=QPushButton('...'); fbtn.clicked.connect(self.select_folder)
        h1=QHBoxLayout(); h1.addWidget(self.tpl_folder); h1.addWidget(fbtn)
        layout.addRow('몬스터 템플릿 폴더:',h1)
        # 2. attack range
        self.atk_range=QSpinBox(); self.atk_range.setRange(0,5000)
        layout.addRow('공격 최대 거리:',self.atk_range)
        # 3. open RouteEditor
        self.open_route_btn=QPushButton('Route Editor 열기')
        self.open_route_btn.clicked.connect(self.open_route)
        layout.addRow(self.open_route_btn)
        self.setLayout(layout)

    def select_folder(self):
        d=QFileDialog.getExistingDirectory(self,'폴더 선택')
        if d: self.tpl_folder.setText(d)

    def open_route(self):
        self.route_win=RouteEditor(); self.route_win.show()


if __name__ == '__main__':
    app=QApplication(sys.argv)
    tabs=QTabWidget()
    tabs.addTab(RouteEditor(), 'Route')
    tabs.addTab(ConfigEditor(), 'Config')
    tabs.addTab(PlayConfigEditor(), 'Play Config')
    tabs.setWindowTitle('Macro Configurator')
    tabs.resize(600,700)
    tabs.show()
    sys.exit(app.exec_())
