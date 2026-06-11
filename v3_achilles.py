"""
v3 Achilles — 全链路模块化视觉+音频创作引擎
================================================
arch: 剧情→镜头脚本→参数库→组件拼装→音画同步输出
all parameters are dead static codes, recombined per frame
"""

import json, time, math
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


# ═══════════════════════════════════════════
# PART 1: 数据类型定义
# ═══════════════════════════════════════════

@dataclass
class Vector3:
    x: float = 0.0; y: float = 0.0; z: float = 0.0

@dataclass
class RGB:
    r: int = 255; g: int = 255; b: int = 255
    def hex(self): return f"#{self.r:02x}{self.g:02x}{self.b:02x}"
    def tuple(self): return (self.r, self.g, self.b)


# ═══════════════════════════════════════════
# PART 0: 统一维度标尺 — 万物标值坐标系
# ═══════════════════════════════════════════

DIMENSIONAL_SCALES = {
    # ─── 光学标尺 ───
    "DS_BRIGHTNESS": {
        "name": "亮度", "unit": "0-10", "type": "linear",
        "marks": {0: "全黑/无光", 2: "暗/夜", 4: "昏暗/阴天", 5: "中灰/标准",
                   6: "明/晴天", 8: "亮/聚光", 10: "全白/过曝"},
        "default": 5.0, "link_to": ["SCENE_LIGHTING", "LIGHT_PHYSICS"]
    },
    "DS_CONTRAST": {
        "name": "对比度", "unit": "0-10", "type": "linear",
        "marks": {0: "平/无对比", 3: "低对比/柔和", 5: "标准", 7: "高对比/强烈", 10: "极对比/剪影"},
        "default": 5.0, "link_to": ["COLOR_GRADING", "SCENE_LIGHTING"]
    },
    "DS_WARMTH": {
        "name": "色温偏移", "unit": "-5到+5", "type": "linear",
        "marks": {-5: "极冷/冰蓝", -2: "冷/清", 0: "中性/标准白", 2: "微暖/黄", 5: "极暖/烛火"},
        "default": 0.0, "link_to": ["COLOR_GRADING", "COLOR_PALETTES", "SCENE_LIGHTING"]
    },
    "DS_SATURATION": {
        "name": "饱和度", "unit": "0-10", "type": "linear",
        "marks": {0: "完全去色/黑白", 3: "低饱和/淡", 5: "自然/标准", 8: "高饱和/浓郁", 10: "过饱和"},
        "default": 5.0, "link_to": ["COLOR_GRADING"]
    },
    "DS_SHARPNESS": {
        "name": "锐度", "unit": "0-10", "type": "linear",
        "marks": {0: "柔焦/全模糊", 3: "软/柔光", 5: "标准/自然", 8: "锐/清晰", 10: "过度锐化/锯齿"},
        "default": 5.0, "link_to": ["RENDER_VALIDATION"]
    },

    # ─── 运动标尺 ───
    "DS_SPEED": {
        "name": "速度倍率", "unit": "0.1x-10x", "type": "logarithmic",
        "marks": {0.1: "极慢/慢镜头", 0.5: "慢/舒缓", 1.0: "正常/实时", 2.0: "快/匆忙", 5.0: "极快/飞奔", 10.0: "瞬移/快进"},
        "default": 1.0, "link_to": ["CHARACTER_ACTIONS", "PACING_PRESETS", "CAMERA_MOVEMENT", "PARTICLE_SYSTEMS"]
    },
    "DS_INTENSITY": {
        "name": "强度", "unit": "0-10", "type": "linear",
        "marks": {0: "无/静止", 2: "微弱/轻", 4: "轻/温和", 5: "中/标准", 7: "强/激烈", 9: "极强/狂暴", 10: "满/极限"},
        "default": 5.0, "link_to": ["EMOTION_PROFILE", "CHARACTER_ACTIONS", "SFX_LIBRARY", "PARTICLE_SYSTEMS"]
    },

    # ─── 音频标尺 ───
    "DS_VOLUME": {
        "name": "音量", "unit": "dB", "type": "db",
        "marks": {-60: "静音", -40: "极轻/耳语", -20: "轻/背景", -12: "标准/对话", -6: "响/强调", 0: "满/爆音边缘"},
        "default": -12.0, "link_to": ["AMBIENT_SOUNDS", "SFX_LIBRARY", "VOICE_PRESETS", "MIXER_BAKER"]
    },
    "DS_PITCH": {
        "name": "音高偏移", "unit": "半音", "type": "linear",
        "marks": {-12: "极低/兽吼", -5: "低/深沉", 0: "基础/正常", 5: "高/尖", 12: "极高/尖叫"},
        "default": 0.0, "link_to": ["VOICE_PRESETS", "VOICE_EMOTION", "TTS_EMOTION_MAP"]
    },

    # ─── 空间标尺 ───
    "DS_AMPLITUDE": {
        "name": "振幅/幅度", "unit": "mm", "type": "linear",
        "marks": {0: "静止", 10: "微动/呼吸", 50: "小动作/手势", 200: "中动作/转身", 500: "大动作/跳跃", 2000: "极大/飞行"},
        "default": 0.0, "link_to": ["CHARACTER_ACTIONS", "CHARACTER_HAND", "EMOTION_PROFILE"]
    },
    "DS_DENSITY": {
        "name": "密度/粒子数", "unit": "%", "type": "linear",
        "marks": {0: "空/无", 10: "稀/微量", 30: "疏/少量", 50: "中/标准", 80: "密/大量", 100: "满/完全填充"},
        "default": 50.0, "link_to": ["PARTICLE_SYSTEMS", "SCENE_VEGETATION", "SCENE_WEATHER"]
    },
    "DS_DISTANCE": {
        "name": "距离/景深", "unit": "m", "type": "linear",
        "marks": {0.1: "微距/紧贴", 0.5: "近距/特写", 2.0: "中距/对话", 10: "远/全景", 100: "极远/大远景", 1000: "无限远/天际"},
        "default": 2.0, "link_to": ["CAMERA_PRESETS", "SHOT_SIZES", "SCENE_LIGHTING"]
    },

    # ─── 材质标尺 ───
    "DS_BLUR": {
        "name": "模糊/柔化", "unit": "px", "type": "linear",
        "marks": {0: "锐利/无模糊", 2: "微柔/胶片", 8: "轻模糊/软", 24: "中模糊/柔和散景", 50: "重模糊/梦幻", 100: "极模糊/抽象"},
        "default": 0.0, "link_to": ["LIGHT_PHYSICS", "COLOR_GRADING"]
    },
    "DS_TRANSPARENCY": {
        "name": "透明度", "unit": "%", "type": "linear",
        "marks": {0: "完全透明/不可见", 25: "半透/玻璃", 50: "半透明/雾", 80: "微透/薄纱", 100: "完全不透明/实体"},
        "default": 100.0, "link_to": ["PARTICLE_SYSTEMS", "SCENE_WATER", "CLOTHING_ACCESSORY"]
    },
    "DS_REFLECTIVITY": {
        "name": "反射率", "unit": "0.0-1.0", "type": "linear",
        "marks": {0.0: "全吸收/哑光", 0.1: "微反/粗糙", 0.3: "弱反/皮肤", 0.5: "半反/木", 0.8: "强反/水面", 1.0: "镜面全反射"},
        "default": 0.1, "link_to": ["COLLISION_MATERIALS", "CLOTHING_ACCESSORY", "SCENE_WATER"]
    },
    "DS_ROUGHNESS": {
        "name": "粗糙度", "unit": "0.0-1.0", "type": "linear",
        "marks": {0.0: "绝对光滑/镜面", 0.2: "光滑/抛光", 0.4: "标准/皮肤", 0.6: "粗糙/石头", 0.8: "粗/布料", 1.0: "极粗/沙石"},
        "default": 0.5, "link_to": ["COLLISION_MATERIALS", "SCENE_TERRAIN", "CLOTHING_UPPER"]
    },
    "DS_ELASTICITY": {
        "name": "弹性", "unit": "0.0-1.0", "type": "linear",
        "marks": {0.0: "完全刚体/不变形", 0.2: "微弹/骨", 0.4: "低弹/肌肉", 0.6: "中弹/橡胶", 0.8: "高弹/皮肤", 1.0: "完美弹性/弹球"},
        "default": 0.2, "link_to": ["COLLISION_MATERIALS", "CHARACTER_BODY", "CLOTH_SIM_PRESETS"]
    },

    # ─── 面部标尺 ───
    "DS_EXPRESSION_WEIGHT": {
        "name": "表情权重", "unit": "0.0-1.0", "type": "linear",
        "marks": {0.0: "无表情/中性", 0.25: "微表情/隐约", 0.5: "半表情/可见", 0.75: "明显表情", 1.0: "极限表情"},
        "default": 0.0, "link_to": ["FACS_UNITS", "EMOTION_PROFILE", "CHARACTER_EYELID"]
    },

    # ─── 环境标尺 ───
    "DS_TEMPERATURE": {
        "name": "环境温度", "unit": "°C", "type": "linear",
        "marks": {-30: "极寒/冻原", -5: "冷/雪", 15: "凉/秋", 25: "舒适/春", 35: "热/夏", 45: "极热/沙漠"},
        "default": 25.0, "link_to": ["SCENE_WEATHER", "PARTICLE_SYSTEMS"]
    },
    "DS_HUMIDITY": {
        "name": "湿度", "unit": "%", "type": "linear",
        "marks": {0: "极干/沙漠", 20: "干/室内", 40: "适中/春秋", 60: "微湿/沿海", 80: "湿/雨后", 100: "饱和/雾中"},
        "default": 40.0, "link_to": ["SCENE_WEATHER", "PARTICLE_SYSTEMS"]
    },

    # ─── 角度标尺 ───
    "DS_ANGLE_AZIMUTH": {
        "name": "水平方位角", "unit": "deg 0-360", "type": "circular",
        "marks": {0: "正前/12点", 45: "右前/1点半", 90: "正右/3点",
                   135: "右后/4点半", 180: "正后/6点", 225: "左后/7点半",
                   270: "正左/9点", 315: "左前/10点半", 360: "正前/回环"},
        "default": 0.0, "link_to": ["SCENE_LIGHTING", "CAMERA_PRESETS", "CHARACTER_ACTIONS"]
    },
    "DS_ANGLE_ELEVATION": {
        "name": "俯仰角", "unit": "deg -90到+90", "type": "linear",
        "marks": {-90: "正下/底光", -45: "低角度/仰拍", -15: "微仰/英雄视角",
                   0: "平视/眼高", 15: "微俯/俯视", 45: "高角度/俯拍",
                   75: "极高/鸟瞰", 90: "正上/顶光/上帝视角"},
        "default": 0.0, "link_to": ["SCENE_LIGHTING", "CAMERA_PRESETS", "CHARACTER_ACTIONS"]
    },
    "DS_ANGLE_ROLL": {
        "name": "旋转倾斜角", "unit": "deg -180到+180", "type": "circular",
        "marks": {-180: "完全倒转", -90: "左倾90", -15: "微左倾/不安",
                   0: "水平/稳定", 3: "微斜/荷兰角", 15: "明显倾斜/失衡",
                   90: "右倾90", 180: "完全翻转"},
        "default": 0.0, "link_to": ["CAMERA_PRESETS", "COMPOSITION_RULES", "CHARACTER_ACTIONS"]
    },
    "DS_ANGLE_FOV": {
        "name": "视场角", "unit": "deg 5-180", "type": "linear",
        "marks": {5: "超长焦/大特写", 20: "长焦/特写", 35: "标准近景",
                   50: "标准中景", 75: "广角/全景", 110: "超广角/大远景", 180: "鱼眼/全包围"},
        "default": 50.0, "link_to": ["CAMERA_PRESETS", "SHOT_SIZES"]
    },
    "DS_ANGLE_JOINT": {
        "name": "关节角度", "unit": "deg -180到+180", "type": "linear",
        "marks": {-180: "极限反向", -90: "反向弯曲", -45: "微反",
                   0: "自然伸直", 30: "微弯", 60: "半弯", 90: "直角弯曲",
                   120: "深度弯曲", 150: "极限折叠", 180: "完全闭合"},
        "default": 0.0, "link_to": ["FINGER_JOINT", "CHARACTER_ACTIONS", "CONSTRAINT_TYPES"]
    },
    "DS_ANGLE_LIGHT_SPREAD": {
        "name": "光束扩散角", "unit": "deg 1-180", "type": "linear",
        "marks": {1: "激光/极窄", 10: "聚光/手电", 30: "窄束/射灯",
                   60: "中束/台灯", 90: "宽束/泛光", 120: "广角/环境", 180: "全向/点光源"},
        "default": 60.0, "link_to": ["SCENE_LIGHTING"]
    },
}

# 标尺→离散码映射 (反向查询：给定一个数值，找到最接近的离散标签)
def scale_to_code(scale_name: str, value: float, code_dict: dict) -> str:
    """把标尺值映射到最近的离散参数码
    
    Example: scale_to_code('DS_BRIGHTNESS', 7.5, SCENE_LIGHTING) -> 'LB_04'
    """
    scale = DIMENSIONAL_SCALES.get(scale_name)
    if not scale:
        return None
    marks = sorted(scale["marks"].keys())
    # 找最近的刻度点
    nearest = min(marks, key=lambda m: abs(m - value))
    return scale["marks"][nearest]


# ═══════════════════════════════════════════
# PART 1: 数据类型定义 (continued)
# ═══════════════════════════════════════════


# ═══════════════════════════════════════════
# PART 2: 场景环境参数库
# ═══════════════════════════════════════════

class TerrainType(Enum):
    MOUNTAIN = "mountain"; HILL = "hill"; CLIFF = "cliff"; PLAIN = "plain"

class WaterType(Enum):
    RIVER = "river"; LAKE = "lake"; OCEAN = "ocean"; STREAM = "stream"; WATERFALL = "waterfall"

SCENE_TERRAIN = {
    "T_MTN_01": {"type": TerrainType.MOUNTAIN, "contour": "steep", "texture": "granite", "layers": 5, "size": 8},
    "T_MTN_02": {"type": TerrainType.MOUNTAIN, "contour": "gentle", "texture": "sandstone", "layers": 3, "size": 6},
    "T_MTN_03": {"type": TerrainType.CLIFF, "contour": "sheer", "texture": "limestone", "layers": 2, "size": 4},
    "T_HIL_01": {"type": TerrainType.HILL, "contour": "rolling", "texture": "grass_rock", "layers": 2, "size": 3},
    "T_PLN_01": {"type": TerrainType.PLAIN, "contour": "flat", "texture": "grass", "layers": 0, "size": 10},
}

SCENE_WATER = {
    "W_RIV_01": {"type": WaterType.RIVER, "area": 3, "depth": 2, "flow": "moderate", "ripple_size": "fine",
                 "ripple_speed": 0.8, "reflection": 0.6, "color": RGB(20,120,180)},
    "W_LAK_01": {"type": WaterType.LAKE, "area": 5, "depth": 4, "flow": "static", "ripple_size": "micro",
                 "ripple_speed": 0.2, "reflection": 0.9, "color": RGB(30,100,160)},
    "W_OCN_01": {"type": WaterType.OCEAN, "area": 10, "depth": 8, "flow": "dynamic", "ripple_size": "large",
                 "ripple_speed": 2.0, "reflection": 0.7, "color": RGB(10,80,140)},
    "W_STM_01": {"type": WaterType.STREAM, "area": 1, "depth": 1, "flow": "rapid", "ripple_size": "fine",
                 "ripple_speed": 1.5, "reflection": 0.5, "color": RGB(80,160,200)},
    "W_WFL_01": {"type": WaterType.WATERFALL, "area": 2, "depth": None, "flow": "falling", "ripple_size": "spray",
                 "ripple_speed": 3.0, "reflection": 0.8, "color": RGB(200,230,255)},
}

SCENE_WEATHER = {
    "WE_CLEAR": {"type": "clear", "cloud": 0, "rain": 0, "fog": 0, "snow": 0, "wind": 0},
    "WE_CLOUDY": {"type": "cloudy", "cloud": 0.6, "cloud_speed": 0.3, "rain": 0, "fog": 0, "snow": 0, "wind": 2},
    "WE_RAIN": {"type": "rain", "cloud": 0.9, "rain_density": 0.7, "rain_speed": 2.0, "rain_size": "medium",
                "fog": 0.3, "wind": 4, "snow": 0},
    "WE_STORM": {"type": "storm", "cloud": 1.0, "rain_density": 1.0, "rain_speed": 3.0, "rain_size": "large",
                 "fog": 0.5, "wind": 8, "lightning": True, "snow": 0},
    "WE_SNOW": {"type": "snow", "cloud": 0.8, "snow_density": 0.6, "snow_speed": 1.0, "snow_size": "fine",
                "fog": 0.4, "wind": 2, "rain": 0},
    "WE_FOG": {"type": "fog", "fog_density": 0.8, "fog_range": 50, "visibility": 0.2, "wind": 0, "rain": 0},
    "WE_TWILIGHT": {"type": "twilight", "cloud": 0.2, "sun_angle": 5, "ambient": "warm", "wind": 1},
    "WE_NIGHT": {"type": "night", "cloud": 0.1, "moon": True, "star_density": 0.8, "wind": 1},
}

SCENE_WIND = {
    "WIND_00": {"name": "无风", "strength": 0, "sway_angle": 0, "dust": 0, "sound_db": -99},
    "WIND_01": {"name": "微风", "strength": 1, "sway_angle": 3, "dust": 0, "sound_db": -30},
    "WIND_02": {"name": "和风", "strength": 2, "sway_angle": 8, "dust": 0, "sound_db": -20},
    "WIND_03": {"name": "大风", "strength": 3, "sway_angle": 20, "dust": 0.3, "sound_db": -10},
    "WIND_04": {"name": "狂风", "strength": 4, "sway_angle": 45, "dust": 0.8, "sound_db": 0},
}

