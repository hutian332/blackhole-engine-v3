"""
v3 全参数库 — 统一编码规则
========================================
1.基础形状  2.尺寸  3.颜色  4.骨骼  5.运动
10.光线     11.画质

万物皆静态编码 → 按帧重组 → 连续输出视频流
"""

import json

# ═══════════════════════════════════════
# 10. 光线参数库
# ═══════════════════════════════════════

LIGHT_DIRECTION = {
    "L_D01": {"name": "正上方直射", "type": "顶光", "vector": (0, -1, 0)},
    "L_D02": {"name": "斜左上", "type": "侧顶光", "vector": (-1, -1, 0.5)},
    "L_D03": {"name": "斜右上", "type": "侧顶光", "vector": (1, -1, 0.5)},
    "L_D04": {"name": "正左侧", "type": "正侧光", "vector": (-1, 0, 0)},
    "L_D05": {"name": "正右侧", "type": "正侧光", "vector": (1, 0, 0)},
    "L_D06": {"name": "斜左下", "type": "底侧光", "vector": (-1, 1, 0.5)},
    "L_D07": {"name": "斜右下", "type": "底侧光", "vector": (1, 1, 0.5)},
    "L_D08": {"name": "正前方", "type": "面光", "vector": (0, 0, 1)},
    "L_D09": {"name": "正后方", "type": "逆光/轮廓光", "vector": (0, 0, -1)},
}

LIGHT_ANGLE = {
    "L_A00": {"angle": 0, "name": "平行扫光", "scenario": "水平扫描光"},
    "L_A01": {"angle": 15, "name": "低角度柔光", "scenario": "清晨/黄昏"},
    "L_A02": {"angle": 30, "name": "日常外景自然光", "scenario": "室外普通光照"},
    "L_A03": {"angle": 45, "name": "标准主光", "scenario": "通用画面主光源"},
    "L_A04": {"angle": 60, "name": "偏顶光", "scenario": "上午/下午天光"},
    "L_A05": {"angle": 90, "name": "垂直顶光", "scenario": "正午强光"},
}

LIGHT_LENGTH = {
    "L_L01": {"distance_cm": 50, "coverage": "近距离局部"},
    "L_L02": {"distance_cm": 120, "coverage": "单人/单件物体"},
    "L_L03": {"distance_cm": 240, "coverage": "小范围场景"},
    "L_L04": {"distance_cm": 500, "coverage": "室内整屋"},
    "L_L05": {"distance_cm": 800, "coverage": "户外大范围环境光"},
}

LIGHT_RANGE = {
    "L_R01": {"beam_angle": 10, "type": "窄束光", "examples": "手电筒、射灯"},
    "L_R02": {"beam_angle": 30, "type": "中束光", "examples": "聚光灯、台灯"},
    "L_R03": {"beam_angle": 60, "type": "常规漫射光", "examples": "室内主灯、柔光箱"},
    "L_R04": {"beam_angle": 90, "type": "大范围柔光", "examples": "窗光"},
    "L_R05": {"beam_angle": 180, "type": "全域环境光", "examples": "阴天散射光"},
}

LIGHT_STRENGTH = {
    "L_S00": {"value": 0, "name": "全黑"},
    "L_S01": {"value": 2, "name": "微光", "effect": "夜晚/烛火"},
    "L_S02": {"value": 4, "name": "弱光", "effect": "阴天/傍晚"},
    "L_S03": {"value": 6, "name": "标准亮度", "effect": "日常室内/户外"},
    "L_S04": {"value": 8, "name": "强光", "effect": "晴天日光"},
    "L_S05": {"value": 10, "name": "极亮", "effect": "高光/闪光"},
}

LIGHT_COLOR = {
    "L_C01": {"name": "白光", "rgb": (255, 255, 255), "hex": "#FFFFFF"},
    "L_C02": {"name": "暖黄光", "rgb": (255, 240, 180), "hex": "#FFF0B4"},
    "L_C03": {"name": "冷蓝光", "rgb": (180, 220, 255), "hex": "#B4DCFF"},
    "L_C04": {"name": "红光", "rgb": (255, 80, 80), "hex": "#FF5050"},
    "L_C05": {"name": "绿光", "rgb": (80, 255, 120), "hex": "#50FF78"},
}

