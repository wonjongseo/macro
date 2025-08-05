import json
from dataclasses import dataclass
from typing import Optional

@dataclass
class AppConfig:
    END_X: int = 970
    END_Y: int = 700
    HP_thr: int = 55
    MP_thr: int = 55
    mode_folder: bool = True
    template_folder: Optional[str] = None
    hp_img: Optional[str] = None
    mp_img: Optional[str] = None
    mm_tl: Optional[str] = None
    mm_br: Optional[str] = None
    mm_self: Optional[str] = None
    mm_others: Optional[str] = None
    death_warn: Optional[str] = None
    attack_range: int = 100  # PlayConfigEditor에서 쓰는 값

    @classmethod
    def load_from_file(cls, path: str) -> "AppConfig":
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)

    def save_to_file(self, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=2)