SCENE_VEGETATION = {
    "V_TREE_OAK": {"type": "tree", "size": 8, "density": 0.7, "leaf_size": "large",
                   "sway_amp": 1.0, "color": RGB(30,120,40)},
    "V_TREE_PINE": {"type": "tree", "size": 7, "density": 0.9, "leaf_size": "needle",
                    "sway_amp": 0.5, "color": RGB(20,80,30)},
    "V_BUSH": {"type": "bush", "size": 2, "density": 0.8, "leaf_size": "small",
               "sway_amp": 1.5, "color": RGB(40,140,50)},
    "V_FLOWER": {"type": "flower", "size": 0.5, "density": 0.3, "petal_drop_speed": 0.5,
                 "color": RGB(255,100,150)},
    "V_GRASS": {"type": "grass", "size": 1, "density": 1.0, "sway_rhythm": 1.2,
                "color": RGB(60,180,60)},
}


# ═══════════════════════════════════════════
# PART 3: 光影&镜头运镜
# ═══════════════════════════════════════════

SCENE_LIGHTING = {
    # 光源类型
    "LT_SUN": {"type": "natural", "name": "日光", "temperature": 5500, "base_color": RGB(255,255,240)},
    "LT_MOON": {"type": "natural", "name": "月光", "temperature": 4100, "base_color": RGB(180,200,255)},
    "LT_FIRE": {"type": "artificial", "name": "火光", "temperature": 2000, "base_color": RGB(255,140,40)},
    "LT_LAMP": {"type": "artificial", "name": "灯光", "temperature": 3200, "base_color": RGB(255,240,200)},
    "LT_MAGIC": {"type": "special", "name": "特效光", "temperature": None, "base_color": RGB(100,200,255)},
    
    # 亮度
    "LB_00": {"name": "极暗", "brightness": 0.05, "contrast": 0.1},
    "LB_01": {"name": "偏暗", "brightness": 0.25, "contrast": 0.3},
    "LB_02": {"name": "正常", "brightness": 0.50, "contrast": 0.5},
    "LB_03": {"name": "明亮", "brightness": 0.75, "contrast": 0.7},
    "LB_04": {"name": "强光", "brightness": 1.00, "contrast": 0.9},
    
    # 动态
    "LD_STILL": {"name": "静止", "speed": 0, "flicker": 0, "transition_s": 0},
    "LD_PAN": {"name": "缓慢平移", "speed": 0.1, "transition_s": 10},
    "LD_FLICKER": {"name": "闪烁", "speed": 0, "flicker": 0.8, "flicker_hz": 3, "transition_s": 0.1},
    "LD_FADE": {"name": "渐变过渡", "speed": 0, "transition_s": 2.0},
}

CAMERA_PRESETS = {
    "CAM_XL": {"name": "远景", "fov": 90, "distance": 100, "dof": "deep", "subject_ratio": 0.1},
    "CAM_WIDE": {"name": "全景", "fov": 75, "distance": 50, "dof": "deep", "subject_ratio": 0.3},
    "CAM_MED": {"name": "中景", "fov": 50, "distance": 20, "dof": "medium", "subject_ratio": 0.5},
    "CAM_CLOSE": {"name": "近景", "fov": 35, "distance": 8, "dof": "shallow", "subject_ratio": 0.7},
    "CAM_CU": {"name": "特写", "fov": 20, "distance": 3, "dof": "very_shallow", "subject_ratio": 0.9},
    "CAM_MACRO": {"name": "微距", "fov": 10, "distance": 0.5, "dof": "extreme_shallow", "subject_ratio": 1.0},
}

CAMERA_MOVEMENT = {
    "CM_FIXED": {"name": "固定", "pan_x": 0, "pan_y": 0, "zoom": 0, "shake": 0, "duration_s": 0},
    "CM_SLOW_PUSH": {"name": "慢推", "zoom": 0.05, "duration_s": 5, "ease": "ease_in_out"},
    "CM_FAST_PUSH": {"name": "快推", "zoom": 0.3, "duration_s": 1, "ease": "ease_in"},
    "CM_PAN_LEFT": {"name": "左摇", "pan_x": -10, "duration_s": 3, "ease": "linear"},
    "CM_PAN_RIGHT": {"name": "右摇", "pan_x": 10, "duration_s": 3, "ease": "linear"},
    "CM_TILT_UP": {"name": "上摇", "pan_y": -5, "duration_s": 2, "ease": "ease_out"},
    "CM_TILT_DOWN": {"name": "下摇", "pan_y": 5, "duration_s": 2, "ease": "ease_out"},
    "CM_SHAKE": {"name": "抖动", "shake": 3, "shake_hz": 12, "duration_s": 0.5},
    "CM_DOLLY": {"name": "平移轨道", "pan_x": 30, "pan_y": 0, "duration_s": 8, "ease": "ease_in_out"},
}


# ═══════════════════════════════════════════
# PART 4: 人物主体参数库
# ═══════════════════════════════════════════

CHARACTER_BODY = {
    "BODY_MALE_M": {"name": "成年男性中等", "height_cm": 175, "build": "medium", "proportion": "standard"},
    "BODY_MALE_L": {"name": "成年男性高大", "height_cm": 190, "build": "athletic", "proportion": "broad_shoulder"},
    "BODY_FEMALE_M": {"name": "成年女性中等", "height_cm": 165, "build": "medium", "proportion": "standard"},
    "BODY_FEMALE_S": {"name": "成年女性娇小", "height_cm": 155, "build": "slim", "proportion": "petite"},
    "BODY_CHILD": {"name": "儿童", "height_cm": 120, "build": "small", "proportion": "child"},
    "BODY_ELDER": {"name": "老人", "height_cm": 160, "build": "thin", "proportion": "stooped"},
}

CHARACTER_HAND = {
    "H_OPEN": {"name": "摊开手", "palm_angle": 180, "fingers": [0,0,0,0,0]},
    "H_FIST": {"name": "握拳", "palm_angle": 0, "fingers": [90,90,90,90,90]},
    "H_POINT": {"name": "指", "palm_angle": 90, "fingers": [0,0,0,0,-45]},
    "H_GRASP": {"name": "抓握", "palm_angle": 45, "fingers": [60,60,60,60,60]},
    "H_REST": {"name": "自然放松", "palm_angle": 30, "fingers": [15,15,15,15,15]},
}

CHARACTER_MOUTH = {
    "M_CLOSED": {"name": "闭嘴", "open_mm": 0, "shape": "neutral"},
    "M_SLIGHT": {"name": "微张", "open_mm": 3, "shape": "relaxed"},
    "M_HALF": {"name": "半张", "open_mm": 8, "shape": "oval"},
    "M_WIDE": {"name": "大张", "open_mm": 15, "shape": "wide_oval"},
    "M_AA": {"name": "ɑ音", "open_mm": 14, "shape": "tall_oval"},
    "M_EE": {"name": "i音", "open_mm": 4, "shape": "wide_flat"},
    "M_OO": {"name": "u音", "open_mm": 2, "shape": "round_small"},
    "M_FF": {"name": "f音", "open_mm": 1, "shape": "lip_bite"},
}

# ═══════════════════════════════════════════
# 眼部系统 — 毫米级参数拆解
# ═══════════════════════════════════════════

# 4.1 眼皮开合 (上眼睑位置, 0=全睁 1=全闭)
CHARACTER_EYELID = {
    "EL_FULL_OPEN":   {"name": "全睁", "upper_lid": 0.00, "lower_lid": 1.00, "eye_exposure": 1.0},
    "EL_WIDE":        {"name": "瞪大", "upper_lid": -0.15, "lower_lid": 1.10, "eye_exposure": 1.25},
    "EL_NORMAL":      {"name": "正常", "upper_lid": 0.10, "lower_lid": 0.95, "eye_exposure": 0.90},
    "EL_RELAXED":     {"name": "放松", "upper_lid": 0.35, "lower_lid": 0.85, "eye_exposure": 0.70},
    "EL_HALF":        {"name": "半睁", "upper_lid": 0.55, "lower_lid": 0.75, "eye_exposure": 0.45},
    "EL_NARROW":      {"name": "微眯", "upper_lid": 0.70, "lower_lid": 0.70, "eye_exposure": 0.25},
    "EL_SQUINT":      {"name": "眯眼", "upper_lid": 0.85, "lower_lid": 0.60, "eye_exposure": 0.10},
    "EL_CLOSED":      {"name": "闭眼", "upper_lid": 1.00, "lower_lid": 0.50, "eye_exposure": 0.0},
    "EL_TIGHT":       {"name": "紧闭", "upper_lid": 1.10, "lower_lid": 0.55, "eye_exposure": -0.1},
}

# 4.2 眼球转向 (独立XY轴角度, 精度1°)
CHARACTER_GAZE = {
    "GZ_CENTER":      {"name": "正前方", "angle_x": 0, "angle_y": 0, "focus": "mid"},
    "GZ_UP":          {"name": "向上", "angle_x": 0, "angle_y": -12, "focus": "far"},
    "GZ_DOWN":        {"name": "向下", "angle_x": 0, "angle_y": 15, "focus": "near"},
    "GZ_LEFT":        {"name": "向左", "angle_x": -15, "angle_y": 0, "focus": "left"},
    "GZ_RIGHT":       {"name": "向右", "angle_x": 15, "angle_y": 0, "focus": "right"},
    "GZ_UP_LEFT":     {"name": "左上", "angle_x": -12, "angle_y": -10, "focus": "far_left"},
    "GZ_UP_RIGHT":    {"name": "右上", "angle_x": 12, "angle_y": -10, "focus": "far_right"},
    "GZ_DOWN_LEFT":   {"name": "左下", "angle_x": -12, "angle_y": 13, "focus": "near_left"},
    "GZ_DOWN_RIGHT":  {"name": "右下", "angle_x": 12, "angle_y": 13, "focus": "near_right"},
    # 微调偏移
    "GZ_SLIDE_L":     {"name": "左移", "angle_x": -5, "angle_y": 0, "focus": "shift"},
    "GZ_SLIDE_R":     {"name": "右移", "angle_x": 5, "angle_y": 0, "focus": "shift"},
    "GZ_GLANCE_UP":   {"name": "瞥上", "angle_x": 0, "angle_y": -8, "focus": "glance"},
    "GZ_GLANCE_DOWN": {"name": "瞥下", "angle_x": 0, "angle_y": 10, "focus": "glance"},
}

# 4.3 瞳孔缩放 (独立, 受光线+情绪联动)
CHARACTER_PUPIL = {
    "PP_DILATED_3":   {"name": "极度放大", "size": 0.85, "trigger": "暗光/惊恐/极度兴趣"},
    "PP_DILATED_2":   {"name": "明显放大", "size": 0.70, "trigger": "弱光/兴奋/好感"},
    "PP_DILATED_1":   {"name": "微放大", "size": 0.55, "trigger": "柔和光/放松/兴趣"},
    "PP_NORMAL":      {"name": "正常", "size": 0.40, "trigger": "日常光线/平静"},
    "PP_CONTRACT_1":  {"name": "微收缩", "size": 0.28, "trigger": "明亮/专注"},
    "PP_CONTRACT_2":  {"name": "明显收缩", "size": 0.18, "trigger": "强光/紧张/愤怒"},
    "PP_PINPOINT":    {"name": "针尖", "size": 0.08, "trigger": "极强光/极度恐惧"},
}

# 4.4 眨眼模式 (微秒级可控)
CHARACTER_BLINK = {
    "BLK_NORMAL":     {"name": "正常", "interval_s": 4.0, "duration_ms": 150, "asymmetry": 0},
    "BLK_FAST":       {"name": "快速", "interval_s": 1.5, "duration_ms": 80, "asymmetry": 0},
    "BLK_SLOW":       {"name": "缓慢", "interval_s": 6.0, "duration_ms": 350, "asymmetry": 0.1},
    "BLK_FLUTTER":    {"name": "颤动", "interval_s": 0.5, "duration_ms": 60, "asymmetry": 0.2},
    "BLK_NONE":       {"name": "不眨", "interval_s": 99, "duration_ms": 0, "asymmetry": 0},
    "BLK_WINK_L":     {"name": "左眼单眨", "interval_s": 99, "duration_ms": 200, "asymmetry": 1.0, "side": "left"},
    "BLK_WINK_R":     {"name": "右眼单眨", "interval_s": 99, "duration_ms": 200, "asymmetry": 1.0, "side": "right"},
    "BLK_TEAR":       {"name": "含泪", "interval_s": 2.0, "duration_ms": 250, "asymmetry": 0.15},
}

# 4.5 眼尾/眼角弧度 (独立参数, 表达情绪微差)
CHARACTER_EYE_CORNER = {
    "EC_NEUTRAL":     {"name": "平直", "outer_angle": 0, "inner_angle": 0},
    "EC_SMILE":       {"name": "笑弯", "outer_angle": -12, "inner_angle": -5, "crowfeet": 0.6},
    "EC_SAD":         {"name": "下垂", "outer_angle": 10, "inner_angle": -3, "crowfeet": 0},
    "EC_ANGRY":       {"name": "内压", "outer_angle": -5, "inner_angle": -8, "crowfeet": 0},
    "EC_SURPRISE":    {"name": "上扬", "outer_angle": -8, "inner_angle": 3, "crowfeet": 0.2},
    "EC_TIRED":       {"name": "疲惫下垂", "outer_angle": 15, "inner_angle": 5, "crowfeet": 0.3},
}

# 4.6 眼眶明暗 (配合光影, 强化情绪)
CHARACTER_EYE_SOCKET = {
    "ES_FLAT":        {"name": "平光", "shadow": 0, "highlight": 0},
    "ES_DEEP":        {"name": "深邃", "shadow": 0.6, "highlight": 0.1},
    "ES_BRIGHT":      {"name": "明亮", "shadow": 0.1, "highlight": 0.5},
    "ES_HOLLOW":      {"name": "凹陷", "shadow": 0.8, "highlight": 0},
    "ES_PUFFY":       {"name": "浮肿", "shadow": 0.2, "highlight": 0.3, "puffiness": 0.5},
}

# 4.7 视线移动速度 (°/s, 控制扫视/追踪/凝视)
CHARACTER_GAZE_SPEED = {
    "GS_FIXED":       {"name": "凝视不动", "speed_dps": 0},
    "GS_SLOW_TRACK":  {"name": "缓慢追踪", "speed_dps": 5},
    "GS_NORMAL_TRACK":{"name": "正常追踪", "speed_dps": 15},
    "GS_QUICK_SCAN":  {"name": "快速扫视", "speed_dps": 40},
    "GS_SACCADE":     {"name": "眼跳", "speed_dps": 200},
}

# 4.8 眼部联动预设 (一键调用, 全维度)  
EYE_PRESETS = {
    "eye_joy": {
        "name": "喜悦之眼",
        "eyelid": "EL_HALF", "gaze": "GZ_CENTER",
        "pupil": "PP_DILATED_1", "blink": "BLK_FAST",
        "corner": "EC_SMILE", "socket": "ES_BRIGHT",
        "gaze_speed": "GS_SLOW_TRACK",
    },
    "eye_anger": {
        "name": "愤怒之眼",
        "eyelid": "EL_NARROW", "gaze": "GZ_CENTER",
        "pupil": "PP_CONTRACT_2", "blink": "BLK_SLOW",
        "corner": "EC_ANGRY", "socket": "ES_DEEP",
        "gaze_speed": "GS_FIXED",
    },
    "eye_sadness": {
        "name": "悲伤之眼",
        "eyelid": "EL_HALF", "gaze": "GZ_DOWN",
        "pupil": "PP_DILATED_1", "blink": "BLK_TEAR",
        "corner": "EC_SAD", "socket": "ES_HOLLOW",
        "gaze_speed": "GS_SLOW_TRACK",
    },
    "eye_fear": {
        "name": "惊恐之眼",
        "eyelid": "EL_WIDE", "gaze": "GZ_CENTER",
        "pupil": "PP_DILATED_3", "blink": "BLK_FLUTTER",
        "corner": "EC_SURPRISE", "socket": "ES_HOLLOW",
        "gaze_speed": "GS_QUICK_SCAN",
    },
    "eye_interest": {
        "name": "专注之眼",
        "eyelid": "EL_NORMAL", "gaze": "GZ_CENTER",
        "pupil": "PP_DILATED_2", "blink": "BLK_SLOW",
        "corner": "EC_NEUTRAL", "socket": "ES_FLAT",
        "gaze_speed": "GS_NORMAL_TRACK",
    },
    "eye_surprise": {
        "name": "惊讶之眼",
        "eyelid": "EL_WIDE", "gaze": "GZ_CENTER",
        "pupil": "PP_DILATED_1", "blink": "BLK_NONE",
        "corner": "EC_SURPRISE", "socket": "ES_BRIGHT",
        "gaze_speed": "GS_SACCADE",
    },
    "eye_tender": {
        "name": "温柔之眼",
        "eyelid": "EL_RELAXED", "gaze": "GZ_DOWN_RIGHT",
        "pupil": "PP_DILATED_2", "blink": "BLK_SLOW",
        "corner": "EC_SMILE", "socket": "ES_BRIGHT",
        "gaze_speed": "GS_SLOW_TRACK",
    },
    "eye_suspicious": {
        "name": "怀疑之眼",
        "eyelid": "EL_NARROW", "gaze": "GZ_SLIDE_R",
        "pupil": "PP_NORMAL", "blink": "BLK_SLOW",
        "corner": "EC_ANGRY", "socket": "ES_DEEP",
        "gaze_speed": "GS_QUICK_SCAN",
    },
    "eye_tired": {
        "name": "疲惫之眼",
        "eyelid": "EL_HALF", "gaze": "GZ_DOWN",
        "pupil": "PP_CONTRACT_1", "blink": "BLK_SLOW",
        "corner": "EC_TIRED", "socket": "ES_PUFFY",
        "gaze_speed": "GS_SLOW_TRACK",
    },
}