LIGHT_MOTION = {
    "L_M00": {"name": "光线静止", "speed": "static"},
    "L_M01": {"name": "缓慢平移", "speed": "slow_pan", "desc": "太阳移位"},
    "L_M02": {"name": "小幅摇摆", "speed": "oscillate", "desc": "烛火/风吹灯盏"},
    "L_M03": {"name": "明暗闪烁", "speed": "flicker", "desc": "火焰/星光"},
    "L_M04": {"name": "光束扫动", "speed": "sweep", "desc": "光线扫射"},
}

# ═══════════════════════════════════════
# 11. 画质参数库
# ═══════════════════════════════════════

QUALITY_RESOLUTION = {
    "Q_R01": {"name": "标清", "w": 720, "h": 480, "pixels": "0.3MP"},
    "Q_R02": {"name": "高清", "w": 1280, "h": 720, "pixels": "0.9MP"},
    "Q_R03": {"name": "全高清", "w": 1920, "h": 1080, "pixels": "2.1MP"},
    "Q_R04": {"name": "2K", "w": 2560, "h": 1440, "pixels": "3.7MP"},
    "Q_R05": {"name": "4K", "w": 3840, "h": 2160, "pixels": "8.3MP"},
}

QUALITY_SAMPLING = {
    "Q_S01": {"steps": 15, "name": "低采样", "desc": "速度快，画质一般"},
    "Q_S02": {"steps": 30, "name": "中采样", "desc": "均衡画质与速度"},
    "Q_S03": {"steps": 50, "name": "高采样", "desc": "细节丰富，高清首选"},
}

QUALITY_SHARPEN = {
    "Q_SH00": {"value": 0, "name": "无锐化", "desc": "原生柔和"},
    "Q_SH05": {"value": 5, "name": "中等锐化", "desc": "常规清晰"},
    "Q_SH10": {"value": 10, "name": "高锐化", "desc": "边缘锐利、细节拉满"},
}

# ═══════════════════════════════════════
# 光线预设
# ═══════════════════════════════════════

LIGHT_PRESETS = {
    "sunlight_natural": {
        "name": "自然日光",
        "codes": ("L_D02", "L_A03", "L_L05", "L_R05", "L_S04", "L_C01", "L_M01"),
    },
    "studio_portrait": {
        "name": "影棚人像",
        "codes": ("L_D02", "L_A03", "L_L02", "L_R03", "L_S04", "L_C01", "L_M00"),
    },
    "sunset_warm": {
        "name": "黄昏暖光",
        "codes": ("L_D02", "L_A01", "L_L05", "L_R04", "L_S03", "L_C02", "L_M01"),
    },
    "moonlight": {
        "name": "月光夜景",
        "codes": ("L_D02", "L_A02", "L_L05", "L_R05", "L_S01", "L_C03", "L_M00"),
    },
    "candle_fire": {
        "name": "烛火",
        "codes": ("L_D01", "L_A00", "L_L01", "L_R02", "L_S01", "L_C02", "L_M03"),
    },
    "flashlight": {
        "name": "手电筒",
        "codes": ("L_D08", "L_A00", "L_L03", "L_R01", "L_S04", "L_C01", "L_M04"),
    },
    "theater_spotlight": {
        "name": "剧场追光",
        "codes": ("L_D01", "L_A05", "L_L03", "L_R01", "L_S05", "L_C01", "L_M04"),
    },
    "horror_backlight": {
        "name": "恐怖逆光",
        "codes": ("L_D09", "L_A00", "L_L02", "L_R04", "L_S04", "L_C04", "L_M03"),
    },
    "dream_fantasy": {
        "name": "幻境光",
        "codes": ("L_D02", "L_A02", "L_L04", "L_R04", "L_S03", "L_C05", "L_M02"),
    },
    "noon_harsh": {
        "name": "正午强光",
        "codes": ("L_D01", "L_A05", "L_L05", "L_R05", "L_S05", "L_C01", "L_M00"),
    },
}