CHARACTER_HAIR = {
    "HR_SHORT": {"name": "短发", "length_cm": 5, "density": 0.9, "texture": "straight", "sway_amp": 0.3},
    "HR_MEDIUM": {"name": "中长发", "length_cm": 25, "density": 0.8, "texture": "wavy", "sway_amp": 1.0},
    "HR_LONG": {"name": "长发", "length_cm": 60, "density": 0.7, "texture": "smooth", "sway_amp": 1.5},
    "HR_CURLY": {"name": "卷发", "length_cm": 15, "density": 0.6, "texture": "curly", "sway_amp": 0.4},
    "HR_BEARD": {"name": "胡须", "length_cm": 3, "density": 0.5, "texture": "coarse", "sway_amp": 0.2},
}

# 情绪联动表 — 一个情绪标签, 自动匹配全维度 (含眼神精密参数)
EMOTION_PROFILE = {
    "joy": {
        "name": "喜悦",
        # 口型
        "mouth": "M_WIDE", "mouth_open_mm": 8,
        # 眼部精密
        "eye_preset": "eye_joy",
        "eyelid": "EL_HALF", "gaze": "GZ_CENTER", "pupil": "PP_DILATED_1",
        "blink": "BLK_FAST", "eye_corner": "EC_SMILE", "eye_socket": "ES_BRIGHT",
        "gaze_speed": "GS_SLOW_TRACK",
        # 眉
        "brow_angle": 5, "brow_height": 0.1,
        # 面颊
        "cheek": "raised", "cheek_lift_mm": 2,
        # 肢体
        "body_posture": "open", "gesture_speed": 1.3, "gesture_amp": 1.2,
        "finger_spread": 0.3, "arm_swing": 0.4,
        # 光影
        "light_brightness": "LB_03", "light_contrast": "medium", "light_warmth": 0.2,
        # 镜头
        "cam_distance": "near", "dof_shift": -0.1,
        # 语音
        "voice_pitch": 1.1, "voice_speed": 1.1, "voice_breath": 0.2,
    },
    "anger": {
        "name": "愤怒",
        "mouth": "M_HALF", "mouth_open_mm": 6,
        "eye_preset": "eye_anger",
        "eyelid": "EL_NARROW", "gaze": "GZ_CENTER", "pupil": "PP_CONTRACT_2",
        "blink": "BLK_SLOW", "eye_corner": "EC_ANGRY", "eye_socket": "ES_DEEP",
        "gaze_speed": "GS_FIXED",
        "brow_angle": -15, "brow_height": -0.3,
        "cheek": "tense", "cheek_lift_mm": -1,
        "body_posture": "tense", "gesture_speed": 1.5, "gesture_amp": 1.5,
        "finger_spread": 0.1, "arm_swing": 0.7,
        "light_brightness": "LB_04", "light_contrast": "high", "light_warmth": -0.1,
        "cam_distance": "close", "dof_shift": -0.2,
        "voice_pitch": 0.8, "voice_speed": 1.3, "voice_breath": 0.3,
    },
    "sadness": {
        "name": "悲伤",
        "mouth": "M_SLIGHT", "mouth_open_mm": 2,
        "eye_preset": "eye_sadness",
        "eyelid": "EL_HALF", "gaze": "GZ_DOWN", "pupil": "PP_DILATED_1",
        "blink": "BLK_TEAR", "eye_corner": "EC_SAD", "eye_socket": "ES_HOLLOW",
        "gaze_speed": "GS_SLOW_TRACK",
        "brow_angle": 10, "brow_height": -0.1,
        "cheek": "dropped", "cheek_lift_mm": -2,
        "body_posture": "closed", "gesture_speed": 0.6, "gesture_amp": 0.4,
        "finger_spread": 0.2, "arm_swing": 0.2,
        "light_brightness": "LB_01", "light_contrast": "low", "light_warmth": 0,
        "cam_distance": "medium", "dof_shift": 0.1,
        "voice_pitch": 0.9, "voice_speed": 0.7, "voice_breath": 0.4,
    },
    "fear": {
        "name": "惊恐",
        "mouth": "M_WIDE", "mouth_open_mm": 10,
        "eye_preset": "eye_fear",
        "eyelid": "EL_WIDE", "gaze": "GZ_CENTER", "pupil": "PP_DILATED_3",
        "blink": "BLK_FLUTTER", "eye_corner": "EC_SURPRISE", "eye_socket": "ES_HOLLOW",
        "gaze_speed": "GS_QUICK_SCAN",
        "brow_angle": -10, "brow_height": 0.3,
        "cheek": "tense", "cheek_lift_mm": 0,
        "body_posture": "defensive", "gesture_speed": 2.0, "gesture_amp": 0.8,
        "finger_spread": 0.8, "arm_swing": 0.3,
        "light_brightness": "LB_01", "light_contrast": "high", "light_warmth": -0.2,
        "cam_distance": "close", "dof_shift": -0.3,
        "voice_pitch": 1.3, "voice_speed": 1.5, "voice_breath": 0.6,
    },
    "calm": {
        "name": "平静",
        "mouth": "M_CLOSED", "mouth_open_mm": 0,
        "eye_preset": None,
        "eyelid": "EL_NORMAL", "gaze": "GZ_CENTER", "pupil": "PP_NORMAL",
        "blink": "BLK_NORMAL", "eye_corner": "EC_NEUTRAL", "eye_socket": "ES_FLAT",
        "gaze_speed": "GS_SLOW_TRACK",
        "brow_angle": 0, "brow_height": 0,
        "cheek": "relaxed", "cheek_lift_mm": 0,
        "body_posture": "relaxed", "gesture_speed": 1.0, "gesture_amp": 1.0,
        "finger_spread": 0.15, "arm_swing": 0.3,
        "light_brightness": "LB_02", "light_contrast": "medium", "light_warmth": 0,
        "cam_distance": "medium", "dof_shift": 0,
        "voice_pitch": 1.0, "voice_speed": 1.0, "voice_breath": 0.1,
    },
    "tender": {
        "name": "温柔",
        "mouth": "M_SLIGHT", "mouth_open_mm": 1,
        "eye_preset": "eye_tender",
        "eyelid": "EL_RELAXED", "gaze": "GZ_DOWN_RIGHT", "pupil": "PP_DILATED_2",
        "blink": "BLK_SLOW", "eye_corner": "EC_SMILE", "eye_socket": "ES_BRIGHT",
        "gaze_speed": "GS_SLOW_TRACK",
        "brow_angle": 3, "brow_height": 0.05,
        "cheek": "soft", "cheek_lift_mm": 1,
        "body_posture": "leaning", "gesture_speed": 0.7, "gesture_amp": 0.6,
        "finger_spread": 0.25, "arm_swing": 0.2,
        "light_brightness": "LB_02", "light_contrast": "low", "light_warmth": 0.3,
        "cam_distance": "close", "dof_shift": 0.15,
        "voice_pitch": 1.0, "voice_speed": 0.8, "voice_breath": 0.3,
    },
    "surprise": {
        "name": "惊讶",
        "mouth": "M_HALF", "mouth_open_mm": 9,
        "eye_preset": "eye_surprise",
        "eyelid": "EL_WIDE", "gaze": "GZ_CENTER", "pupil": "PP_DILATED_1",
        "blink": "BLK_NONE", "eye_corner": "EC_SURPRISE", "eye_socket": "ES_BRIGHT",
        "gaze_speed": "GS_SACCADE",
        "brow_angle": -8, "brow_height": 0.25,
        "cheek": "raised", "cheek_lift_mm": 1,
        "body_posture": "open", "gesture_speed": 1.5, "gesture_amp": 0.6,
        "finger_spread": 0.6, "arm_swing": 0.1,
        "light_brightness": "LB_03", "light_contrast": "medium", "light_warmth": 0.1,
        "cam_distance": "medium", "dof_shift": -0.05,
        "voice_pitch": 1.2, "voice_speed": 1.2, "voice_breath": 0.2,
    },
    "disgust": {
        "name": "厌恶",
        "mouth": "M_SLIGHT", "mouth_open_mm": 1,
        "eye_preset": None,
        "eyelid": "EL_NARROW", "gaze": "GZ_SLIDE_R", "pupil": "PP_CONTRACT_1",
        "blink": "BLK_FAST", "eye_corner": "EC_ANGRY", "eye_socket": "ES_DEEP",
        "gaze_speed": "GS_QUICK_SCAN",
        "brow_angle": -10, "brow_height": -0.2,
        "cheek": "tense", "cheek_lift_mm": 0,
        "body_posture": "defensive", "gesture_speed": 1.2, "gesture_amp": 0.5,
        "finger_spread": 0.1, "arm_swing": 0.3,
        "light_brightness": "LB_02", "light_contrast": "medium", "light_warmth": -0.1,
        "cam_distance": "medium", "dof_shift": 0.05,
        "voice_pitch": 0.85, "voice_speed": 1.1, "voice_breath": 0.15,
    },
    "suspicious": {
        "name": "怀疑",
        "mouth": "M_CLOSED", "mouth_open_mm": 0,
        "eye_preset": "eye_suspicious",
        "eyelid": "EL_NARROW", "gaze": "GZ_SLIDE_R", "pupil": "PP_NORMAL",
        "blink": "BLK_SLOW", "eye_corner": "EC_ANGRY", "eye_socket": "ES_DEEP",
        "gaze_speed": "GS_QUICK_SCAN",
        "brow_angle": -5, "brow_height": -0.15,
        "cheek": "tense", "cheek_lift_mm": -0.5,
        "body_posture": "closed", "gesture_speed": 0.8, "gesture_amp": 0.4,
        "finger_spread": 0.1, "arm_swing": 0.2,
        "light_brightness": "LB_02", "light_contrast": "high", "light_warmth": -0.15,
        "cam_distance": "close", "dof_shift": -0.1,
        "voice_pitch": 0.95, "voice_speed": 0.9, "voice_breath": 0.1,
    },
    "tired": {
        "name": "疲惫",
        "mouth": "M_SLIGHT", "mouth_open_mm": 1,
        "eye_preset": "eye_tired",
        "eyelid": "EL_HALF", "gaze": "GZ_DOWN", "pupil": "PP_CONTRACT_1",
        "blink": "BLK_SLOW", "eye_corner": "EC_TIRED", "eye_socket": "ES_PUFFY",
        "gaze_speed": "GS_SLOW_TRACK",
        "brow_angle": 8, "brow_height": -0.1,
        "cheek": "dropped", "cheek_lift_mm": -2,
        "body_posture": "slumped", "gesture_speed": 0.5, "gesture_amp": 0.3,
        "finger_spread": 0.1, "arm_swing": 0.15,
        "light_brightness": "LB_01", "light_contrast": "low", "light_warmth": 0.1,
        "cam_distance": "medium", "dof_shift": 0.1,
        "voice_pitch": 0.9, "voice_speed": 0.6, "voice_breath": 0.5,
    },
}


# ═══════════════════════════════════════════
# PART 4.5A: 服饰参数库
# ═══════════════════════════════════════════

CLOTHING_UPPER = {
    "CU_TEE": {"name": "T恤", "shape": "loose", "sleeve": "short", "collar": "round", "thickness": 1},
    "CU_SHIRT": {"name": "衬衫", "shape": "fitted", "sleeve": "long", "collar": "point", "thickness": 1},
    "CU_HOODIE": {"name": "卫衣", "shape": "oversized", "sleeve": "long", "collar": "hood", "thickness": 3},
    "CU_JACKET": {"name": "夹克", "shape": "boxy", "sleeve": "long", "collar": "stand", "thickness": 2},
    "CU_COAT": {"name": "大衣", "shape": "long", "sleeve": "long", "collar": "lapel", "thickness": 4},
    "CU_VEST": {"name": "背心", "shape": "fitted", "sleeve": "none", "collar": "scoop", "thickness": 1},
    "CU_TANK": {"name": "无袖衫", "shape": "tight", "sleeve": "none", "collar": "round", "thickness": 1},
}

CLOTHING_LOWER = {
    "CL_JEANS": {"name": "牛仔裤", "shape": "straight", "length": "full", "stiffness": 3, "creases": 4},
    "CL_SLACKS": {"name": "西裤", "shape": "straight", "length": "full", "stiffness": 2, "creases": 2},
    "CL_SHORTS": {"name": "短裤", "shape": "loose", "length": "knee", "stiffness": 1, "creases": 1},
    "CL_SKIRT": {"name": "裙子", "shape": "flare", "length": "knee", "stiffness": 1, "creases": 3},
    "CL_JOGGER": {"name": "运动裤", "shape": "tapered", "length": "full", "stiffness": 1, "creases": 5},
    "CL_CARGO": {"name": "工装裤", "shape": "baggy", "length": "full", "stiffness": 2, "creases": 4},
    "CL_TIGHTS": {"name": "紧身裤", "shape": "tight", "length": "full", "stiffness": 1, "creases": 0},
}

CLOTHING_FOOTWEAR = {
    "FW_SNEAKER": {"name": "运动鞋", "height": "low", "sole": 3, "material": "leather_synthetic"},
    "FW_BOOT": {"name": "靴子", "height": "high", "sole": 5, "material": "leather"},
    "FW_LOAFER": {"name": "皮鞋", "height": "low", "sole": 2, "material": "leather"},
    "FW_SANDAL": {"name": "凉鞋", "height": "flat", "sole": 1, "material": "rubber"},
    "FW_BAREFOOT": {"name": "赤脚", "height": "none", "sole": 0, "material": "none"},
    "FW_HIGH_HEEL": {"name": "高跟鞋", "height": "high", "sole": 1, "material": "leather"},
}

CLOTHING_ACCESSORY = {
    "AC_WATCH": {"name": "手表", "position": "wrist_left", "size": "small", "reflectivity": 0.8},
    "AC_GLASSES": {"name": "眼镜", "position": "eyes", "size": "medium", "reflectivity": 0.5},
    "AC_HAT": {"name": "帽子", "position": "head_top", "size": "large", "reflectivity": 0.1},
    "AC_SCARF": {"name": "围巾", "position": "neck", "size": "long", "reflectivity": 0.05},
    "AC_BELT": {"name": "皮带", "position": "waist", "size": "small", "reflectivity": 0.3},
    "AC_RING": {"name": "戒指", "position": "finger", "size": "tiny", "reflectivity": 0.9},
}

# 布料物理参数 (与风联动)
FABRIC_PHYSICS = {
    "FP_WIND_RESPONSE": {"stiff_to_soft": ["denim", "cotton", "silk", "chiffon"],
                         "sway_amplitude": [0.0, 0.1, 0.4, 0.8]},
    "FP_CREASE_FIDELITY": {"none": 0, "light": 2, "medium": 5, "heavy": 10},
    "FP_SWING_DAMPING": {"heavy": 0.3, "medium": 0.6, "light": 0.9},
}


# ═══════════════════════════════════════════
# PART 4.5B: 光照物理参数 (AO/SSS/高漫分离/阴影)
# ═══════════════════════════════════════════

LIGHT_PHYSICS = {
    # 环境光遮蔽
    "AO_NONE": {"name": "无AO", "strength": 0, "radius_px": 0, "samples": 0},
    "AO_LIGHT": {"name": "轻AO", "strength": 0.3, "radius_px": 8, "samples": 4},
    "AO_MEDIUM": {"name": "中AO", "strength": 0.6, "radius_px": 16, "samples": 8},
    "AO_HEAVY": {"name": "重AO", "strength": 1.0, "radius_px": 32, "samples": 16},
    "AO_GI": {"name": "全局光照AO", "strength": 0.4, "radius_px": 64, "samples": 32},

    # 次表面散射
    "SSS_NONE": {"name": "无SSS", "depth_mm": 0, "color": "none", "blur": 0},
    "SSS_SKIN": {"name": "皮肤SSS", "depth_mm": 1.5, "color": "#FFCCAA", "blur": 3},
    "SSS_WAX": {"name": "蜡质SSS", "depth_mm": 3.0, "color": "#FFFFFF", "blur": 5},
    "SSS_LEAF": {"name": "叶片SSS", "depth_mm": 0.5, "color": "#AACC88", "blur": 2},
    "SSS_MARBLE": {"name": "大理石SSS", "depth_mm": 8.0, "color": "#EEEEEE", "blur": 6},

    # 高光/漫反射分离
    "SPEC_SHARP": {"name": "锐利高光", "intensity": 1.0, "roughness": 0.1, "fresnel": 0.04},
    "SPEC_SOFT": {"name": "柔和高光", "intensity": 0.6, "roughness": 0.4, "fresnel": 0.04},
    "SPEC_MATTE": {"name": "哑光", "intensity": 0.1, "roughness": 0.9, "fresnel": 0.02},
    "SPEC_METAL": {"name": "金属", "intensity": 1.5, "roughness": 0.2, "fresnel": 0.8},
    "SPEC_WET": {"name": "湿润", "intensity": 1.2, "roughness": 0.05, "fresnel": 0.3},
    "DIFF_LAMBERT": {"name": "Lambert漫反射", "albedo": 1.0, "roughness_diff": 1.0},
    "DIFF_OREN_NAYAR": {"name": "Oren-Nayar", "albedo": 1.0, "roughness_diff": 0.6},

    # 阴影柔硬
    "SHADOW_HARD": {"name": "硬阴影", "blur_px": 0, "opacity": 1.0, "contact_hardness": 1.0},
    "SHADOW_SOFT": {"name": "软阴影", "blur_px": 8, "opacity": 0.8, "contact_hardness": 0.5},
    "SHADOW_DIFFUSE": {"name": "漫射阴影", "blur_px": 24, "opacity": 0.5, "contact_hardness": 0.0},
    "SHADOW_COLORED": {"name": "彩色阴影", "blur_px": 6, "opacity": 0.6, "tint": "#334455"},
}


# ═══════════════════════════════════════════
# PART 4.5C: 手指独立关节参数库
# ═══════════════════════════════════════════

# 5指 × 3关节 = 15个独立角度, 每指有名称/位置/联动组
FINGER_JOINT = {
    # 拇指 (Carpometacarpal→Metacarpophalangeal→Interphalangeal)
    "FJ_THUMB_CMC": {"name": "拇指掌腕", "finger": "thumb", "joint_order": 0, "range_deg": [-45, 45], "axis": "flexion_abduction"},
    "FJ_THUMB_MCP": {"name": "拇指掌指", "finger": "thumb", "joint_order": 1, "range_deg": [-30, 60], "axis": "flexion"},
    "FJ_THUMB_IP": {"name": "拇指指间", "finger": "thumb", "joint_order": 2, "range_deg": [0, 90], "axis": "flexion"},
    # 食指
    "FJ_INDEX_MCP": {"name": "食指掌指", "finger": "index", "joint_order": 0, "range_deg": [-15, 90], "axis": "flexion"},
    "FJ_INDEX_PIP": {"name": "食指近指间", "finger": "index", "joint_order": 1, "range_deg": [0, 110], "axis": "flexion"},
    "FJ_INDEX_DIP": {"name": "食指远指间", "finger": "index", "joint_order": 2, "range_deg": [0, 80], "axis": "flexion"},
    # 中指
    "FJ_MIDDLE_MCP": {"name": "中指掌指", "finger": "middle", "joint_order": 0, "range_deg": [-15, 90], "axis": "flexion"},
    "FJ_MIDDLE_PIP": {"name": "中指近指间", "finger": "middle", "joint_order": 1, "range_deg": [0, 110], "axis": "flexion"},
    "FJ_MIDDLE_DIP": {"name": "中指远指间", "finger": "middle", "joint_order": 2, "range_deg": [0, 80], "axis": "flexion"},
    # 无名指
    "FJ_RING_MCP": {"name": "无名指掌指", "finger": "ring", "joint_order": 0, "range_deg": [-10, 90], "axis": "flexion"},
    "FJ_RING_PIP": {"name": "无名指近指间", "finger": "ring", "joint_order": 1, "range_deg": [0, 110], "axis": "flexion"},
    "FJ_RING_DIP": {"name": "无名指远指间", "finger": "ring", "joint_order": 2, "range_deg": [0, 80], "axis": "flexion"},
    # 小指
    "FJ_PINKY_MCP": {"name": "小指掌指", "finger": "pinky", "joint_order": 0, "range_deg": [-5, 90], "axis": "flexion"},
    "FJ_PINKY_PIP": {"name": "小指近指间", "finger": "pinky", "joint_order": 1, "range_deg": [0, 110], "axis": "flexion"},
    "FJ_PINKY_DIP": {"name": "小指远指间", "finger": "pinky", "joint_order": 2, "range_deg": [0, 80], "axis": "flexion"},
}

# 手势预设 (一键设置全部15个关节)
HAND_PRESET = {
    "HP_OPEN": {"name": "张开", "desc": "五指自然伸展",
                "angles": {"THUMB_CMC": 15, "THUMB_MCP": 30, "THUMB_IP": 20,
                           "INDEX_MCP": 0, "INDEX_PIP": 0, "INDEX_DIP": 0,
                           "MIDDLE_MCP": 0, "MIDDLE_PIP": 0, "MIDDLE_DIP": 0,
                           "RING_MCP": 0, "RING_PIP": 0, "RING_DIP": 0,
                           "PINKY_MCP": 0, "PINKY_PIP": 0, "PINKY_DIP": 0}},
    "HP_FIST": {"name": "握拳", "desc": "五指弯曲收紧",
               "angles": {"THUMB_CMC": 30, "THUMB_MCP": 60, "THUMB_IP": 50,
                          "INDEX_MCP": 85, "INDEX_PIP": 105, "INDEX_DIP": 75,
                          "MIDDLE_MCP": 85, "MIDDLE_PIP": 105, "MIDDLE_DIP": 75,
                          "RING_MCP": 85, "RING_PIP": 105, "RING_DIP": 75,
                          "PINKY_MCP": 85, "PINKY_PIP": 105, "PINKY_DIP": 75}},
    "HP_POINT": {"name": "指点", "desc": "食指伸出，其余握拳",
                "angles": {"THUMB_CMC": 30, "THUMB_MCP": 50, "THUMB_IP": 40,
                           "INDEX_MCP": 0, "INDEX_PIP": 0, "INDEX_DIP": 0,
                           "MIDDLE_MCP": 85, "MIDDLE_PIP": 105, "MIDDLE_DIP": 75,
                           "RING_MCP": 85, "RING_PIP": 105, "RING_DIP": 75,
                           "PINKY_MCP": 85, "PINKY_PIP": 105, "PINKY_DIP": 75}},
    "HP_PEACE": {"name": "V字", "desc": "食指中指伸出",
                "angles": {"THUMB_CMC": 20, "THUMB_MCP": 50, "THUMB_IP": 40,
                           "INDEX_MCP": 0, "INDEX_PIP": 0, "INDEX_DIP": 0,
                           "MIDDLE_MCP": 0, "MIDDLE_PIP": 0, "MIDDLE_DIP": 0,
                           "RING_MCP": 85, "RING_PIP": 105, "RING_DIP": 75,
                           "PINKY_MCP": 85, "PINKY_PIP": 105, "PINKY_DIP": 75}},
    "HP_GRASP": {"name": "抓握", "desc": "半弯抓取物体",
                 "angles": {"THUMB_CMC": 20, "THUMB_MCP": 40, "THUMB_IP": 30,
                            "INDEX_MCP": 45, "INDEX_PIP": 60, "INDEX_DIP": 40,
                            "MIDDLE_MCP": 50, "MIDDLE_PIP": 65, "MIDDLE_DIP": 45,
                            "RING_MCP": 55, "RING_PIP": 70, "RING_DIP": 50,
                            "PINKY_MCP": 60, "PINKY_PIP": 75, "PINKY_DIP": 55}},
    "HP_DELICATE": {"name": "精细", "desc": "拇指食指捏合",
                    "angles": {"THUMB_CMC": 25, "THUMB_MCP": 35, "THUMB_IP": 50,
                               "INDEX_MCP": 20, "INDEX_PIP": 30, "INDEX_DIP": 30,
                               "MIDDLE_MCP": 30, "MIDDLE_PIP": 50, "MIDDLE_DIP": 40,
                               "RING_MCP": 50, "RING_PIP": 70, "RING_DIP": 50,
                               "PINKY_MCP": 60, "PINKY_PIP": 80, "PINKY_DIP": 60}},
    "HP_SWIPE": {"name": "滑动", "desc": "四指并拢侧向",
                 "angles": {"THUMB_CMC": 10, "THUMB_MCP": 20, "THUMB_IP": 10,
                            "INDEX_MCP": 0, "INDEX_PIP": 5, "INDEX_DIP": 5,
                            "MIDDLE_MCP": 0, "MIDDLE_PIP": 5, "MIDDLE_DIP": 5,
                            "RING_MCP": 0, "RING_PIP": 5, "RING_DIP": 5,
                            "PINKY_MCP": 0, "PINKY_PIP": 5, "PINKY_DIP": 5}},
    "HP_ROCK": {"name": "摇滚", "desc": "食指小指伸出",
                "angles": {"THUMB_CMC": 0, "THUMB_MCP": 40, "THUMB_IP": 30,
                           "INDEX_MCP": 0, "INDEX_PIP": 0, "INDEX_DIP": 0,
                           "MIDDLE_MCP": 85, "MIDDLE_PIP": 105, "MIDDLE_DIP": 75,
                           "RING_MCP": 85, "RING_PIP": 105, "RING_DIP": 75,
                           "PINKY_MCP": 0, "PINKY_PIP": 0, "PINKY_DIP": 0}},
}


# ═══════════════════════════════════════════
# PART 4.5D: 脚步声地面联动
# ═══════════════════════════════════════════

FOOTSTEP_GROUND = {
    "FG_STONE": {"name": "石板", "impact": "hard", "resonance": 0.8, "bass": 0.2, "treble": 0.7,
                 "dry_wet": 0.1, "decay_s": 0.3},
    "FG_COBBLE": {"name": "鹅卵石", "impact": "medium", "resonance": 0.5, "bass": 0.3, "treble": 0.5,
                  "dry_wet": 0.2, "decay_s": 0.4},
    "FG_GRASS": {"name": "草地", "impact": "soft", "resonance": 0.1, "bass": 0.5, "treble": 0.3,
                 "dry_wet": 0.6, "decay_s": 0.1},
    "FG_WOOD": {"name": "木地板", "impact": "medium", "resonance": 0.6, "bass": 0.4, "treble": 0.5,
                "dry_wet": 0.15, "decay_s": 0.35},
    "FG_SAND": {"name": "沙地", "impact": "soft", "resonance": 0.05, "bass": 0.6, "treble": 0.1,
                "dry_wet": 0.8, "decay_s": 0.05},
    "FG_SNOW": {"name": "雪地", "impact": "soft", "resonance": 0.0, "bass": 0.1, "treble": 0.3,
                "dry_wet": 0.9, "decay_s": 0.02},
    "FG_METAL": {"name": "金属", "impact": "hard", "resonance": 1.0, "bass": 0.1, "treble": 0.9,
                 "dry_wet": 0.05, "decay_s": 0.6},
    "FG_PUDDLE": {"name": "积水", "impact": "soft", "resonance": 0.1, "bass": 0.2, "treble": 0.4,
                  "dry_wet": 0.5, "decay_s": 0.15},
    "FG_CARPET": {"name": "地毯", "impact": "soft", "resonance": 0.0, "bass": 0.7, "treble": 0.05,
                  "dry_wet": 0.9, "decay_s": 0.02},
}

FOOTSTEP_SHOE = {
    "FS_BARE": {"name": "赤脚", "weight": 0.3, "surface_area": "small", "attack_ms": 30,
                "heel_click": 0.0, "scuff": 0.6},
    "FS_SNEAKER": {"name": "运动鞋", "weight": 0.5, "surface_area": "large", "attack_ms": 20,
                   "heel_click": 0.0, "scuff": 0.3},
    "FS_LEATHER": {"name": "皮鞋", "weight": 0.7, "surface_area": "small", "attack_ms": 10,
                   "heel_click": 0.8, "scuff": 0.2},
    "FS_BOOT": {"name": "靴子", "weight": 0.9, "surface_area": "large", "attack_ms": 8,
                "heel_click": 0.6, "scuff": 0.4},
    "FS_HIGH_HEEL": {"name": "高跟鞋", "weight": 0.4, "surface_area": "tiny", "attack_ms": 5,
                     "heel_click": 1.0, "scuff": 0.1},
}

# 地面类型与场景联动
GROUND_TO_FOOTSTEP = {
    "T_FLT_01": "FG_GRASS",    # 草原
    "T_HIL_01": "FG_GRASS",    # 丘陵
    "T_DESERT": "FG_SAND",     # 沙漠
    "T_SNOW": "FG_SNOW",       # 雪原
    "T_CITY": "FG_STONE",      # 城市
    "default": "FG_STONE",
}


# ═══════════════════════════════════════════
# PART 4.5E: FACS 面部动作编码系统
# ═══════════════════════════════════════════

FACS_UNITS = {
    # 眉毛动作 (AU1-7)
    "AU1": {"name": "眉毛内端上抬", "muscle": "frontalis_pars_medialis", "intensity_range": [0, 5],
            "visual": "inner_brow_raiser"},
    "AU2": {"name": "眉毛外端上抬", "muscle": "frontalis_pars_lateralis", "intensity_range": [0, 5],
            "visual": "outer_brow_raiser"},
    "AU4": {"name": "眉毛压低", "muscle": "depressor_glabellae", "intensity_range": [0, 5],
            "visual": "brow_lowerer"},
    "AU5": {"name": "上眼睑上抬", "muscle": "levator_palpebrae_superioris", "intensity_range": [0, 5],
            "visual": "upper_lid_raiser"},
    "AU6": {"name": "脸颊上抬", "muscle": "orbicularis_oculi_pars_orbitalis", "intensity_range": [0, 5],
            "visual": "cheek_raiser"},
    "AU7": {"name": "眼睑收紧", "muscle": "orbicularis_oculi_pars_palpebralis", "intensity_range": [0, 5],
            "visual": "lid_tightener"},
    # 眼部动作
    "AU43": {"name": "眼睛闭合", "muscle": "levator_palpebrae_relaxation", "intensity_range": [0, 5],
             "visual": "eyes_closed"},
    "AU45": {"name": "眨眼", "muscle": "orbicularis_oculi_pars_palpebralis", "intensity_range": [0, 5],
             "visual": "blink"},
    "AU46": {"name": "单眼眨", "muscle": "orbicularis_oculi_unilateral", "intensity_range": [0, 5],
             "visual": "wink"},
    # 鼻子动作
    "AU9": {"name": "鼻梁皱起", "muscle": "levator_labii_superioris_alaeque_nasi", "intensity_range": [0, 5],
            "visual": "nose_wrinkler"},
    # 嘴唇动作
    "AU10": {"name": "上唇上抬", "muscle": "levator_labii_superioris", "intensity_range": [0, 5],
             "visual": "upper_lip_raiser"},
    "AU12": {"name": "嘴角上拉", "muscle": "zygomaticus_major", "intensity_range": [0, 5],
             "visual": "lip_corner_puller"},
    "AU14": {"name": "嘴角收紧", "muscle": "buccinator", "intensity_range": [0, 5],
             "visual": "dimpler"},
    "AU15": {"name": "嘴角下压", "muscle": "depressor_anguli_oris", "intensity_range": [0, 5],
             "visual": "lip_corner_depressor"},
    "AU16": {"name": "下唇下压", "muscle": "depressor_labii_inferioris", "intensity_range": [0, 5],
             "visual": "lower_lip_depressor"},
    "AU17": {"name": "下巴上抬", "muscle": "mentalis", "intensity_range": [0, 5],
             "visual": "chin_raiser"},
    "AU18": {"name": "嘴唇噘起", "muscle": "incisivii_labii", "intensity_range": [0, 5],
             "visual": "lip_puckerer"},
    "AU20": {"name": "嘴唇拉伸", "muscle": "risorius", "intensity_range": [0, 5],
             "visual": "lip_stretcher"},
    "AU22": {"name": "嘴唇漏斗", "muscle": "orbicularis_oris", "intensity_range": [0, 5],
             "visual": "lip_funneler"},
    "AU23": {"name": "嘴唇收紧", "muscle": "orbicularis_oris", "intensity_range": [0, 5],
             "visual": "lip_tightener"},
    "AU24": {"name": "嘴唇压合", "muscle": "orbicularis_oris", "intensity_range": [0, 5],
             "visual": "lip_pressor"},
    "AU25": {"name": "嘴唇分开", "muscle": "depressor_labii_relaxation", "intensity_range": [0, 5],
             "visual": "lips_part"},
    "AU26": {"name": "下颚下垂", "muscle": "mylohyoid_relaxation", "intensity_range": [0, 5],
             "visual": "jaw_drop"},
    "AU27": {"name": "嘴巴张大", "muscle": "pterygoid_lateral", "intensity_range": [0, 5],
             "visual": "mouth_stretch"},
    "AU28": {"name": "嘴唇吸入", "muscle": "orbicularis_oris", "intensity_range": [0, 5],
             "visual": "lip_suck"},
}

# 经典情绪 = FACS 组合
FACS_EMOTION = {
    "joy_facs": {"name": "喜悦", "units": {"AU6": 4, "AU12": 4, "AU25": 2, "AU26": 1}},
    "sadness_facs": {"name": "悲伤", "units": {"AU1": 3, "AU4": 2, "AU15": 4, "AU17": 3}},
    "anger_facs": {"name": "愤怒", "units": {"AU4": 5, "AU5": 3, "AU7": 4, "AU10": 3}},  # 无AU23→AU10替代
    "fear_facs": {"name": "恐惧", "units": {"AU1": 4, "AU2": 4, "AU5": 5, "AU20": 3, "AU26": 3}},
    "surprise_facs": {"name": "惊讶", "units": {"AU1": 5, "AU2": 5, "AU5": 4, "AU26": 4}},
    "disgust_facs": {"name": "厌恶", "units": {"AU4": 2, "AU9": 5, "AU10": 3, "AU15": 2}},
    "contempt_facs": {"name": "轻蔑", "units": {"AU12": 2, "AU14": 3}},
    "tender_facs": {"name": "温柔", "units": {"AU6": 2, "AU12": 2, "AU14": 1}},
    "tired_facs": {"name": "疲惫", "units": {"AU5": -2, "AU7": 3, "AU15": 1, "AU43": 3}},
}


# ═══════════════════════════════════════════
# PART 4.5F: 剧情结构模板库
# ═══════════════════════════════════════════

STORY_STRUCTURES = {
    # 经典三幕
    "SS_THREE_ACT": {"name": "三幕结构",
        "acts": [
            {"act": 1, "name": "建制", "share": 0.25, "beats": ["ordinary_world", "inciting_incident", "call_to_adventure"]},
            {"act": 2, "name": "对抗", "share": 0.50, "beats": ["rising_action", "midpoint", "darkest_hour", "final_push"]},
            {"act": 3, "name": "解决", "share": 0.25, "beats": ["climax", "resolution", "new_normal"]},
        ]},
    # 起承转合
    "SS_QICHENGZHUANHE": {"name": "起承转合",
        "acts": [
            {"act": 1, "name": "起", "share": 0.25, "beats": ["introduce", "establish", "hook"]},
            {"act": 2, "name": "承", "share": 0.30, "beats": ["develop", "deepen", "complicate"]},
            {"act": 3, "name": "转", "share": 0.20, "beats": ["twist", "shift", "revelation"]},
            {"act": 4, "name": "合", "share": 0.25, "beats": ["converge", "resolve", "echo"]},
        ]},
    # 英雄之旅
    "SS_HERO_JOURNEY": {"name": "英雄之旅",
        "acts": [
            {"act": 1, "name": "启程", "share": 0.30, "beats": ["ordinary_world", "call", "refusal", "mentor", "threshold"]},
            {"act": 2, "name": "试炼", "share": 0.40, "beats": ["tests", "innermost_cave", "ordeal", "reward"]},
            {"act": 3, "name": "归来", "share": 0.30, "beats": ["road_back", "resurrection", "return_with_elixir"]},
        ]},
}