QUALITY_PRESETS = {
    "fast_preview":  {"name": "快速预览", "codes": ("Q_R02", "Q_S01", "Q_SH00")},
    "standard":      {"name": "标准出片", "codes": ("Q_R03", "Q_S02", "Q_SH05")},
    "high_quality":  {"name": "高质量",   "codes": ("Q_R03", "Q_S03", "Q_SH10")},
    "cinema_4k":     {"name": "电影级4K", "codes": ("Q_R05", "Q_S03", "Q_SH05")},
}

# ═══════════════════════════════════════
# 实体类目 (1-9，复用)
# ═══════════════════════════════════════

ENTITY_CATEGORIES = {
    "bio_human":        {"cat": "生物-人类",    "sub": ["成年男性","成年女性","儿童","老人","战士","法师"]},
    "bio_land":         {"cat": "生物-陆生动物","sub": ["犬","猫","马","牛","虎","狮","熊","鹿","兔"]},
    "bio_bird":         {"cat": "生物-飞禽",    "sub": ["鹰","雀","鹤","鹦鹉","凤凰"]},
    "bio_water":        {"cat": "生物-水生动物","sub": ["鱼","鲸","鲨","海豚","龟"]},
    "bio_insect":       {"cat": "生物-虫爬",    "sub": ["蛇","蜥蜴","蜘蛛","蝎子","蝴蝶"]},
    "wp_long":          {"cat": "武器-长柄",    "sub": ["长枪","大刀","长矛","戟","棍"]},
    "wp_short":         {"cat": "武器-短柄",    "sub": ["剑","刀","匕首","斧","锤"]},
    "wp_range":         {"cat": "武器-远程",    "sub": ["弓","弩","火枪"]},
    "wp_armor":         {"cat": "武器-防具",    "sub": ["盾","头盔","胸甲","护腕"]},
    "home_table":       {"cat": "家居-桌台",    "sub": ["方桌","圆桌","书桌","茶几"]},
    "home_chair":       {"cat": "家居-椅凳",    "sub": ["靠椅","长凳","沙发"]},
    "home_storage":     {"cat": "家居-储物",    "sub": ["柜子","书架","箱子"]},
    "home_ware":        {"cat": "家居-日用器物","sub": ["瓶子","碗","壶","灯"]},
    "bldg_wall":        {"cat": "建筑-墙体",    "sub": ["砖墙","石墙","木墙"]},
    "bldg_door":        {"cat": "建筑-门窗",    "sub": ["木门","铁门","拱门","窗格"]},
    "bldg_beam":        {"cat": "建筑-梁柱",    "sub": ["木柱","石柱","横梁"]},
    "bldg_roof":        {"cat": "建筑-屋顶地面","sub": ["瓦顶","平顶","石板地","木地板"]},
    "bldg_yard":        {"cat": "建筑-院落",    "sub": ["围墙","水井","台阶"]},
    "nat_rock":         {"cat": "自然-山石岩土","sub": ["山","岩","石"]},
    "nat_water":        {"cat": "自然-水体",    "sub": ["河流","湖泊","瀑布","池塘"]},
    "nat_plant":        {"cat": "自然-植被",    "sub": ["树","灌木","花丛","草"]},
    "nat_weather":      {"cat": "自然-天象地貌","sub": ["云","山峦","悬崖","平原"]},
    "vehicle_land":     {"cat": "交通-陆地载具","sub": ["马车","汽车","摩托"]},
    "vehicle_water":    {"cat": "交通-水上载具","sub": ["木舟","帆船"]},
    "tool_farm":        {"cat": "工具-农耕",    "sub": ["锄头","镰刀","犁"]},
    "tool_hand":        {"cat": "工具-手工",    "sub": ["锤子","锯子","凿"]},
    "fantasy_weapon":   {"cat": "幻想-法器法宝","sub": ["飞剑","宝珠","符咒"]},
    "fantasy_beast":    {"cat": "幻想-奇珍异兽","sub": ["龙","麒麟","九尾狐"]},
}