EMOTIONAL_ARC = {
    "EA_RISE": {"name": "上升弧", "curve": [0.2, 0.3, 0.5, 0.7, 0.9, 1.0], "desc": "从低到高，正面结局"},
    "EA_FALL": {"name": "下降弧", "curve": [0.9, 0.7, 0.5, 0.3, 0.2, 0.1], "desc": "从高到低，悲剧"},
    "EA_VALLEY": {"name": "低谷回升", "curve": [0.6, 0.3, 0.1, 0.4, 0.8, 0.95], "desc": "先跌后涨，逆转"},
    "EA_PEAK": {"name": "高峰回落", "curve": [0.3, 0.7, 0.9, 0.7, 0.5, 0.3], "desc": "先扬后抑，幻灭"},
    "EA_WAVE": {"name": "波动", "curve": [0.5, 0.3, 0.8, 0.2, 0.9, 0.6], "desc": "多次起伏，悬疑"},
    "EA_FLAT": {"name": "平静", "curve": [0.5, 0.55, 0.5, 0.45, 0.5, 0.5], "desc": "平稳叙事"},
}

CONFLICT_TYPES = {
    "CT_MAN_VS_MAN": {"name": "人vs人", "tension_source": "opposing_wills", "escalation": "confrontation_betrayal_showdown"},
    "CT_MAN_VS_NATURE": {"name": "人vs自然", "tension_source": "survival", "escalation": "warning_disaster_aftermath"},
    "CT_MAN_VS_SELF": {"name": "人vs自我", "tension_source": "inner_demon", "escalation": "denial_crisis_acceptance"},
    "CT_MAN_VS_SOCIETY": {"name": "人vs社会", "tension_source": "system_oppression", "escalation": "awakening_rebellion_verdict"},
    "CT_MAN_VS_FATE": {"name": "人vs命运", "tension_source": "inevitability", "escalation": "prophecy_struggle_fulfillment"},
}

PACING_PRESETS = {
    "PP_FAST": {"name": "快节奏", "avg_shot_s": 2.0, "cuts_per_minute": 30, "breath_room": 0.05},
    "PP_NORMAL": {"name": "正常", "avg_shot_s": 4.0, "cuts_per_minute": 15, "breath_room": 0.15},
    "PP_SLOW": {"name": "慢节奏", "avg_shot_s": 8.0, "cuts_per_minute": 7, "breath_room": 0.30},
    "PP_DREAMLIKE": {"name": "梦境", "avg_shot_s": 12.0, "cuts_per_minute": 3, "breath_room": 0.50},
}


# ═══════════════════════════════════════════
# PART 4.5G: 分镜语言规则库
# ═══════════════════════════════════════════

SHOT_TRANSITIONS = {
    "ST_CUT": {"name": "硬切", "frames": 0, "mood": "abrupt", "rule": "same_scene_or_match_action"},
    "ST_DISSOLVE": {"name": "叠化", "frames": 12, "mood": "gentle", "rule": "time_passage_or_memory"},
    "ST_FADE_OUT": {"name": "淡出", "frames": 24, "mood": "final", "rule": "chapter_end"},
    "ST_FADE_IN": {"name": "淡入", "frames": 24, "mood": "awakening", "rule": "chapter_begin"},
    "ST_WIPE_LEFT": {"name": "左划", "frames": 8, "mood": "forward", "rule": "spatial_continuity"},
    "ST_WIPE_RIGHT": {"name": "右划", "frames": 8, "mood": "backward", "rule": "spatial_continuity"},
    "ST_MATCH_CUT": {"name": "匹配剪辑", "frames": 0, "mood": "surreal", "rule": "shape_or_motion_match"},
    "ST_JUMP_CUT": {"name": "跳切", "frames": 0, "mood": "jarring", "rule": "intentional_discontinuity"},
}

SHOT_SIZES = {
    "SIZE_ECU": {"name": "大特写", "fov": 5, "subject_fill": 0.95, "purpose": "detail_obsession"},
    "SIZE_CU": {"name": "特写", "fov": 20, "subject_fill": 0.85, "purpose": "emotion_intimate"},
    "SIZE_MCU": {"name": "近景", "fov": 35, "subject_fill": 0.65, "purpose": "expression_read"},
    "SIZE_MS": {"name": "中景", "fov": 50, "subject_fill": 0.45, "purpose": "action_body"},
    "SIZE_MLS": {"name": "全景", "fov": 65, "subject_fill": 0.30, "purpose": "posture_environment"},
    "SIZE_LS": {"name": "远景", "fov": 80, "subject_fill": 0.15, "purpose": "figure_landscape"},
    "SIZE_ELS": {"name": "大远景", "fov": 110, "subject_fill": 0.03, "purpose": "epic_scale"},
}

# 180度轴线规则
AXIS_RULES = {
    "AX_180_LINE": {"name": "180度线", "desc": "两角色对话，摄影机不越过想象连线",
                    "violation": "跳轴导致观众迷失方向", "fix": "插入中性镜头过渡"},
    "AX_30_DEGREE": {"name": "30度规则", "desc": "同主体两个镜头至少转30度",
                      "violation": "跳切感", "fix": "加大角度或改变景别"},
    "AX_EYELINE_MATCH": {"name": "视线匹配", "desc": "看的方向在画面内保持一致",
                         "violation": "角色看向反方向", "fix": "翻转或插入POV"},
}

COMPOSITION_RULES = {
    "CR_RULE_OF_THIRDS": {"name": "三分法", "grid": "3x3", "anchor_points": 4,
                          "weight": {"power_point": 0.6, "center": 0.2, "edge": 0.2}},
    "CR_LEADING_LINES": {"name": "引导线", "types": ["diagonal", "s_curve", "converging"],
                         "destination": "subject_or_horizon"},
    "CR_HEADROOM": {"name": "头顶空间", "ratio": 0.08, "fix": "too_much_amateur_too_little_cramped"},
    "CR_LOOKROOM": {"name": "视线空间", "direction": "subject_look_direction",
                    "ratio": 0.33, "fix": "looking_off_screen_unbalanced"},
    "CR_SYMMETRY": {"name": "对称构图", "axis": "vertical_or_horizontal",
                    "mood": ["order", "power", "stillness"]},
    "CR_DUTCH_ANGLE": {"name": "倾斜构图", "angle_deg": [3, 15],
                       "mood": ["unease", "tension", "disorientation"]},
}


# ═══════════════════════════════════════════
# PART 4.5H: 色彩调色板库
# ═══════════════════════════════════════════

COLOR_PALETTES = {
    # 经典电影调色
    "CP_TEAL_ORANGE": {"name": "青橙", "primary": "#FF8C2A", "secondary": "#008B8B",
                       "shadows": "#0A1A2A", "highlights": "#FFD4A0",
                       "mood": "cinematic_blockbuster", "contrast": 1.2},
    "CP_WARM_SUNSET": {"name": "暖黄昏", "primary": "#FF6B35", "secondary": "#FFD700",
                       "shadows": "#2A1508", "highlights": "#FFF0CC",
                       "mood": "nostalgic_romantic", "contrast": 0.9},
    "CP_COOL_NOIR": {"name": "冷黑色", "primary": "#4A6FA5", "secondary": "#1A1A2E",
                     "shadows": "#000011", "highlights": "#8899BB",
                     "mood": "mystery_tension", "contrast": 1.5},
    "CP_PASTEL_DREAM": {"name": "粉彩梦", "primary": "#FFB5C2", "secondary": "#B5D8FF",
                        "shadows": "#2A2040", "highlights": "#FFF5F8",
                        "mood": "dreamy_soft", "contrast": 0.6},
    "CP_DESERT_DRY": {"name": "沙漠枯", "primary": "#C4A35A", "secondary": "#8B6914",
                      "shadows": "#1A1008", "highlights": "#F5E6C8",
                      "mood": "harsh_weathered", "contrast": 1.3},
    "CP_FOREST_DEEP": {"name": "森林深", "primary": "#2D5A27", "secondary": "#1A3A1A",
                       "shadows": "#0A1505", "highlights": "#8BBA7A",
                       "mood": "mysterious_nature", "contrast": 1.1},
    "CP_NEON_CYBER": {"name": "霓虹赛博", "primary": "#FF00FF", "secondary": "#00FFFF",
                      "shadows": "#0A0020", "highlights": "#FF88FF",
                      "mood": "cyberpunk_future", "contrast": 1.8},
    "CP_MONO_WARM": {"name": "暖单色", "primary": "#8B7355", "secondary": "#C4A882",
                     "shadows": "#1A1008", "highlights": "#F5E6D0",
                     "mood": "vintage_intimate", "contrast": 1.0},
}

COLOR_GRADING = {
    # 色温
    "CG_WARM_05": {"name": "微暖500K", "temp_shift_k": 500, "tint_magenta": 0},
    "CG_WARM_15": {"name": "暖1500K", "temp_shift_k": 1500, "tint_magenta": 5},
    "CG_COOL_05": {"name": "微冷-500K", "temp_shift_k": -500, "tint_magenta": -5},
    "CG_COOL_20": {"name": "冷-2000K", "temp_shift_k": -2000, "tint_magenta": -10},
    # 饱和度
    "CG_SAT_HIGH": {"name": "高饱和", "saturation": 1.4, "vibrance": 1.2},
    "CG_SAT_LOW": {"name": "低饱和", "saturation": 0.6, "vibrance": 0.5},
    "CG_SAT_DESAT": {"name": "去色", "saturation": 0.0, "vibrance": 0.1},
    # 对比度
    "CG_CON_HIGH": {"name": "高对比", "contrast": 1.5, "crush_black": 0.05, "clip_white": 0.05},
    "CG_CON_LOW": {"name": "低对比", "contrast": 0.7, "lift_black": 0.05, "soft_white": 0.05},
    # 暗角
    "CG_VIGNETTE_LIGHT": {"name": "轻暗角", "vignette_strength": 0.15, "vignette_radius": 0.8},
    "CG_VIGNETTE_HEAVY": {"name": "重暗角", "vignette_strength": 0.50, "vignette_radius": 0.6},
    "CG_VIGNETTE_NONE": {"name": "无暗角", "vignette_strength": 0.0, "vignette_radius": 1.0},
    # 胶片颗粒
    "CG_GRAIN_LIGHT": {"name": "轻颗粒", "grain_intensity": 0.03, "grain_size": 1.0},
    "CG_GRAIN_HEAVY": {"name": "重颗粒", "grain_intensity": 0.12, "grain_size": 2.0},
    "CG_GRAIN_NONE": {"name": "无颗粒", "grain_intensity": 0.0, "grain_size": 0},
}


# ═══════════════════════════════════════════
# PART 4.5I: 粒子系统参数库
# ═══════════════════════════════════════════

PARTICLE_SYSTEMS = {
    # 降水
    "PS_RAIN_LIGHT": {"name": "小雨", "count": 500, "speed": 8, "size_px": 1, "lifetime_s": 1.5,
                      "direction": (0, -1, 0), "spread": (10, 15, 10), "color": (180, 200, 230), "opacity": 0.6},
    "PS_RAIN_HEAVY": {"name": "暴雨", "count": 3000, "speed": 14, "size_px": 2, "lifetime_s": 0.8,
                      "direction": (0.2, -1, 0.1), "spread": (15, 20, 15), "color": (160, 190, 220), "opacity": 0.8},
    "PS_SNOW_FLURRY": {"name": "小雪", "count": 200, "speed": 1.5, "size_px": 3, "lifetime_s": 8,
                       "direction": (0.1, -0.3, 0.05), "spread": (20, 25, 15), "color": (255, 255, 255), "opacity": 0.7},
    "PS_SNOW_BLIZZARD": {"name": "暴雪", "count": 2000, "speed": 5, "size_px": 4, "lifetime_s": 4,
                         "direction": (0.3, -0.5, 0.2), "spread": (25, 30, 20), "color": (240, 245, 255), "opacity": 0.9},
    # 灰尘与雾气
    "PS_DUST_MOTE": {"name": "浮尘", "count": 100, "speed": 0.3, "size_px": 2, "lifetime_s": 10,
                     "direction": (0.05, -0.02, 0.02), "spread": (5, 8, 5), "color": (200, 190, 160), "opacity": 0.3},
    "PS_DUST_KICK": {"name": "扬尘", "count": 80, "speed": 2, "size_px": 4, "lifetime_s": 1.5,
                     "direction": (0, 0.5, 0), "spread": (2, 0.5, 2), "color": (180, 160, 130), "opacity": 0.5},
    "PS_MIST_GROUND": {"name": "低雾", "count": 50, "speed": 0.1, "size_px": 60, "lifetime_s": 20,
                       "direction": (0.02, 0, 0), "spread": (15, 2, 10), "color": (200, 210, 220), "opacity": 0.15},
    # 火花/火焰
    "PS_SPARK_SMALL": {"name": "小火花", "count": 30, "speed": 3, "size_px": 2, "lifetime_s": 0.5,
                       "direction": (0.2, 1, 0.2), "spread": (0.3, 0.3, 0.3), "color": (255, 200, 50), "opacity": 1.0},
    "PS_FIRE_SMALL": {"name": "小火", "count": 100, "speed": 1, "size_px": 8, "lifetime_s": 1.2,
                      "direction": (0, 1.5, 0), "spread": (0.5, 0.5, 0.5), "color": (255, 120, 20), "opacity": 0.8},
    "PS_FIRE_LARGE": {"name": "大火", "count": 500, "speed": 3, "size_px": 15, "lifetime_s": 0.8,
                      "direction": (0.1, 2, 0.1), "spread": (2, 1, 2), "color": (255, 80, 10), "opacity": 0.9},
    "PS_EMBER_DRIFT": {"name": "飘烬", "count": 40, "speed": 0.8, "size_px": 3, "lifetime_s": 4,
                       "direction": (0.1, 0.3, 0.1), "spread": (8, 5, 8), "color": (255, 100, 30), "opacity": 0.6},
    # 气泡
    "PS_BUBBLES_SLOW": {"name": "缓慢气泡", "count": 20, "speed": 0.5, "size_px": 5, "lifetime_s": 6,
                        "direction": (0.1, 0.8, 0.05), "spread": (3, 1, 3), "color": (200, 230, 255), "opacity": 0.4},
    # 魔法粒子
    "PS_MAGIC_GLOW": {"name": "魔法光点", "count": 60, "speed": 0.6, "size_px": 3, "lifetime_s": 3,
                      "direction": (0, 0.2, 0), "spread": (4, 4, 4), "color": (180, 200, 255), "opacity": 0.7},
    "PS_LEAVES_FALL": {"name": "落叶", "count": 30, "speed": 1.5, "size_px": 6, "lifetime_s": 5,
                       "direction": (0.3, -0.5, 0.1), "spread": (10, 8, 8), "color": (180, 140, 60), "opacity": 0.8},
}


# ═══════════════════════════════════════════
# PART 4.5J: 角色动作库
# ═══════════════════════════════════════════

CHARACTER_ACTIONS = {
    # 基础位移
    "CA_WALK_SLOW": {"name": "慢走", "duration_s": 3.0, "cycles": 1, "speed_mps": 1.0,
                     "ik_targets": ["hip", "knee_L", "ankle_L", "knee_R", "ankle_R"],
                     "body_tilt_deg": 3, "arm_swing_amp": 0.3, "bounce_mm": 20},
    "CA_WALK_NORMAL": {"name": "常速走", "duration_s": 2.0, "cycles": 1, "speed_mps": 1.5,
                       "ik_targets": ["hip", "knee_L", "ankle_L", "knee_R", "ankle_R"],
                       "body_tilt_deg": 5, "arm_swing_amp": 0.5, "bounce_mm": 35},
    "CA_WALK_FAST": {"name": "快走", "duration_s": 1.5, "cycles": 1, "speed_mps": 2.2,
                     "ik_targets": ["hip", "knee_L", "ankle_L", "knee_R", "ankle_R"],
                     "body_tilt_deg": 10, "arm_swing_amp": 0.7, "bounce_mm": 50},
    "CA_RUN": {"name": "跑步", "duration_s": 0.8, "cycles": 1, "speed_mps": 5.0,
               "ik_targets": ["hip", "knee_L", "ankle_L", "knee_R", "ankle_R"],
               "body_tilt_deg": 20, "arm_swing_amp": 0.9, "bounce_mm": 80, "air_time": 0.15},
    "CA_SPRINT": {"name": "冲刺", "duration_s": 0.5, "cycles": 1, "speed_mps": 8.0,
                  "ik_targets": ["hip", "knee_L", "ankle_L", "knee_R", "ankle_R"],
                  "body_tilt_deg": 30, "arm_swing_amp": 1.0, "bounce_mm": 120, "air_time": 0.25},
    # 转向
    "CA_TURN_45L": {"name": "左转45", "duration_s": 0.5, "rotation_deg": -45,
                    "weight_shift": "left_foot", "body_lean": 5},
    "CA_TURN_45R": {"name": "右转45", "duration_s": 0.5, "rotation_deg": 45,
                    "weight_shift": "right_foot", "body_lean": -5},
    "CA_TURN_180": {"name": "转身180", "duration_s": 1.2, "rotation_deg": 180,
                    "steps": 3, "body_lean": 0},
    # 姿态
    "CA_STAND_IDLE": {"name": "站立", "duration_s": 2.0, "loops": True,
                      "weight_distribution": "both_feet", "sway_mm": 5, "breath_cycle_s": 4},
    "CA_SIT_DOWN": {"name": "坐下", "duration_s": 1.5, "transition": True,
                    "phases": ["bend_knees", "lower_hips", "settle"], "hip_drop_mm": 400},
    "CA_SIT_IDLE": {"name": "坐着", "duration_s": 2.0, "loops": True,
                    "weight_distribution": "seat", "sway_mm": 2, "slouch_pct": 0.1},
    "CA_STAND_UP": {"name": "站起", "duration_s": 1.5, "transition": True,
                    "phases": ["lean_forward", "push_up", "steady"], "hip_rise_mm": 400},
    "CA_CROUCH": {"name": "蹲下", "duration_s": 1.0, "transition": True,
                  "hip_drop_mm": 350, "knee_bend_deg": 120, "heel_lift_mm": 30},
    # 头部
    "CA_HEAD_NOD": {"name": "点头", "duration_s": 0.4, "cycles": 1,
                    "rotation_deg": [-15, 0], "axis": "pitch", "neck_bend": True},
    "CA_HEAD_SHAKE": {"name": "摇头", "duration_s": 0.6, "cycles": 2,
                      "rotation_deg": [-15, 15], "axis": "yaw"},
    "CA_HEAD_TILT": {"name": "歪头", "duration_s": 0.3, "rotation_deg": 15, "axis": "roll"},
    # 上肢
    "CA_ARM_RAISE_R": {"name": "右手抬起", "duration_s": 0.8, "target_deg": {"shoulder_R": 90, "elbow_R": 10},
                       "arc": "front_plane", "ease": "ease_out"},
    "CA_ARM_LOWER_R": {"name": "右手放下", "duration_s": 0.6, "target_deg": {"shoulder_R": 0, "elbow_R": 0},
                       "arc": "front_plane", "ease": "ease_in"},
    "CA_WAVE": {"name": "挥手", "duration_s": 1.5, "cycles": 2,
                "target_deg": {"shoulder_R": 80, "elbow_R": 20}, "arc": "side_plane"},
    "CA_CLAP": {"name": "拍手", "duration_s": 0.4, "cycles": 1,
                "hands_meet": True, "contact_frame": 10, "recoil_mm": 50},
    "CA_POINT": {"name": "指向", "duration_s": 0.6, "hold_s": 2.0,
                 "target_deg": {"shoulder_R": 75, "elbow_R": 5}, "finger_extend": "index"},
    # 全身
    "CA_JUMP": {"name": "跳跃", "duration_s": 1.0, "phases": ["crouch", "launch", "air", "land"],
               "apex_mm": 300, "air_time_s": 0.3, "landing_knee_bend": 40},
    "CA_FALL": {"name": "摔倒", "duration_s": 0.8, "direction": "forward",
               "phases": ["lose_balance", "fall", "impact"], "ground_contact": ["hands", "knees"]},
    "CA_STRETCH": {"name": "伸懒腰", "duration_s": 2.0, "phases": ["extend", "hold", "release"],
                   "arm_reach_mm": 800, "back_arch_deg": 15, "yawn": True},
}