# ═══════════════════════════════════════
# 参数对象
# ═══════════════════════════════════════

class LightParams:
    """光线参数 — 7维独立可调"""
    
    def __init__(self, direction="L_D02", angle="L_A03", length="L_L02",
                 range_code="L_R03", strength="L_S03", color="L_C01", motion="L_M00"):
        self.direction = direction
        self.angle = angle
        self.length = length
        self.range = range_code
        self.strength = strength
        self.color = color
        self.motion = motion
    
    @classmethod
    def from_preset(cls, name):
        p = LIGHT_PRESETS.get(name)
        if p: return cls(*p['codes'])
        raise ValueError(f"Unknown preset: {name}")
    
    @classmethod
    def from_description(cls, desc):
        """自然语言 → 编码"""
        d = desc.lower()
        direction = "L_D01" if any(w in d for w in ['顶','上','top']) else \
                    "L_D08" if any(w in d for w in ['正前','前','front']) else \
                    "L_D09" if any(w in d for w in ['后','背','逆光','back']) else \
                    "L_D03" if any(w in d for w in ['右','right']) else "L_D02"
        angle = "L_A01" if any(w in d for w in ['低角','黄昏','夕阳','清晨']) else \
                "L_A05" if any(w in d for w in ['正午','垂直','中午']) else \
                "L_A04" if any(w in d for w in ['偏顶','上午','下午']) else "L_A03"
        strength = "L_S04" if any(w in d for w in ['强光','烈日','bright','晴天']) else \
                   "L_S01" if any(w in d for w in ['微光','暗','夜晚','night','dim']) else \
                   "L_S02" if any(w in d for w in ['弱光','阴天','傍晚']) else \
                   "L_S05" if any(w in d for w in ['极亮','闪光','爆炸']) else "L_S03"
        color = "L_C02" if any(w in d for w in ['暖','黄','夕阳','烛','黄昏']) else \
                "L_C03" if any(w in d for w in ['冷','蓝','月','夜晚','夜']) else \
                "L_C04" if any(w in d for w in ['红','火','red']) else \
                "L_C05" if any(w in d for w in ['绿','幻','green']) else "L_C01"
        motion = "L_M01" if any(w in d for w in ['平移','移动','移位']) else \
                 "L_M02" if any(w in d for w in ['摇摆','晃动','摇晃']) else \
                 "L_M03" if any(w in d for w in ['闪烁','闪','明暗']) else \
                 "L_M04" if any(w in d for w in ['扫','扫射','扫动']) else "L_M00"
        range_code = "L_R01" if any(w in d for w in ['窄','手电','射灯','聚光']) else \
                     "L_R04" if any(w in d for w in ['宽','大范围','环境光','散射']) else "L_R03"
        length = "L_L01" if any(w in d for w in ['特写','近','脸部','面部']) else \
                 "L_L02" if any(w in d for w in ['单人','单件']) else \
                 "L_L04" if any(w in d for w in ['室内','房间','屋']) else \
                 "L_L05" if any(w in d for w in ['户外','远景','大范围','环境']) else "L_L03"
        return cls(direction, angle, length, range_code, strength, color, motion)
    
    @property
    def codes(self):
        return (self.direction, self.angle, self.length, self.range, self.strength, self.color, self.motion)
    
    def _get(self, db, code):
        return db.get(code, {})
    
    def prompt(self):
        d = LIGHT_DIRECTION.get(self.direction, {})
        a = LIGHT_ANGLE.get(self.angle, {})
        l = LIGHT_LENGTH.get(self.length, {})
        r = LIGHT_RANGE.get(self.range, {})
        s = LIGHT_STRENGTH.get(self.strength, {})
        c = LIGHT_COLOR.get(self.color, {})
        m = LIGHT_MOTION.get(self.motion, {})
        return (f"{d.get('name','?')} {a.get('name','?')}, "
                f"{l.get('distance_cm','?')}cm {r.get('type','?')}, "
                f"强度{s.get('value','?')} {c.get('name','?')} {c.get('rgb','?')}, "
                f"{m.get('name','?')}")
    
    def seedance_hint(self):
        s = LIGHT_STRENGTH.get(self.strength, {})
        c = LIGHT_COLOR.get(self.color, {})
        m = LIGHT_MOTION.get(self.motion, {})
        d = LIGHT_DIRECTION.get(self.direction, {})
        return {
            "key_light": {
                "position": d.get('vector'),
                "intensity": s.get('value', 6) / 10,
                "color": list(c.get('rgb', (255, 255, 255))),
            },
            "ambient_light": {
                "intensity": max(0.1, s.get('value', 6) / 20),
                "color": list(c.get('rgb', (255, 255, 255))),
            },
            "motion": m.get('speed', 'static'),
        }