# 动作融合
ACTION_BLEND = {
    "AB_LINEAR": {"name": "线性混合", "duration_s": 0.2, "curve": "linear"},
    "AB_EASE": {"name": "缓动混合", "duration_s": 0.4, "curve": "ease_in_out"},
    "AB_STEP": {"name": "步进", "duration_s": 0.0, "curve": "none", "snap": True},
}


# ═══════════════════════════════════════════
# PART 4.5K: 输出格式映射
# ═══════════════════════════════════════════

OUTPUT_FORMATS = {
    # Seedance 2.0
    "OUT_SEEDANCE": {
        "api": "seedance_2.0",
        "field_map": {
            "shots": {"path": "timeline.shots", "format": "array"},
            "scene_terrain": {"path": "shot.scene.terrain", "from": "SCENE_TERRAIN", "join": ","},
            "camera_preset": {"path": "shot.camera.preset", "from": "CAMERA_PRESETS", "extract": "fov"},
            "camera_movement": {"path": "shot.camera.movement", "from": "CAMERA_MOVEMENT", "extract": "type"},
            "light_source": {"path": "shot.lighting.source", "from": "SCENE_LIGHTING"},
            "character_emotion": {"path": "shot.characters[].emotion", "from": "EMOTION_PROFILE"},
            "facs_units": {"path": "shot.characters[].facs", "from": "FACS_UNITS"},
            "color_palette": {"path": "shot.grading.palette", "from": "COLOR_PALETTES"},
            "particle_system": {"path": "shot.particles", "from": "PARTICLE_SYSTEMS"},
            "action_sequence": {"path": "shot.characters[].actions", "from": "CHARACTER_ACTIONS"},
            "audio_ambient": {"path": "shot.audio.ambient", "from": "AMBIENT_SOUNDS"},
        },
        "required": ["shots", "total_frames", "fps"],
        "resolution_native": [1920, 1080],
        "fps_supported": [24, 30, 60],
    },
    # ComfyUI
    "OUT_COMFYUI": {
        "api": "comfyui_workflow",
        "field_map": {
            "positive_prompt": {"build": "concat", "from": ["shot.description", "scene.weather", "lighting", "color_palette.mood"]},
            "negative_prompt": {"default": "blurry, distorted, bad anatomy, watermark"},
            "steps": {"from": "quality.sampling_steps", "default": 30},
            "cfg": {"from": "quality.cfg_scale", "default": 7},
            "resolution": {"path": "quality.resolution", "default": [1920, 1080]},
            "seed": {"generate": "random"},
            "control_net": {"path": "shot.camera", "type": "depth_or_pose"},
        },
        "nodes": ["LoadCheckpoint", "CLIPTextEncode", "KSampler", "VAEDecode", "SaveImage"],
    },
    # RenderNet
    "OUT_RENDERNET": {
        "api": "rendernet_api_v1",
        "field_map": {
            "scene": {"path": "shot.scene", "format": "render_scene"},
            "camera": {"path": "shot.camera", "format": "render_camera"},
            "characters": {"path": "shot.characters", "format": "render_avatar"},
            "lighting": {"path": "shot.lighting", "format": "render_light"},
            "environment": {"path": "shot.grading", "format": "render_post"},
            "animation": {"path": "shot.characters[].actions", "format": "render_animation"},
        },
        "supported_formats": ["mp4", "exr", "png_sequence"],
        "render_engine": ["cycles", "eevee"],
    },
    # 本地概念引擎输出
    "OUT_CONCEPT_ENGINE": {
        "api": "internal_v3",
        "field_map": {},  # 全量内部
        "output": "serialized_frame_array",
        "purpose": "feed to rendering pipeline or store as concept memory",
    },
}


# ═══════════════════════════════════════════
# PART 5: 音频参数库
# ═══════════════════════════════════════════

VOICE_PRESETS = {
    "VX_MALE_DEEP": {"name": "男低音", "pitch_base": 100, "timbre": "deep", "age_group": "adult"},
    "VX_MALE_MID": {"name": "男中音", "pitch_base": 150, "timbre": "warm", "age_group": "adult"},
    "VX_MALE_HIGH": {"name": "男高音", "pitch_base": 200, "timbre": "bright", "age_group": "young"},
    "VX_FEMALE_MID": {"name": "女中音", "pitch_base": 220, "timbre": "clear", "age_group": "adult"},
    "VX_FEMALE_HIGH": {"name": "女高音", "pitch_base": 280, "timbre": "light", "age_group": "young"},
    "VX_CHILD": {"name": "童声", "pitch_base": 300, "timbre": "pure", "age_group": "child"},
    "VX_ELDER": {"name": "老年", "pitch_base": 130, "timbre": "raspy", "age_group": "elder"},
}

VOICE_EMOTION = {
    "VE_NEUTRAL": {"name": "正常", "pitch_shift": 0, "speed_factor": 1.0, "breath": 0.1, "tremolo": 0},
    "VE_WARM": {"name": "温暖", "pitch_shift": 0.05, "speed_factor": 0.9, "breath": 0.2, "tremolo": 0.1},
    "VE_CRY": {"name": "哭腔", "pitch_shift": -0.1, "speed_factor": 0.7, "breath": 0.5, "tremolo": 0.3},
    "VE_LAUGH": {"name": "笑意", "pitch_shift": 0.1, "speed_factor": 1.1, "breath": 0.3, "tremolo": 0.2},
    "VE_ANGRY": {"name": "愤怒", "pitch_shift": -0.2, "speed_factor": 1.3, "breath": 0.4, "tremolo": 0.1},
    "VE_WHISPER": {"name": "气声", "pitch_shift": 0, "speed_factor": 0.8, "breath": 0.8, "tremolo": 0},
}

AMBIENT_SOUNDS = {
    "AMB_RIVER": {"name": "流水声", "volume": -15, "loop": True, "fade_in_s": 2},
    "AMB_WIND": {"name": "风声", "volume": -20, "loop": True, "fade_in_s": 1},
    "AMB_RAIN": {"name": "雨声", "volume": -12, "loop": True, "fade_in_s": 3},
    "AMB_BIRDS": {"name": "鸟鸣", "volume": -25, "loop": True, "fade_in_s": 1},
    "AMB_THUNDER": {"name": "雷声", "volume": -5, "loop": False, "duration_s": 3},
    "AMB_WAVES": {"name": "海浪声", "volume": -10, "loop": True, "fade_in_s": 2},
}

SFX_LIBRARY = {
    "SFX_FOOTSTEP": {"name": "脚步声", "volume": -18, "trigger": "character_move", "pitch_vary": 0.1},
    "SFX_CLOTH": {"name": "衣物摩擦", "volume": -30, "trigger": "character_move", "pitch_vary": 0.05},
    "SFX_ROCK": {"name": "石块碰撞", "volume": -12, "trigger": "object_collide"},
    "SFX_SWOOSH": {"name": "破空音", "volume": -8, "trigger": "fast_move", "pitch_vary": 0.2},
    "SFX_IMPACT": {"name": "冲击音", "volume": -6, "trigger": "impact", "pitch_vary": 0.15},
}


# ═══════════════════════════════════════════
# PART 5.5A: 音频合成引擎
# ═══════════════════════════════════════════

AUDIO_SYNTH = {
    # 合成器基础波形
    "AS_SINE": {"name": "正弦波", "harmonics": [1], "amps": [1.0], "timbre": "pure"},
    "AS_TRIANGLE": {"name": "三角波", "harmonics": [1, 3, 5, 7], "amps": [1.0, 0.11, 0.04, 0.02], "timbre": "soft"},
    "AS_SQUARE": {"name": "方波", "harmonics": [1, 3, 5, 7, 9], "amps": [1.0, 0.33, 0.2, 0.14, 0.11], "timbre": "hollow"},
    "AS_SAWTOOTH": {"name": "锯齿波", "harmonics": [1, 2, 3, 4, 5, 6], "amps": [1.0, 0.5, 0.33, 0.25, 0.2, 0.17], "timbre": "bright"},
    "AS_NOISE_WHITE": {"name": "白噪声", "noise_type": "uniform", "range": [-1, 1], "use": "wind_wave_breath"},
    "AS_NOISE_PINK": {"name": "粉噪声", "noise_type": "1/f", "range": [-0.7, 0.7], "use": "rain_fire_nature"},
    "AS_NOISE_BROWN": {"name": "布朗噪声", "noise_type": "brownian", "range": [-0.5, 0.5], "use": "thunder_rumble"},
}

ENVELOPE_PRESETS = {
    "ENV_PERCUSSIVE": {"name": "打击", "attack_s": 0.002, "decay_s": 0.3, "sustain": 0.0, "release_s": 0.1,
                        "curve": "exponential"},
    "ENV_PLUCK": {"name": "拨弦", "attack_s": 0.005, "decay_s": 0.8, "sustain": 0.0, "release_s": 0.05,
                 "curve": "exponential"},
    "ENV_PAD": {"name": "铺底", "attack_s": 0.3, "decay_s": 0.2, "sustain": 0.8, "release_s": 1.5,
               "curve": "linear"},
    "ENV_STAB": {"name": "刺音", "attack_s": 0.001, "decay_s": 0.05, "sustain": 0.0, "release_s": 0.01,
                 "curve": "exponential"},
    "ENV_SWELL": {"name": "渐强", "attack_s": 2.0, "decay_s": 0.5, "sustain": 0.6, "release_s": 3.0,
                 "curve": "sigmoid"},
}

MIXER_BAKER = {
    # 混音规则
    "MX_LAYER": {"name": "叠加", "method": "sum", "normalize": True, "headroom_db": -3},
    "MX_CROSSFADE": {"name": "交叉淡入", "method": "crossfade", "fade_ms": 50, "curve": "equal_power"},
    "MX_DUCK": {"name": "闪避", "method": "sidechain", "trigger": "dialogue", "duck_db": -12, "attack_ms": 5, "release_ms": 200},
    "MX_SPATIAL": {"name": "空间化", "method": "pan", "positions": {"center": 0, "left": -1, "right": 1, "rear": ["reverb", -0.5]}},
}

# TTS 与 情绪联动
TTS_EMOTION_MAP = {
    "joy": {"pitch_shift_semitones": 2, "speed": 1.1, "energy": 1.2, "breathiness": 0.1},
    "anger": {"pitch_shift_semitones": -3, "speed": 1.3, "energy": 1.5, "breathiness": 0.2},
    "sadness": {"pitch_shift_semitones": -1, "speed": 0.7, "energy": 0.4, "breathiness": 0.4},
    "fear": {"pitch_shift_semitones": 4, "speed": 1.4, "energy": 1.3, "breathiness": 0.5},
    "calm": {"pitch_shift_semitones": 0, "speed": 1.0, "energy": 0.6, "breathiness": 0.1},
    "tender": {"pitch_shift_semitones": 1, "speed": 0.85, "energy": 0.5, "breathiness": 0.3},
    "surprise": {"pitch_shift_semitones": 3, "speed": 1.2, "energy": 1.4, "breathiness": 0.2},
    "disgust": {"pitch_shift_semitones": -2, "speed": 1.0, "energy": 0.8, "breathiness": 0.15},
    "suspicious": {"pitch_shift_semitones": -1, "speed": 0.9, "energy": 0.5, "breathiness": 0.2},
    "tired": {"pitch_shift_semitones": -2, "speed": 0.6, "energy": 0.3, "breathiness": 0.5},
}

# 环境音合成
AMBIENT_GENERATORS = {
    "AG_WIND": {"source": "AS_NOISE_PINK", "filter": "bandpass_200_2000hz", "modulation": "slow_lfo_0.2hz",
               "volume_range_db": [-30, -15]},
    "AG_RAIN": {"source": "AS_NOISE_PINK + AS_NOISE_WHITE", "filter": "lowpass_5000hz",
               "granular": {"grain_ms": 30, "density": 50, "spread": 0.8}},
    "AG_THUNDER": {"source": "AS_NOISE_BROWN", "filter": "lowpass_200hz",
                   "envelope": "ENV_PERUSSIVE", "rumble_tail_s": 3.0},
    "AG_FIRE": {"source": "AS_NOISE_PINK", "filter": "bandpass_300_3000hz",
               "crackle": {"rate": 15, "intensity": 0.3, "envelope": "ENV_STAB"}},
    "AG_STREAM": {"source": "AS_NOISE_WHITE", "filter": "bandpass_500_4000hz",
                  "modulation": "multi_lfo", "lfo_rates": [0.8, 1.3, 2.1]},
    "AG_BIRDS": {"source": "AS_SINE", "filter": "bandpass_2000_8000hz",
                 "chirp": {"pattern": "random_interval", "interval_s": [0.5, 3.0],
                           "pitch_bend": {"start_semi": 0, "end_semi": 3, "duration_ms": 100}}},
}

# 音效合成
SFX_GENERATORS = {
    "SFXG_FOOTSTEP": {"source": "AS_NOISE_PINK", "filter": "lowpass_800hz",
                      "envelope": "ENV_PERCUSSIVE", "pitch_vary_semi": 2},
    "SFXG_IMPACT": {"source": "AS_NOISE_BROWN + AS_SINE_80hz", "filter": "lowpass_300hz",
                    "envelope": "ENV_PERCUSSIVE", "sub_bass_boost_db": 6},
    "SFXG_SWOOSH": {"source": "AS_NOISE_WHITE", "filter": "bandpass_1000_8000hz_sweep_down",
                    "envelope": "ENV_SWELL", "duration_s": 0.3},
    "SFXG_CLOTH": {"source": "AS_NOISE_PINK", "filter": "highpass_500hz",
                   "envelope": "ENV_PERCUSSIVE", "volume_db": -35},
    "SFXG_SPARK": {"source": "AS_NOISE_WHITE", "filter": "highpass_6000hz",
                   "envelope": "ENV_STAB", "ring_mod_hz": 4000},
}


# ═══════════════════════════════════════════
# PART 5.5B: 安全水印/指纹引擎
# ═══════════════════════════════════════════

WATERMARK_METHODS = {
    # 视觉水印
    "WM_VISIBLE_CORNER": {"name": "角标水印", "type": "visible", "position": "bottom_right",
                          "opacity": 0.4, "size_pct": 5, "text": "YUGE_V3"},
    "WM_VISIBLE_BADGE": {"name": "徽章水印", "type": "visible", "position": "top_left",
                         "opacity": 0.3, "size_pct": 8, "icon": "blackhole_emblem"},
    # 隐写水印
    "WM_DCT_COEFF": {"name": "DCT系数隐写", "type": "invisible", "domain": "frequency",
                     "method": "dct_mid_band", "capacity_bits": 256, "robustness": "high",
                     "payload": {"creator": "yinxin_yin", "engine": "v3_achilles", "timestamp": "auto"}},
    "WM_LSB_SPREAD": {"name": "LSB扩频", "type": "invisible", "domain": "spatial",
                      "method": "lsb_spread_spectrum", "capacity_bits": 128, "robustness": "medium"},
    "WM_DEEP_SIGN": {"name": "深度签名", "type": "invisible", "domain": "neural",
                     "method": "hi_dimensional_embedding", "capacity_bits": 2048,
                     "payload": {"version": "v3", "date": "auto", "hash": "sha256_of_frame"}},
    # 指纹
    "FP_PERCEPTUAL": {"name": "感知哈希指纹", "type": "fingerprint",
                      "algorithms": ["pHash", "dHash", "wHash"], "purpose": "leak_tracing"},
    "FP_FEATURE_POINTS": {"name": "特征点指纹", "type": "fingerprint",
                          "algorithm": "SIFT_descriptor_hash", "purpose": "derivative_detection"},
}

IDENTITY_SIGNATURE = {
    "creator": "殷竺欣 (Yinxin Yin)",
    "engine": "v3 Achilles 全链路创作引擎",
    "theory": "黑洞理论 (Blackhole Theory v3)",
    "philosophy": "万物死·马赛克 — 死色块×时间驱动 = 活的宇宙",
    "copyright": "All Rights Reserved. 殷竺欣独有原创知识产权",
    "hash_algorithm": "SHA-256",
    "timestamp_format": "ISO8601_Asia/Shanghai",
}

LICENSE_PRESETS = {
    "LIC_PROPRIETARY": {"name": "独占", "allow_inspect": False, "allow_modify": False,
                        "allow_redistribute": False, "must_credit": True},
    "LIC_RESEARCH": {"name": "研究", "allow_inspect": True, "allow_modify": True,
                     "allow_redistribute": False, "must_credit": True, "scope": "academic_only"},
    "LIC_SHOWCASE": {"name": "展示", "allow_inspect": False, "allow_modify": False,
                     "allow_redistribute": True, "must_credit": True, "scope": "portfolio_presentation"},
}

PROVENANCE_CHAIN = {
    # 产出溯源码链：每帧/每个文件都有创作路径
    "PC_CREATION": {"name": "创作溯源",
                    "record": ["prompt", "story_structure", "shot_script", "parameters", "frame_output"],
                    "verification": "parent_hash_chain"},
    "PC_MODIFICATION": {"name": "修改溯源",
                       "record": ["base_file_hash", "modification_description", "new_file_hash"],
                       "immutable": True},
}


# ═══════════════════════════════════════════
# PART 5.5C: 口型-语音同步映射
# ═══════════════════════════════════════════

# 音素 → 口型 映射 (国际音标IPA → achilles口型码)
PHONEME_TO_MOUTH = {
    # 元音
    "a": "M_WIDE", "\u0251": "M_WIDE",  # /a/ /ɑ/ 大开
    "e": "M_SEMI_WIDE", "\u025b": "M_SEMI_WIDE",  # /e/ /ɛ/ 半开
    "i": "M_STRETCHED",  # /i/ 横拉
    "o": "M_ROUND", "\u0254": "M_ROUND",  # /o/ /ɔ/ 圆唇
    "u": "M_TIGHT",  # /u/ 紧收
    "\u0259": "M_SLIGHT",  # /ə/ 微开
    # 双元音
    "ai": "M_WIDE", "ei": "M_SEMI_WIDE", "ao": "M_ROUND", "ou": "M_TIGHT",
    # 辅音 — 双唇
    "p": "M_CLOSED", "b": "M_CLOSED", "m": "M_CLOSED",
    # 辅音 — 唇齿
    "f": "M_TEETH_LIP", "v": "M_TEETH_LIP",
    # 辅音 — 齿龈
    "t": "M_SLIGHT", "d": "M_SLIGHT", "n": "M_SLIGHT", "l": "M_SLIGHT",
    "s": "M_TEETH", "z": "M_TEETH",
    # 辅音 — 翘舌
    "\u0282": "M_ROUND_OPEN", "\u0290": "M_ROUND_OPEN", "\u0288\u0282": "M_ROUND_OPEN", "\u0288\u0290": "M_ROUND_OPEN",
    # 辅音 — 软腭
    "k": "M_HALF", "g": "M_HALF", "\u014b": "M_HALF", "x": "M_HALF",
    # 辅音 — 硬腭
    "t\u0255": "M_STRETCHED", "t\u0255\u02b0": "M_STRETCHED", "\u0255": "M_STRETCHED",
    # 特殊
    "sil": "M_CLOSED",  # 静音 = 闭嘴
    "sp": "M_SLIGHT",  # 短停顿
}

# 中文拼音 → 音素/口型
PINYIN_TO_MOUTH = {
    "a": "M_WIDE", "o": "M_ROUND", "e": "M_SEMI_WIDE",
    "i": "M_STRETCHED", "u": "M_TIGHT", "v": "M_TIGHT",
    "ai": "M_WIDE", "ei": "M_SEMI_WIDE", "ao": "M_ROUND", "ou": "M_TIGHT",
    "an": "M_WIDE", "en": "M_SEMI_WIDE", "ang": "M_WIDE", "eng": "M_SEMI_WIDE",
    "b": "M_CLOSED", "p": "M_CLOSED", "m": "M_CLOSED",
    "f": "M_TEETH_LIP",
    "d": "M_SLIGHT", "t": "M_SLIGHT", "n": "M_SLIGHT", "l": "M_SLIGHT",
    "g": "M_HALF", "k": "M_HALF", "h": "M_HALF",
    "j": "M_STRETCHED", "q": "M_STRETCHED", "x": "M_STRETCHED",
    "zh": "M_ROUND_OPEN", "ch": "M_ROUND_OPEN", "sh": "M_ROUND_OPEN", "r": "M_ROUND_OPEN",
    "z": "M_TEETH", "c": "M_TEETH", "s": "M_TEETH",
}

# 口型过渡曲线
MOUTH_TRANSITION = {
    "MT_STEP": {"name": "阶梯", "interp_ms": 0, "style": "abrupt", "use": "fast_cuts"},
    "MT_LINEAR": {"name": "线性", "interp_ms": 40, "style": "mechanical", "use": "robotic_voice"},
    "MT_SMOOTH": {"name": "平滑", "interp_ms": 80, "style": "natural", "use": "normal_dialogue"},
    "MT_EXPRESSIVE": {"name": "表情化", "interp_ms": 120, "style": "emotional", "use": "emotional_scenes"},
}

# 语音到口型的完整时间线
class LipSyncTrack:
    """口型同步轨：timestamps → mouth shapes → FACS blend"""

    @staticmethod
    def from_text_and_timestamps(text, timestamps_ms, method="pinyin"):
        """输入文本+每个字的时间戳，输出口型序列

        timestamps_ms: [(start_ms, end_ms), ...] 每个字/音素的起止时间
        """
        track = []
        for i, (start, end) in enumerate(timestamps_ms):
            duration = end - start
            # 查找口型
            if method == "pinyin" and i < len(text):
                # 简化：按拼音首字母匹配
                mouth = PINYIN_TO_MOUTH.get(text[i].lower() if text[i].isalpha() else "a", "M_SLIGHT")
            else:
                mouth = "M_SLIGHT"

            track.append({
                "frame_range": (int(start * 24 / 1000), int(end * 24 / 1000)),
                "mouth": mouth,
                "duration_frames": int(duration * 24 / 1000),
                "open_mm": MOUTH_OPEN_MM.get(mouth, 2),
            })
        return track

# 口型张开幅度映射 (mm)
MOUTH_OPEN_MM = {
    "M_CLOSED": 0, "M_SLIGHT": 2, "M_SEMI_WIDE": 6,
    "M_HALF": 8, "M_WIDE": 10, "M_ROUND": 5,
    "M_TIGHT": 2, "M_STRETCHED": 3, "M_TEETH_LIP": 1,
    "M_TEETH": 3, "M_ROUND_OPEN": 6,
}


# ═══════════════════════════════════════════
# PART 5.5D: 耳→脑直通管道
# ═══════════════════════════════════════════

LISTEN_PIPELINE = {
    # 麦克风配置
    "LP_MIC": {"device": "default", "sample_rate": 16000, "channels": 1,
               "chunk_ms": 200, "format": "int16", "gain": 1.0},
    # VAD 语音活动检测
    "LP_VAD": {"method": "energy_threshold", "silence_db": -40, "min_speech_ms": 300,
               "max_silence_ms": 800, "padding_ms": 200},
    # ASR 识别引擎
    "LP_ASR": {"engine": "whisper_local", "model": "base", "language": "zh",
               "beam_size": 5, "temperature": 0.0, "real_time_factor": "<1.0"},
    # 情绪识别
    "LP_EMOTION": {"source": "audio_features",
                   "features": ["pitch_mean", "pitch_range", "energy", "speech_rate", "spectral_centroid"],
                   "classifier": "rule_based",
                   "output": "EMOTION_PROFILE_key"},
    # 说话人识别
    "LP_SPEAKER": {"method": "voice_embedding", "model": "ecapa_tdnn_small",
                   "registered": ["yinxin"], "unknown": "prompt_for_enrollment"},
}

# 耳→v3脑 处理链
EAR_TO_BRAIN_CHAIN = [
    {"stage": 1, "name": "listen", "action": "capture_audio_chunk", "output": "raw_pcm"},
    {"stage": 2, "name": "vad", "action": "detect_speech", "output": "speech_segments"},
    {"stage": 3, "name": "transcribe", "action": "whisper_asr", "output": "text"},
    {"stage": 4, "name": "parse", "action": "extract_intent", "output": "intent_with_params"},
    {"stage": 5, "name": "route", "action": "v3_concept_route", "output": "response_plan"},
    {"stage": 6, "name": "speak", "action": "tts_with_emotion", "output": "audio_response"},
]

INTERRUPT_HANDLING = {
    "IH_BARGE_IN": {"name": "打断", "trigger": "user_speech_during_tts",
                    "action": "fade_out_current_audio_ms_200_then_listen"},
    "IH_TURN_TAKING": {"name": "轮次", "trigger": "long_pause_500ms",
                       "action": "assume_turn_complete", "max_turn_gap_ms": 1500},
    "IH_OVERLAP": {"name": "重叠", "trigger": "both_speaking",
                   "action": "yield_to_user_mute_self"},
}


# ═══════════════════════════════════════════
# PART 5.5E: 物理引擎参数库
# ═══════════════════════════════════════════

GRAVITY_PRESETS = {
    "GRAV_EARTH": {"name": "地球", "g_mps2": 9.8, "terminal_velocity_ms": 53,
                   "air_density": 1.225, "description": "normal"},
    "GRAV_MOON": {"name": "月球", "g_mps2": 1.62, "terminal_velocity_ms": 200,
                  "air_density": 0, "description": "floaty"},
    "GRAV_SPACE": {"name": "太空", "g_mps2": 0.0, "terminal_velocity_ms": None,
                   "air_density": 0, "description": "weightless"},
    "GRAV_HEAVY": {"name": "超重", "g_mps2": 19.6, "terminal_velocity_ms": 30,
                   "air_density": 2.0, "description": "crushing"},
}

COLLISION_MATERIALS = {
    "CM_SOFT_FLESH": {"name": "软组织", "restitution": 0.1, "friction": 0.8,
                      "deform_mm": 15, "sound": "dull_thud"},
    "CM_HARD_BONE": {"name": "骨骼", "restitution": 0.3, "friction": 0.4,
                     "deform_mm": 0.5, "sound": "click"},
    "CM_METAL": {"name": "金属", "restitution": 0.6, "friction": 0.3,
                 "deform_mm": 0, "sound": "clang", "spark": True},
    "CM_WOOD": {"name": "木材", "restitution": 0.2, "friction": 0.6,
                "deform_mm": 2, "sound": "thud", "splinter": True},
    "CM_STONE": {"name": "石材", "restitution": 0.05, "friction": 0.7,
                 "deform_mm": 0, "sound": "crunch"},
    "CM_FABRIC": {"name": "布料", "restitution": 0.0, "friction": 0.5,
                  "deform_mm": 30, "sound": "rustle", "fold": True},
    "CM_WATER": {"name": "水面", "restitution": 0.0, "friction": 0.01,
                 "deform_mm": 100, "sound": "splash", "ripple_radius_mm": 200},
    "CM_GROUND": {"name": "地面", "restitution": 0.0, "friction": 0.9,
                  "deform_mm": 0, "sound": "thud", "footstep_type": "FG_STONE"},
}

CONSTRAINT_TYPES = {
    "CT_HINGE": {"name": "铰链", "dof": ["rotation_1_axis"], "limits": {"min_deg": -180, "max_deg": 180},
                 "use": "elbow_knee_door"},
    "CT_BALL": {"name": "球窝", "dof": ["rotation_3_axes"], "limits": {"cone_deg": 120},
               "use": "shoulder_hip"},
    "CT_SLIDER": {"name": "滑动", "dof": ["translation_1_axis"], "limits": {"min_mm": 0, "max_mm": 100},
                 "use": "drawer_telescope"},
    "CT_FIXED": {"name": "固定", "dof": [], "use": "weld_glue"},
    "CT_SPRING": {"name": "弹簧", "dof": ["translation_1_axis"],
                  "params": {"stiffness_npm": 100, "damping": 10, "rest_mm": 0}},
}

# 布料物理
CLOTH_SIM_PRESETS = {
    "CS_SILK": {"name": "丝绸", "bend_stiffness": 0.01, "stretch_stiffness": 0.5,
                "mass_per_vertex": 0.1, "damping": 0.02, "self_collision": True,
                "wind_response": 0.9, "fold_crease_angle": 30},
    "CS_COTTON": {"name": "棉布", "bend_stiffness": 0.05, "stretch_stiffness": 0.8,
                 "mass_per_vertex": 0.2, "damping": 0.05, "self_collision": True,
                 "wind_response": 0.5, "fold_crease_angle": 45},
    "CS_DENIM": {"name": "牛仔", "bend_stiffness": 0.15, "stretch_stiffness": 0.95,
                "mass_per_vertex": 0.3, "damping": 0.08, "self_collision": False,
                "wind_response": 0.1, "fold_crease_angle": 60},
    "CS_LEATHER": {"name": "皮革", "bend_stiffness": 0.3, "stretch_stiffness": 0.99,
                   "mass_per_vertex": 0.25, "damping": 0.1, "self_collision": False,
                   "wind_response": 0.05, "fold_crease_angle": 80},
}

# 粒子-环境交互
PARTICLE_PHYSICS = {
    "PP_RAIN_DROP": {"name": "雨滴物理", "mass_g": 0.05, "drag": 0.99,
                     "collision": "ground_splash", "splash_particles": 5},
    "PP_SNOW_FLAKE": {"name": "雪花物理", "mass_g": 0.001, "drag": 0.7,
                      "wind_sway": 0.4, "melt_on_collision": True},
    "PP_DUST_SETTLE": {"name": "尘埃沉降", "mass_g": 0.0001, "drag": 0.95,
                       "brownian_motion": 0.1, "settle_time_s": 30},
    "PP_SPARK_FADE": {"name": "火花衰减", "mass_g": 0.01, "drag": 0.8,
                      "temperature_decay": 0.95, "life_by_temp": True},
}


# ═══════════════════════════════════════════
# PART 5.5F: 多输出调度引擎
# ═══════════════════════════════════════════

RENDER_QUEUE = {
    # 渲染队列管理
    "RQ_PRIORITY": {"levels": ["urgent", "high", "normal", "batch"],
                    "max_concurrent": 2, "timeout_minutes": 30},
    "RQ_CHUNK": {"max_frames_per_chunk": 120, "chunk_overlap": 5,
                 "checkpoint_every": 30},
    "RQ_RETRY": {"max_retries": 3, "backoff_factor": 2.0, "backoff_base_s": 10},
}

SCHEDULER_PIPELINE = {
    # 多引擎调度
    "SP_COMFYUI": {"address": "localhost:8188", "ws_protocol": True,
                   "queue_mode": "prompt", "history_ttl_h": 24},
    "SP_SEEDANCE": {"endpoint": "api.seedance.io/v2", "auth": "api_key",
                    "poll_interval_s": 5, "max_wait_minutes": 10},
    "SP_RENDERNET": {"endpoint": "api.rendernet.ai/v1", "auth": "api_key",
                     "format": "json", "async": True},
    "SP_LOCAL": {"engine": "concept_render", "device": "cuda", "vr_budget_gb": 10,
                 "tile_size": 512, "upscale": "lanczos"},
}

# 帧→工作流 转换
FRAME_TO_WORKFLOW = {
    "FTW_DIRECT": {"name": "直转", "method": "parameter_map",
                   "output": "comfyui_prompt_json"},
    "FTW_BATCH": {"name": "批处理", "method": "keyframe_interpolation",
                  "output": "batch_prompts"},
    "FTW_STREAM": {"name": "流式", "method": "continuous_pipe",
                   "output": "websocket_events"},
}

# 渲染校验
RENDER_VALIDATION = {
    "RV_RESOLUTION": {"check": "resolution_match", "tolerance_px": 2},
    "RV_COLOR_RANGE": {"check": "no_clipping", "warn_at": 0.02, "reject_at": 0.1},
    "RV_FRAME_COUNT": {"check": "frame_count_match", "skip_ok": 0, "skip_reject": 3},
    "RV_WATERMARK": {"check": "watermark_present", "required": True},
    "RV_BLACK_FRAME": {"check": "no_black_frames", "threshold_luma": 5},
    "RV_ARTIFACT": {"check": "no_glitch", "edge_diff_max": 0.3},
}

# 输出打包
EXPORT_PACKAGES = {
    "EP_SINGLE_MP4": {"name": "单文件MP4", "container": "mp4", "video_codec": "h264",
                      "audio_codec": "aac", "bitrate_mbps": 15, "metadata": True},
    "EP_FRAME_SEQUENCE": {"name": "帧序列", "format": "png_16bit",
                          "naming": "frame_%06d.png", "metadata": "sidecar_json"},
    "EP_PROOF_BUNDLE": {"name": "存证包", "contains": ["output", "parameters", "hashes", "timestamps", "signature"],
                        "format": "tar.xz", "encrypted": True},
    "EP_STREAMING": {"name": "流式分片", "chunk_duration_s": 10,
                     "manifest": "dash_mpd", "drm": "clearkey"},
}


# ═══════════════════════════════════════════
# PART 6: 镜头脚本结构
# ═══════════════════════════════════════════