class QualityParams:
    """画质参数 — 3维独立可调"""
    
    def __init__(self, resolution="Q_R03", sampling="Q_S02", sharpen="Q_SH05"):
        self.resolution = resolution
        self.sampling = sampling
        self.sharpen = sharpen
    
    @classmethod
    def from_preset(cls, name):
        p = QUALITY_PRESETS.get(name)
        if p: return cls(*p['codes'])
        raise ValueError(f"Unknown quality preset: {name}")
    
    def prompt(self):
        r = QUALITY_RESOLUTION.get(self.resolution, {})
        s = QUALITY_SAMPLING.get(self.sampling, {})
        sh = QUALITY_SHARPEN.get(self.sharpen, {})
        return (f"{r.get('name','?')} {r.get('w','?')}x{r.get('h','?')}, "
                f"采样{s.get('steps','?')}步, 锐化{sh.get('value','?')}级")
    
    def seedance_hint(self):
        r = QUALITY_RESOLUTION.get(self.resolution, {})
        s = QUALITY_SAMPLING.get(self.sampling, {})
        sh = QUALITY_SHARPEN.get(self.sharpen, {})
        return {
            "width": r.get('w', 1920),
            "height": r.get('h', 1080),
            "steps": s.get('steps', 30),
            "sharpness": sh.get('value', 5),
        }


# ═══════════════════════════════════════
# 最终拼接器
# ═══════════════════════════════════════

class FrameBuilder:
    """帧拼接器 — 万物死编码 → 活视频帧
    
    使用:
      fb = FrameBuilder()
      fb.entity("bio_land", "犬")
      fb.part("S_head", "M_L20", "C_creamy", bone="B_DOG_HEAD")
      fb.motion(angle=15, speed=0.8, direction="right")
      fb.light(LightParams.from_preset("sunset_warm"))
      fb.quality(QualityParams.from_preset("cinema_4k"))
      fb.build()  → 完整帧描述
    """
    
    def __init__(self):
        self._entity = None
        self._parts = []
        self._motion = {}
        self._light = LightParams()
        self._quality = QualityParams()
    
    def entity(self, category, sub_item):
        self._entity = {"category": category, "item": sub_item}
        return self
    
    def part(self, shape, size, color, bone=None, motion=None):
        self._parts.append({
            "shape": shape, "size": size, "color": color,
            "bone": bone, "motion": motion,
        })
        return self
    
    def motion(self, angle=0, displacement=0, deform=0, speed=0, direction="none"):
        self._motion = {
            "angle": angle, "displacement": displacement,
            "deform": deform, "speed": speed, "direction": direction,
        }
        return self
    
    def light(self, lp):
        self._light = lp
        return self
    
    def quality(self, qp):
        self._quality = qp
        return self
    
    def build(self):
        """输出完整帧参数"""
        return {
            "entity": self._entity,
            "parts": self._parts,
            "motion": self._motion,
            "light": {
                "codes": self._light.codes,
                "prompt": self._light.prompt(),
                "seedance": self._light.seedance_hint(),
            },
            "quality": {
                "prompt": self._quality.prompt(),
                "seedance": self._quality.seedance_hint(),
            },
        }
    
    def build_prompt(self, format="seedance"):
        """输出完整文本提示"""
        b = self.build()
        parts_desc = "; ".join(
            f"{p['shape']}/{p['size']}/{p['color']}" + (f"/{p['bone']}" if p.get('bone') else "")
            for p in b['parts']
        )
        entity = f"{b['entity']['item']}" if b['entity'] else ""
        
        lines = [f"Subject: {entity} [{parts_desc}]"]
        if any(self._motion.values()):
            lines.append(f"Motion: angle={self._motion['angle']} "
                        f"disp={self._motion['displacement']} "
                        f"speed={self._motion['speed']} {self._motion['direction']}")
        lines.append(f"Lighting: {self._light.prompt()}")
        lines.append(f"Quality: {self._quality.prompt()}")
        return "\n".join(lines)