class ShotScript:
    """单镜头脚本"""
    def __init__(self, shot_id: int, duration_s: float, description: str = ""):
        self.id = shot_id
        self.duration_s = duration_s
        self.description = description
        
        # 场景参数
        self.scene: Dict = {}           # terrain, water, weather, vegetation
        self.lighting: Dict = {}        # light source, brightness, dynamic
        self.camera: Dict = {}          # preset + movement
        self.characters: List['CharacterFrame'] = []
        self.audio: Dict = {}           # voice, ambient, sfx
        
    def set_scene(self, terrain=None, water=None, weather="WE_CLEAR", 
                  wind="WIND_00", vegetation=None):
        self.scene = {
            "terrain": terrain, "water": water,
            "weather": weather, "wind": wind, "vegetation": vegetation,
        }
        return self
    
    def set_lighting(self, source="LT_SUN", brightness="LB_02", dynamic="LD_STILL",
                     angle_deg=45, color_temp=None):
        self.lighting = {
            "source": source, "brightness": brightness, "dynamic": dynamic,
            "angle_deg": angle_deg, "color_temp": color_temp,
        }
        return self
    
    def set_camera(self, preset="CAM_MED", movement="CM_FIXED"):
        self.camera = {"preset": preset, "movement": movement}
        return self
    
    def add_character(self, cf: 'CharacterFrame'):
        self.characters.append(cf)
        return self
    
    def set_audio(self, ambient=None, sfx=None):
        self.audio = {"ambient": ambient or [], "sfx": sfx or []}
        return self
    
    def build(self):
        """生成镜头完整参数"""
        return {
            "shot_id": self.id,
            "duration_s": self.duration_s,
            "total_frames": int(self.duration_s * 24),  # 24fps base
            "description": self.description,
            "scene": self.scene,
            "lighting": self.lighting,
            "camera": self.camera,
            "characters": [c.build() for c in self.characters],
            "audio": self.audio,
        }


class CharacterFrame:
    """镜头内的人物参数 — 逐帧可变, 全维度可控"""
    
    def __init__(self, name: str, body="BODY_MALE_M"):
        self.name = name
        self.body = body
        self.hand = "H_REST"
        self.mouth = "M_CLOSED"
        # 眼部8维
        self.eyelid = "EL_NORMAL"
        self.gaze = "GZ_CENTER"
        self.pupil = "PP_NORMAL"
        self.blink = "BLK_NORMAL"
        self.eye_corner = "EC_NEUTRAL"
        self.eye_socket = "ES_FLAT"
        self.gaze_speed = "GS_SLOW_TRACK"
        self.eye_preset = None
        # 面部
        self.brow_angle = 0
        self.brow_height = 0
        self.cheek = "relaxed"
        self.hair = "HR_SHORT"
        # 肢体
        self.body_posture = "relaxed"
        self.gesture_speed = 1.0
        self.gesture_amp = 1.0
        self.finger_spread = 0.15
        self.arm_swing = 0.3
        # 情绪
        self.emotion = "calm"
        # 位置
        self.position = Vector3()
        self.rotation = Vector3()
        # 语音
        self.voice = "VX_MALE_MID"
        self.voice_emotion = "VE_NEUTRAL"
        self.dialogue = ""
    
    def set_emotion(self, emotion: str):
        """情绪联动: 一键设置全部维度"""
        self.emotion = emotion
        ep = EMOTION_PROFILE.get(emotion, EMOTION_PROFILE["calm"])
        # 口型
        self.mouth = ep.get("mouth", "M_CLOSED")
        # 眼部8维
        if ep.get("eye_preset"):
            self.eye_preset = ep["eye_preset"]
        self.eyelid = ep.get("eyelid", "EL_NORMAL")
        self.gaze = ep.get("gaze", "GZ_CENTER")
        self.pupil = ep.get("pupil", "PP_NORMAL")
        self.blink = ep.get("blink", "BLK_NORMAL")
        self.eye_corner = ep.get("eye_corner", "EC_NEUTRAL")
        self.eye_socket = ep.get("eye_socket", "ES_FLAT")
        self.gaze_speed = ep.get("gaze_speed", "GS_SLOW_TRACK")
        # 面部
        self.brow_angle = ep.get("brow_angle", 0)
        self.brow_height = ep.get("brow_height", 0)
        self.cheek = ep.get("cheek", "relaxed")
        # 肢体
        self.body_posture = ep.get("body_posture", "relaxed")
        self.gesture_speed = ep.get("gesture_speed", 1.0)
        self.gesture_amp = ep.get("gesture_amp", 1.0)
        self.finger_spread = ep.get("finger_spread", 0.1)
        self.arm_swing = ep.get("arm_swing", 0.3)
        # 语音联动
        vp = ep.get("voice_pitch", 1.0)
        vs = ep.get("voice_speed", 1.0)
        if vp > 1.05:
            self.voice_emotion = "VE_LAUGH" if emotion == "joy" else "VE_NEUTRAL"
        elif vs < 0.8:
            self.voice_emotion = "VE_CRY" if emotion == "sadness" else "VE_WHISPER"
        elif vp < 0.9:
            self.voice_emotion = "VE_ANGRY" if emotion == "anger" else "VE_NEUTRAL"
        else:
            self.voice_emotion = "VE_NEUTRAL"
        return self
    
    def build(self):
        return {
            "name": self.name,
            "body": self.body,
            "hand": self.hand,
            "mouth": self.mouth,
            # 眼部
            "eyelid": self.eyelid,
            "gaze": self.gaze,
            "pupil": self.pupil,
            "blink": self.blink,
            "eye_corner": self.eye_corner,
            "eye_socket": self.eye_socket,
            "gaze_speed": self.gaze_speed,
            "eye_preset": self.eye_preset,
            # 面部
            "brow_angle": self.brow_angle,
            "brow_height": self.brow_height,
            "cheek": self.cheek,
            "hair": self.hair,
            # 肢体
            "body_posture": self.body_posture,
            "gesture_speed": self.gesture_speed,
            "gesture_amp": self.gesture_amp,
            "finger_spread": self.finger_spread,
            "arm_swing": self.arm_swing,
            # 情绪
            "emotion": self.emotion,
            # 位置
            "position": vars(self.position),
            "rotation": vars(self.rotation),
            # 语音
            "voice": self.voice,
            "voice_emotion": self.voice_emotion,
            "dialogue": self.dialogue,
        }


# ═══════════════════════════════════════════
# PART 7: 时序调度引擎
# ═══════════════════════════════════════════

class TimelineScheduler:
    """时序调度 — 按帧编排所有参数变化"""
    
    def __init__(self, fps=24):
        self.fps = fps
        self.shots: List[ShotScript] = []
        self.total_frames = 0
    
    def add_shot(self, shot: ShotScript):
        self.shots.append(shot)
        self.total_frames += int(shot.duration_s * self.fps)
        return self
    
    def frame_at(self, frame_idx: int) -> Dict:
        """获取第N帧的完整参数"""
        # 找到对应镜头
        elapsed = 0
        for shot in self.shots:
            shot_frames = int(shot.duration_s * self.fps)
            if frame_idx < elapsed + shot_frames:
                local_frame = frame_idx - elapsed
                progress = local_frame / max(1, shot_frames)
                return self._interpolate_frame(shot, progress)
            elapsed += shot_frames
        
        return {}  # 超出范围
    
    def _interpolate_frame(self, shot: ShotScript, progress: float) -> Dict:
        """帧间插值"""
        f = {"progress": round(progress, 3), "shot_id": shot.id}
        
        # 镜头运动插值
        cam_preset = CAMERA_PRESETS.get(shot.camera.get("preset", "CAM_MED"), {})
        cam_move = CAMERA_MOVEMENT.get(shot.camera.get("movement", "CM_FIXED"), {})
        
        if cam_move.get("zoom", 0) != 0:
            cam_preset = dict(cam_preset)
            cam_preset["fov"] *= (1 - cam_move["zoom"] * progress)
        
        f["camera"] = {**cam_preset, "movement": cam_move, "progress": progress}
        
        # 光影插值
        f["lighting"] = dict(shot.lighting)
        if shot.lighting.get("dynamic") == "LD_PAN":
            f["lighting"]["angle_deg"] = (shot.lighting.get("angle_deg", 45) + progress * 5) % 180
        
        # 人物逐帧
        f["characters"] = []
        for ch in shot.characters:
            cf = ch.build()
            # 眨眼计算
            blink = CHARACTER_BLINK.get(ch.blink, {})
            interval = blink.get("interval_s", 4)
            if interval < 999:
                local_time = progress * shot.duration_s
                blink_phase = (local_time % interval) / interval
                cf["is_blinking"] = blink_phase > 0.95
            f["characters"].append(cf)
        
        f["audio"] = dict(shot.audio)
        return f
    
    def build_timeline(self) -> List[Dict]:
        """生成完整时间线 (每帧一个状态快照)"""
        return [self.frame_at(i) for i in range(self.total_frames)]
    
    def export(self, path=None):
        """导出时间线 JSON"""
        data = {
            "fps": self.fps,
            "total_frames": self.total_frames,
            "total_duration_s": self.total_frames / self.fps,
            "shots": [s.build() for s in self.shots],
        }
        if path:
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2))
        return data


# ═══════════════════════════════════════════
# PART 8: 完整演示
# ═══════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 65)
    print("  v3 ACHILLES — Full Pipeline Demo")
    print("=" * 65)
    
    # 创建镜头1: 林间小溪, 男主角行走, 阳光明媚
    shot1 = ShotScript(1, 5.0, "林间小溪，男主缓缓走过")
    shot1.set_scene(terrain="T_HIL_01", water="W_STM_01",
                    weather="WE_CLEAR", wind="WIND_01",
                    vegetation=["V_TREE_OAK", "V_BUSH", "V_GRASS"])
    shot1.set_lighting(source="LT_SUN", brightness="LB_03", dynamic="LD_PAN", angle_deg=45)
    shot1.set_camera(preset="CAM_WIDE", movement="CM_SLOW_PUSH")
    
    char1 = CharacterFrame("男主角", "BODY_MALE_M")
    char1.set_emotion("calm")
    char1.position = Vector3(0, 0, 0)
    char1.dialogue = "今天的森林真安静。"
    shot1.add_character(char1)
    shot1.set_audio(ambient=["AMB_RIVER", "AMB_BIRDS"], sfx=["SFX_FOOTSTEP"])
    
    # 创建镜头2: 特写面部, 喜悦表情, 暖光
    shot2 = ShotScript(2, 3.0, "男主角面部特写，微笑")
    shot2.set_scene(weather="WE_CLEAR", wind="WIND_00")
    shot2.set_lighting(source="LT_SUN", brightness="LB_03", angle_deg=15)
    shot2.set_camera(preset="CAM_CU", movement="CM_FIXED")
    
    char2 = CharacterFrame("男主角", "BODY_MALE_M")
    char2.set_emotion("joy")
    char2.dialogue = "真美啊。"
    shot2.add_character(char2)
    
    # 构建时间线
    tl = TimelineScheduler(fps=24)
    tl.add_shot(shot1).add_shot(shot2)
    
    data = tl.export()
    
    print(f"\nTimeline: {data['total_frames']} frames @ {data['fps']}fps")
    print(f"Duration: {data['total_duration_s']}s")
    print(f"Shots: {len(data['shots'])}")
    
    for s in data['shots']:
        print(f"\n  Shot #{s['shot_id']}: {s['duration_s']}s ({s['total_frames']}fr)")
        print(f"    '{s['description']}'")
        print(f"    Scene: terrain={s['scene'].get('terrain')} weather={s['scene'].get('weather')}")
        print(f"    Light: {s['lighting'].get('source')} {s['lighting'].get('brightness')} ({s['lighting'].get('angle_deg')}deg)")
        print(f"    Camera: {s['camera'].get('preset')} + {s['camera'].get('movement')}")
        print(f"    Audio: ambient={s['audio'].get('ambient')} sfx={s['audio'].get('sfx')}")
        for ch in s['characters']:
            print(f"    Character: {ch['name']} [{ch['emotion']}] mouth={ch['mouth']} eyelid={ch.get('eyelid','?')} gaze={ch.get('gaze','?')}")
            if ch['dialogue']:
                print(f"      Says: \"{ch['dialogue']}\" voice={ch['voice']} {ch['voice_emotion']}")
    
    # 逐帧采样演示
    print(f"\n{'-'*65}")
    print(f"Frame samples (0, 60, 120, 180):")
    for fi in [0, 60, 120, 180]:
        f = tl.frame_at(fi)
        if f:
            cam = f.get('camera', {})
            print(f"  Frame {fi}: shot={f['shot_id']} progress={f['progress']:.2f} "
                  f"fov={cam.get('fov','?'):.1f} characters={len(f.get('characters',[]))}")
    
    # 统计
    print(f"\n{'='*65}")
    print(f"  PARAMETER LIBRARY STATS")
    print(f"{'='*65}")
    sections = [
        ("  Dimensional Scales", DIMENSIONAL_SCALES),
        ("Scene Terrain", SCENE_TERRAIN),
        ("Scene Water", SCENE_WATER),
        ("Weather", SCENE_WEATHER),
        ("Wind", SCENE_WIND),
        ("Vegetation", SCENE_VEGETATION),
        ("Lighting", SCENE_LIGHTING),
        ("Camera Presets", CAMERA_PRESETS),
        ("Camera Movement", CAMERA_MOVEMENT),
        ("Character Body", CHARACTER_BODY),
        ("Hand Gestures", CHARACTER_HAND),
        ("Mouth Shapes", CHARACTER_MOUTH),
        ("Eye Eyelid", CHARACTER_EYELID),
        ("Eye Gaze", CHARACTER_GAZE),
        ("Eye Pupil", CHARACTER_PUPIL),
        ("Eye Blink", CHARACTER_BLINK),
        ("Eye Corner", CHARACTER_EYE_CORNER),
        ("Eye Socket", CHARACTER_EYE_SOCKET),
        ("Eye Gaze Speed", CHARACTER_GAZE_SPEED),
        ("Eye Presets", EYE_PRESETS),
        ("Hair Styles", CHARACTER_HAIR),
        ("Emotion Profiles", EMOTION_PROFILE),
        # 服饰
        ("Clothing Upper", CLOTHING_UPPER),
        ("Clothing Lower", CLOTHING_LOWER),
        ("Clothing Footwear", CLOTHING_FOOTWEAR),
        ("Clothing Accessory", CLOTHING_ACCESSORY),
        # 物理光照
        ("Light AO", {k:v for k,v in LIGHT_PHYSICS.items() if k.startswith("AO_")}),
        ("Light SSS", {k:v for k,v in LIGHT_PHYSICS.items() if k.startswith("SSS_")}),
        ("Light Spec/Diff", {k:v for k,v in LIGHT_PHYSICS.items() if k.startswith("SPEC_") or k.startswith("DIFF_")}),
        ("Light Shadow", {k:v for k,v in LIGHT_PHYSICS.items() if k.startswith("SHADOW_")}),
        # 手指
        ("Finger Joints", FINGER_JOINT),
        ("Hand Presets", HAND_PRESET),
        # 脚步
        ("Footstep Ground", FOOTSTEP_GROUND),
        ("Footstep Shoe", FOOTSTEP_SHOE),
        # FACS
        ("FACS Units", FACS_UNITS),
        ("FACS Emotions", FACS_EMOTION),
        # 剧情
        ("Story Structures", STORY_STRUCTURES),
        ("Emotional Arcs", EMOTIONAL_ARC),
        ("Conflict Types", CONFLICT_TYPES),
        ("Pacing Presets", PACING_PRESETS),
        # 分镜
        ("Shot Transitions", SHOT_TRANSITIONS),
        ("Shot Sizes", SHOT_SIZES),
        ("Axis Rules", AXIS_RULES),
        ("Composition Rules", COMPOSITION_RULES),
        # 色彩
        ("Color Palettes", COLOR_PALETTES),
        ("Color Grading", COLOR_GRADING),
        # 粒子
        ("Particle Systems", PARTICLE_SYSTEMS),
        # 动作
        ("Character Actions", CHARACTER_ACTIONS),
        ("Action Blend", ACTION_BLEND),
        # 输出
        ("Output Formats", OUTPUT_FORMATS),
        # 音频
        ("Voice Presets", VOICE_PRESETS),
        ("Voice Emotion", VOICE_EMOTION),
        ("Ambient Sounds", AMBIENT_SOUNDS),
        ("SFX Library", SFX_LIBRARY),
        # 音频合成
        ("Audio Synth Waveforms", AUDIO_SYNTH),
        ("Envelope Presets", ENVELOPE_PRESETS),
        ("Mixer Baker", MIXER_BAKER),
        ("TTS Emotion Map", TTS_EMOTION_MAP),
        ("Ambient Generators", AMBIENT_GENERATORS),
        ("SFX Generators", SFX_GENERATORS),
        # 安全水印
        ("Watermark Methods", WATERMARK_METHODS),
        ("License Presets", LICENSE_PRESETS),
        ("Provenance Chain", PROVENANCE_CHAIN),
        # 口型同步
        ("Phoneme→Mouth", PHONEME_TO_MOUTH),
        ("Pinyin→Mouth", PINYIN_TO_MOUTH),
        ("Mouth Transition", MOUTH_TRANSITION),
        # 耳脑直通
        ("Listen Pipeline", LISTEN_PIPELINE),
        ("Interrupt Handling", INTERRUPT_HANDLING),
        # 物理
        ("Gravity Presets", GRAVITY_PRESETS),
        ("Collision Materials", COLLISION_MATERIALS),
        ("Constraint Types", CONSTRAINT_TYPES),
        ("Cloth Sim Presets", CLOTH_SIM_PRESETS),
        ("Particle Physics", PARTICLE_PHYSICS),
        # 多输出
        ("Render Queue", RENDER_QUEUE),
        ("Scheduler Pipeline", SCHEDULER_PIPELINE),
        ("Frame→Workflow", FRAME_TO_WORKFLOW),
        ("Render Validation", RENDER_VALIDATION),
        ("Export Packages", EXPORT_PACKAGES),
    ]
    total = 0
    for name, db in sections:
        n = len(db)
        total += n
        print(f"  {name:<22s} {n:3d} codes")
    print(f"  {'─'*30}")
    print(f"  {'TOTAL':<22s} {total:3d} parameter codes")