# ═══════════════════════════════════════
# 演示
# ═══════════════════════════════════════

if __name__ == "__main__":
    print("=" * 65)
    print("  v3 FULL PARAMETER LIBRARY")
    print("=" * 65)
    
    # 光线库
    print("\n[10. LIGHT PARAMETERS]")
    for code, info in LIGHT_DIRECTION.items():
        print(f"  {code} {info['name']:<10s} type={info['type']}")
    print(f"  ... {len(LIGHT_DIRECTION)+len(LIGHT_ANGLE)+len(LIGHT_LENGTH)+len(LIGHT_RANGE)+len(LIGHT_STRENGTH)+len(LIGHT_COLOR)+len(LIGHT_MOTION)} codes total")
    
    # 画质库
    print("\n[11. QUALITY PARAMETERS]")
    for code, info in QUALITY_RESOLUTION.items():
        print(f"  {code} {info['w']}x{info['h']} {info['name']}")
    for code, info in QUALITY_SAMPLING.items():
        print(f"  {code} {info['steps']} steps {info['name']}")
    for code, info in QUALITY_SHARPEN.items():
        print(f"  {code} sharpen={info['value']} {info['name']}")
    
    # 预设
    print("\n[LIGHT PRESETS]")
    for k, v in LIGHT_PRESETS.items():
        print(f"  {k:<20s} {v['name']}")
    print("\n[QUALITY PRESETS]")
    for k, v in QUALITY_PRESETS.items():
        print(f"  {k:<20s} {v['name']}")
    
    # 完整拼接演示
    print("\n" + "=" * 65)
    print("  COMPLETE BUILD DEMO")
    print("=" * 65)
    
    fb = FrameBuilder()
    fb.entity("bio_land", "犬")
    fb.part("S_head", "M_L20", "C_creamy", bone="B_DOG_HEAD")
    fb.part("S_body", "M_L40", "C_creamy", bone="B_DOG_BODY")
    fb.motion(angle=5, speed=0.5, direction="left")
    fb.light(LightParams.from_preset("sunset_warm"))
    fb.quality(QualityParams.from_preset("cinema_4k"))
    
    result = fb.build()
    print(f"\nEntity: {result['entity']}")
    print(f"Parts: {len(result['parts'])}")
    print(f"Motion: {result['motion']}")
    print(f"\nLighting Prompt:")
    print(f"  {result['light']['prompt']}")
    print(f"\nQuality Prompt:")
    print(f"  {result['quality']['prompt']}")
    print(f"\n--- Seedance 2.0 Ready ---")
    print(json.dumps({
        **result['light']['seedance'],
        **result['quality']['seedance'],
    }, indent=2))
    
    print("\n" + "=" * 65)
    print("  NATURAL LANGUAGE → CODES")
    print("=" * 65)
    for text in ["夕阳暖光从左边斜照", "正午烈日顶光", "烛火摇曳闪烁", "蓝色月光夜景"]:
        lp = LightParams.from_description(text)
        print(f"  '{text}' → {lp.codes}")
    
    print(f"\nDone. All libraries ready.")
