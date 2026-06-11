"""
frenchie_pet.py — 法斗桌宠 v2
╔══════════════════════════════════════════════════╗
║  🐾 v3 的脸 — 有灵魂的桌面法斗                   ║
║  性格: 懒/馋/粘人/傲娇                           ║
║  能力: 自主行为 + v3 脑连接 + 成长记忆            ║
╚══════════════════════════════════════════════════╝

殷竺欣 独家原创 | 2026-06-11 08:15 GMT+8
"""
import tkinter as tk
import os, sys, json, threading, time, random, math, urllib.request
from datetime import datetime

# ═══════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════
PET_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(PET_DIR, "frenchie_state.json")
V3_URL = "http://localhost:8081/v1/chat/completions"
TZ = "Asia/Shanghai"

# 宠物属性
INITIAL_STATS = {"hunger": 80, "energy": 90, "happiness": 70, "affection": 50}
DECAY_RATES = {"hunger": -0.3, "energy": -0.15, "happiness": -0.1, "affection": -0.02}  # 每分钟
MAX_STAT = 100
MIN_STAT = 0

# 动画帧率
ANIM_FPS = 30
BEHAVIOR_INTERVAL = 8  # 秒，自主行为间隔

# ═══════════════════════════════════════════════
# 属性系统
# ═══════════════════════════════════════════════

class PetStats:
    def __init__(self):
        self.hunger = INITIAL_STATS["hunger"]
        self.energy = INITIAL_STATS["energy"]
        self.happiness = INITIAL_STATS["happiness"]
        self.affection = INITIAL_STATS["affection"]
        self.age = 0  # 分钟
        self.total_interactions = 0
    
    def decay(self, minutes: float = 1.0):
        """每分钟衰减"""
        self.hunger = max(MIN_STAT, min(MAX_STAT, self.hunger + DECAY_RATES["hunger"] * minutes))
        self.energy = max(MIN_STAT, min(MAX_STAT, self.energy + DECAY_RATES["energy"] * minutes))
        self.happiness = max(MIN_STAT, min(MAX_STAT, self.happiness + DECAY_RATES["happiness"] * minutes))
        self.affection = max(MIN_STAT, min(MAX_STAT, self.affection + DECAY_RATES["affection"] * minutes))
        self.age += minutes
    
    def feed(self, amount: int = 30):
        self.hunger = min(MAX_STAT, self.hunger + amount)
        self.happiness = min(MAX_STAT, self.happiness + amount * 0.3)
        self.total_interactions += 1
    
    def play(self, amount: int = 20):
        self.happiness = min(MAX_STAT, self.happiness + amount)
        self.energy = max(MIN_STAT, self.energy - amount * 0.5)
        self.affection = min(MAX_STAT, self.affection + amount * 0.4)
        self.hunger = max(MIN_STAT, self.hunger - amount * 0.2)
        self.total_interactions += 1
    
    def pet(self):
        self.affection = min(MAX_STAT, self.affection + 10)
        self.happiness = min(MAX_STAT, self.happiness + 5)
        self.total_interactions += 1
    
    def sleep(self, minutes: float = 1.0):
        self.energy = min(MAX_STAT, self.energy + minutes * 3)
        self.happiness = min(MAX_STAT, self.happiness + minutes * 0.5)
    
    def mood(self) -> str:
        """综合心情"""
        avg = (self.hunger + self.energy + self.happiness) / 3
        if self.hunger < 20:
            return "hungry"
        if self.energy < 15:
            return "tired"
        if self.happiness < 20:
            return "sad"
        if avg > 75:
            return "happy"
        if avg > 45:
            return "content"
        return "meh"
    
    def to_dict(self):
        return {
            "hunger": self.hunger, "energy": self.energy,
            "happiness": self.happiness, "affection": self.affection,
            "age": self.age, "total_interactions": self.total_interactions,
            "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
        }
    
    @classmethod
    def from_dict(cls, d):
        s = cls()
        s.hunger = d.get("hunger", INITIAL_STATS["hunger"])
        s.energy = d.get("energy", INITIAL_STATS["energy"])
        s.happiness = d.get("happiness", INITIAL_STATS["happiness"])
        s.affection = d.get("affection", INITIAL_STATS["affection"])
        s.age = d.get("age", 0)
        s.total_interactions = d.get("total_interactions", 0)
        return s


# ═══════════════════════════════════════════════
# 法斗绘制引擎
# ═══════════════════════════════════════════════

class FrenchieDrawer:
    """画法斗——不同状态不同表情"""
    
    # 颜色
    BODY = '#F0D5A0'       # 奶油色身体
    BODY_DARK = '#E0C080'
    MASK = '#4A3728'        # 深色面罩
    MASK_LIGHT = '#6B5040'
    EAR_IN = '#D4A0A0'      # 耳朵内侧
    NOSE = '#1a1a1a'
    EYE = '#1a1a1a'
    EYE_HIGHLIGHT = '#ffffff'
    TONGUE = '#E8888E'
    BELLY = '#FFF8EE'
    COLLAR = '#CC3333'
    TAG = '#FFD700'
    
    def __init__(self, canvas: tk.Canvas, w: int = 300, h: int = 340):
        self.c = canvas
        self.w = w
        self.h = h
        self.cx = w // 2
        self.cy = h // 2 + 30
    
    def draw(self, state: str = 'idle', frame: int = 0, speech: str = ""):
        """主绘制入口"""
        self.c.delete('all')
        
        if state == 'sleeping':
            self._draw_sleeping(frame)
        elif state == 'eating':
            self._draw_eating(frame)
        elif state == 'happy':
            self._draw_happy(frame)
        elif state == 'sad':
            self._draw_sad()
        elif state == 'thinking':
            self._draw_thinking(frame)
        elif state == 'talking':
            self._draw_talking(frame)
        elif state == 'walking':
            self._draw_walking(frame)
        elif state == 'excited':
            self._draw_excited(frame)
        else:  # idle
            self._draw_idle(frame)
        
        if speech:
            self._draw_speech_bubble(speech)
    
    def _draw_idle(self, frame: int):
        """待机——轻微呼吸"""
        breathe = math.sin(frame * 0.1) * 2
        c, cx, cy = self.c, self.cx, self.cy
        y = cy + breathe
        
        # 阴影
        self._shadow(cx, cy + 120 + breathe * 0.3)
        
        # 后腿
        self._oval(cx-40, cy+70, cx-15, cy+110, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx+15, cy+70, cx+40, cy+110, fill=self.BODY, outline=self.BODY_DARK)
        
        # 前腿
        self._oval(cx-55, cy+65, cx-30, cy+110, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx+30, cy+65, cx+55, cy+110, fill=self.BODY, outline=self.BODY_DARK)
        
        # 身体
        self._oval(cx-75, cy+15, cx+75, cy+105, fill=self.BODY, outline=self.BODY_DARK)
        
        # 肚皮
        self._oval(cx-40, cy+30, cx+40, cy+90, fill=self.BELLY, outline='')
        
        # 小尾巴（短桩）
        self._oval(cx+65, cy+10, cx+82, cy+30, fill=self.BODY, outline=self.BODY_DARK)
        
        # 大蝙蝠耳
        self._ear(cx-50, cy-10, -1, breathe)
        self._ear(cx+50, cy-10, 1, breathe)
        
        # 脸
        self._oval(cx-48, cy+15, cx+48, cy+75, fill=self.BODY, outline=self.BODY_DARK)
        
        # 面罩
        self._oval(cx-32, cy+22, cx+32, cy+62, fill=self.MASK, outline='')
        
        # 眼睛 —— 大而圆
        self._eye(cx-22, cy+30, 'open', frame)
        self._eye(cx+22, cy+30, 'open', frame)
        
        # 鼻子
        self._oval(cx-12, cy+42, cx+12, cy+54, fill=self.NOSE, outline='')
        self._oval(cx-4, cy+45, cx+4, cy+49, fill='#cccccc', outline='')
        
        # 嘴
        self._arc(cx-16, cy+54, cx, cy+66, start=0, extent=-180, style='arc', outline=self.MASK_LIGHT, width=2)
        self._arc(cx, cy+54, cx+16, cy+66, start=180, extent=180, style='arc', outline=self.MASK_LIGHT, width=2)
        
        # 舌头（偶尔）
        if frame % 120 < 20:
            self._tongue(cx, cy+62)
    
    def _draw_sleeping(self, frame: int):
        """睡觉"""
        c, cx, cy = self.c, self.cx, self.cy
        
        # 身体——侧躺
        self._shadow(cx, cy+100)
        self._oval(cx-80, cy+50, cx+50, cy+115, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx-50, cy+70, cx+30, cy+105, fill=self.BELLY, outline='')
        
        # 腿——蜷缩
        self._oval(cx-65, cy+85, cx-30, cy+120, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx-20, cy+85, cx+15, cy+120, fill=self.BODY, outline=self.BODY_DARK)
        
        # 尾巴
        self._oval(cx+40, cy+60, cx+55, cy+80, fill=self.BODY, outline=self.BODY_DARK)
        
        # 耳朵——耷拉
        self._ear_floppy(cx-35, cy+35, -1)
        self._ear_floppy(cx+15, cy+35, 1)
        
        # 脸——侧着
        self._oval(cx-45, cy+45, cx+20, cy+90, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx-30, cy+52, cx+12, cy+78, fill=self.MASK, outline='')
        
        # 闭眼
        self._eye(cx-15, cy+55, 'closed', frame)
        self._eye(cx+3, cy+55, 'closed', frame)
        
        # 鼻子
        self._oval(cx-6, cy+62, cx+8, cy+72, fill=self.NOSE, outline='')
        
        # Zzz
        zzz_x = cx + 30
        zzz_y = cy + 30
        for i, (s, clr) in enumerate([(12, '#555'), (9, '#777'), (7, '#999')]):
            c.create_text(zzz_x + i*12, zzz_y - i*10, text='z',
                         font=('Comic Sans MS', s, 'bold'), fill=clr)
        
        if frame % 200 < 100:
            c.create_text(cx+55, cy+50, text='💤', font=('Segoe UI Emoji', 14))
    
    def _draw_eating(self, frame: int):
        """吃东西——嘴在动"""
        self._draw_idle(frame)
        # 食物
        food_x = self.cx - 50 + math.sin(frame * 0.3) * 10
        food_y = self.cy + 55
        self.c.create_oval(food_x-6, food_y-3, food_x+6, food_y+9, fill='#D4956B', outline='')
        self.c.create_text(self.cx + 60, self.cy - 10, text='🍖', font=('Segoe UI Emoji', 18))
        if frame % 40 < 20:
            self.c.create_text(self.cx + 70, self.cy - 25, text='😋', font=('Segoe UI Emoji', 14))
    
    def _draw_happy(self, frame: int):
        """开心——大嘴笑"""
        c, cx, cy = self.c, self.cx, self.cy
        self._draw_idle(frame)
        
        # 大嘴笑
        c.create_arc(cx-18, cy+52, cx+18, cy+72, start=0, extent=-180,
                    fill=self.TONGUE, outline=self.MASK_LIGHT, width=2)
        
        # 爱心
        c.create_text(cx+75, cy-20, text='❤️', font=('Segoe UI Emoji', 16))
        if frame % 60 < 30:
            c.create_text(cx+60, cy-35, text='💕', font=('Segoe UI Emoji', 10))
    
    def _draw_sad(self):
        """难过——耷拉耳朵，垂眼"""
        c, cx, cy = self.c, self.cx, self.cy
        self._shadow(cx, cy+120)
        
        # 身体（缩着）
        self._oval(cx-70, cy+30, cx+70, cy+110, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx-38, cy+70, cx+38, cy+115, fill=self.BELLY, outline='')
        
        # 腿（缩）
        self._oval(cx-50, cy+75, cx-25, cy+112, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx+25, cy+75, cx+50, cy+112, fill=self.BODY, outline=self.BODY_DARK)
        
        # 耷拉耳朵
        self._ear_floppy(cx-45, cy, -1)
        self._ear_floppy(cx+45, cy, 1)
        
        # 脸
        self._oval(cx-45, cy+25, cx+45, cy+80, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx-30, cy+32, cx+30, cy+65, fill=self.MASK, outline='')
        
        # 垂眼
        self._eye(cx-20, cy+38, 'sad', 0)
        self._eye(cx+20, cy+38, 'sad', 0)
        
        # 鼻子
        self._oval(cx-10, cy+48, cx+10, cy+58, fill=self.NOSE, outline='')
        
        # 瘪嘴
        c.create_arc(cx-12, cy+58, cx+12, cy+68, start=0, extent=180, style='arc',
                    outline=self.MASK_LIGHT, width=2)
        
        c.create_text(cx-55, cy+5, text='😢', font=('Segoe UI Emoji', 12))
    
    def _draw_thinking(self, frame: int):
        """思考——歪头"""
        c, cx, cy = self.c, self.cx, self.cy
        
        self._shadow(cx, cy+120)
        
        # 身体
        self._oval(cx-72, cy+20, cx+72, cy+105, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx-35, cy+40, cx+35, cy+90, fill=self.BELLY, outline='')
        
        # 腿
        self._oval(cx-52, cy+68, cx-28, cy+108, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx+28, cy+68, cx+52, cy+108, fill=self.BODY, outline=self.BODY_DARK)
        
        # 耳朵——竖起一只
        self._ear(cx-46, cy-5, -1)
        self._ear_floppy(cx+42, cy+5, 1)
        
        # 脸——微歪
        self._oval(cx-44, cy+22, cx+44, cy+78, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx-28, cy+30, cx+28, cy+65, fill=self.MASK, outline='')
        
        # 思考眼——向上看
        self._eye(cx-16, cy+28, 'look_up', frame)
        self._eye(cx+16, cy+28, 'look_up', frame)
        
        # 鼻子
        self._oval(cx-10, cy+44, cx+10, cy+56, fill=self.NOSE, outline='')
        
        # 思考标记
        c.create_text(cx+65, cy-20, text='🤔', font=('Segoe UI Emoji', 16))
        c.create_text(cx+80, cy-35, text='💭', font=('Segoe UI Emoji', 10))
    
    def _draw_talking(self, frame: int):
        """说话——嘴一张一合"""
        c, cx, cy = self.c, self.cx, self.cy
        self._draw_idle(frame if frame else 0)
        
        # 波线
        for i in range(3):
            c.create_line(cx+55+i*10, cy-15 + math.sin(frame*0.3 + i*0.8)*4,
                         cx+55+i*10+6, cy-15 + math.sin(frame*0.3 + i*0.8)*4,
                         fill=self.MASK_LIGHT, width=2)
    
    def _draw_walking(self, frame: int):
        """走路——腿交替"""
        c, cx, cy = self.c, self.cx, self.cy
        phase = math.sin(frame * 0.3)
        
        self._shadow(cx, cy+115 + abs(phase)*3)
        
        # 后腿交替
        self._oval(cx-40, cy+65-phase*5, cx-15, cy+105-phase*3, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx+15, cy+65+phase*5, cx+40, cy+105+phase*3, fill=self.BODY, outline=self.BODY_DARK)
        
        # 前腿交替
        self._oval(cx-55, cy+60+phase*5, cx-30, cy+108+phase*3, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx+30, cy+60-phase*5, cx+55, cy+108-phase*3, fill=self.BODY, outline=self.BODY_DARK)
        
        # 身体（上下弹）
        bounce = abs(phase) * 3
        self._oval(cx-75, cy+12-bounce, cx+75, cy+100-bounce, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx-40, cy+28-bounce, cx+40, cy+85-bounce, fill=self.BELLY, outline='')
        
        # 尾巴
        self._oval(cx+65, cy+8-bounce, cx+82, cy+28-bounce, fill=self.BODY, outline=self.BODY_DARK)
        
        # 耳朵
        self._ear(cx-48, cy-15-bounce, -1)
        self._ear(cx+48, cy-15-bounce, 1)
        
        # 脸
        self._oval(cx-48, cy+12-bounce, cx+48, cy+70-bounce, fill=self.BODY, outline=self.BODY_DARK)
        self._oval(cx-32, cy+20-bounce, cx+32, cy+58-bounce, fill=self.MASK, outline='')
        
        self._eye(cx-20, cy+28-bounce, 'open', 0)
        self._eye(cx+20, cy+28-bounce, 'open', 0)
        
        # 鼻子
        self._oval(cx-12, cy+40-bounce, cx+12, cy+52-bounce, fill=self.NOSE, outline='')
        
        # 张嘴（喘气）
        self._tongue(cx, cy+60-bounce)
        c.create_text(cx+65+phase*5, cy-15-bounce, text='🐾', font=('Segoe UI Emoji', 8))
    
    def _draw_excited(self, frame: int):
        """兴奋——蹦跳"""
        bounce = abs(math.sin(frame * 0.4)) * 12
        self._draw_happy(frame)
        self.c.create_text(self.cx+55, self.cy-30-bounce, text='🎉', font=('Segoe UI Emoji', 16))
    
    # ── 辅助绘制 ──
    
    def _shadow(self, cx, cy):
        self.c.create_oval(cx-60, cy-3, cx+60, cy+8, fill='#e0e0e0', outline='')
    
    def _oval(self, x1, y1, x2, y2, fill, outline, width=1):
        self.c.create_oval(x1, y1, x2, y2, fill=fill, outline=outline, width=width)
    
    def _arc(self, *a, **kw):
        self.c.create_arc(*a, **kw)
    
    def _ear(self, cx, y, direction, breathe=0):
        """大蝙蝠耳——竖起来"""
        s = direction  # 1 or -1
        points = [
            cx-3*s, y+20, cx-18*s, y-25, cx-8*s, y-30, cx-8*s, y+5,
            cx-10*s, y+10
        ]
        # 外耳
        self.c.create_polygon(*points, fill=self.MASK, outline=self.MASK_LIGHT, width=1, smooth=True)
        # 内耳
        inner = [cx-2*s, y+18, cx-14*s, y-18, cx-8*s, y+2]
        self.c.create_polygon(*inner, fill=self.EAR_IN, outline='', smooth=True)
    
    def _ear_floppy(self, cx, y, direction):
        """耷拉耳朵"""
        s = direction
        self.c.create_polygon(
            cx, y+5, cx-12*s, y+15, cx-8*s, y+40, cx+2*s, y+25,
            fill=self.MASK, outline=self.MASK_LIGHT, width=1, smooth=True
        )
    
    def _eye(self, cx, y, style, frame):
        """画眼睛"""
        if style == 'open':
            self.c.create_oval(cx-7, y-5, cx+7, y+9, fill='white', outline=self.EYE, width=1)
            self.c.create_oval(cx-3, y-2, cx+3, y+5, fill=self.EYE, outline='')
            self.c.create_oval(cx-2, y-1, cx+1, y+2, fill=self.EYE_HIGHLIGHT, outline='')
        elif style == 'closed':
            self.c.create_arc(cx-7, y, cx+7, y+7, start=0, extent=-180, fill=self.EYE, outline='')
        elif style == 'sad':
            self.c.create_oval(cx-7, y-2, cx+7, y+8, fill='white', outline=self.EYE, width=1)
            self.c.create_oval(cx-3, y+1, cx+3, y+6, fill=self.EYE, outline='')
            self.c.create_oval(cx-2, y+2, cx+1, y+4, fill='#cccccc', outline='')
        elif style == 'look_up':
            self.c.create_oval(cx-7, y-3, cx+7, y+9, fill='white', outline=self.EYE, width=1)
            self.c.create_oval(cx-3, y-2, cx+3, y+4, fill=self.EYE, outline='')
            self.c.create_oval(cx-2, y-1, cx+1, y+1, fill=self.EYE_HIGHLIGHT, outline='')
    
    def _tongue(self, cx, y):
        """小舌头"""
        self.c.create_oval(cx-4, y-2, cx+6, y+8, fill=self.TONGUE, outline=self.TONGUE, width=1)
        self.c.create_line(cx, y, cx+2, y+6, fill='#d07078', width=1)
    
    def _draw_speech_bubble(self, text: str):
        """气泡对话框"""
        text = text[:80]
        c = self.c
        bx = self.cx + 65
        by = self.cy - 60
        
        # 测量文字
        font = ('Microsoft YaHei', 10)
        c.itemconfigure('bubble', state='hidden') if self.c.find_withtag('bubble') else None
        
        # 气泡背景
        padding = 8
        text_w = min(len(text) * 9, 200)
        text_h = 30 + (len(text) // 20) * 16
        
        # 气泡圆角矩形（用多个形状拼）
        c.create_oval(bx, by, bx+16, by+12, fill='white', outline='#ddd', tags=('bubble',))
        c.create_oval(bx+text_w+padding*2-16, by, bx+text_w+padding*2, by+12, fill='white', outline='#ddd', tags=('bubble',))
        c.create_oval(bx, by+text_h-12, bx+12, by+text_h, fill='white', outline='#ddd', tags=('bubble',))
        c.create_oval(bx+text_w+padding*2-12, by+text_h-12, bx+text_w+padding*2, by+text_h, fill='white', outline='#ddd', tags=('bubble',))
        c.create_rectangle(bx+6, by, bx+text_w+padding*2-6, by+text_h, fill='white', outline='', tags=('bubble',))
        c.create_rectangle(bx, by+6, bx+text_w+padding*2, by+text_h-6, fill='white', outline='', tags=('bubble',))
        c.create_rectangle(bx+2, by+2, bx+text_w+padding*2-2, by+text_h-2, outline='#ddd', tags=('bubble',))
        
        # 气泡尾巴
        c.create_polygon(bx+10, by+text_h-6, bx+22, by+text_h+12, bx+30, by+text_h,
                        fill='white', outline='#ddd', tags=('bubble',))
        
        # 文字
        lines = [text[i:i+18] for i in range(0, len(text), 18)]
        for i, line in enumerate(lines[:3]):
            c.create_text(bx+padding+text_w//2+6, by+padding+8 + i*16, text=line,
                         font=font, fill='#333', justify='center', tags=('bubble',))


# ═══════════════════════════════════════════════
# v3 脑连接
# ═══════════════════════════════════════════════

class V3Brain:
    """宠物背后的脑子——连接 super_brain_server"""
    
    def __init__(self, url: str = V3_URL):
        self.url = url
        self.online = False
        self._check()
    
    def _check(self):
        try:
            req = urllib.request.Request("http://localhost:8081/v1/engine/stats", 
                                        headers={"User-Agent": "FrenchiePet/2.0"})
            with urllib.request.urlopen(req, timeout=2):
                self.online = True
        except:
            self.online = False
    
    def chat(self, message: str, personality: str = "", timeout: int = 30) -> str:
        """跟 v3 对话"""
        if not self.online:
            self._check()
        if not self.online:
            return self._offline_reply(message)
        
        try:
            body = json.dumps({
                "model": "blackhole-superbrain-v2",
                "messages": [
                    {"role": "system", "content": (
                        "你是殷竺欣的桌宠法斗——叫'豆包'。性格：懒、馋、粘人、傲娇。"
                        "说话像宠物狗的语气，加一点傲娇。回复极短（20字以内），用emoji。"
                        f"当前心情: {personality}"
                    )},
                    {"role": "user", "content": message}
                ],
                "stream": False
            }).encode("utf-8")
            req = urllib.request.Request(self.url, data=body,
                                        headers={"Content-Type": "application/json", "User-Agent": "FrenchiePet/2.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "汪～")
            return content[:80]
        except Exception:
            return self._offline_reply(message)
    
    def _offline_reply(self, message: str) -> str:
        """v3 不在线时的离线回复"""
        replies = {
            "饿": ["呜...肚子咕咕叫🥺", "饿了...", "想吃肉肉..."],
            "玩": ["汪！来玩！🐾", "追我呀～", "扔球球！"],
            "睡": ["zzz...呼...💤", "困了...", "别吵...zzZ"],
            "摸": ["呼噜呼噜...😌", "再摸一会～", "舒服...❤️"],
            "default": ["汪～🐾", "嗯？", "汪！", "🦴", "哼～"]
        }
        for k, v in replies.items():
            if k in message:
                return random.choice(v)
        return random.choice(replies["default"])


# ═══════════════════════════════════════════════
# 宠物主类
# ═══════════════════════════════════════════════

class FrenchiePet:
    """法斗桌宠——有灵魂的桌面伙伴"""
    
    def __init__(self):
        self.stats = PetStats()
        self._load_state()
        self.brain = V3Brain()
        
        # 状态
        self.state = 'idle'
        self.frame = 0
        self.speech = ""
        self.speech_timer = 0
        self.behavior_timer = 0
        self.last_decay = time.time()
        self.running = True
        
        # 窗口
        self.win_w = 300
        self.win_h = 360
        self._create_window()
        
        # 动画循环
        self._animate()
    
    def _load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.stats = PetStats.from_dict(data.get("stats", {}))
                # 离线时间衰减
                last = data.get("stats", {}).get("updated", "")
                if last:
                    try:
                        last_dt = datetime.fromisoformat(last)
                        elapsed = (datetime.now() - last_dt).total_seconds() / 60
                        if elapsed > 0 and elapsed < 1440:  # 最多衰减24小时
                            self.stats.decay(elapsed)
                    except:
                        pass
            except:
                pass
    
    def _save_state(self):
        try:
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump({"stats": self.stats.to_dict()}, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def _create_window(self):
        self.root = tk.Tk()
        self.root.title('豆包 🐾')
        self.root.geometry(f'{self.win_w}x{self.win_h}+1000+400')
        
        # 透明背景
        self.root.attributes('-transparentcolor', '#010101')
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)
        self.root.configure(bg='#010101')
        
        # 画布
        self.canvas = tk.Canvas(self.root, width=self.win_w, height=self.win_h,
                                bg='#010101', highlightthickness=0)
        self.canvas.pack()
        
        # 画师
        self.drawer = FrenchieDrawer(self.canvas, self.win_w, self.win_h)
        
        # 事件绑定
        self.canvas.bind('<Button-1>', self._on_click)
        self.canvas.bind('<Button-3>', self._on_right_click)
        self._bind_drag()
        
        # 右键菜单
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="🍖 喂食", command=self._feed)
        self.menu.add_command(label="🎾 玩耍", command=self._play)
        self.menu.add_command(label="💤 睡觉", command=self._sleep_toggle)
        self.menu.add_command(label="❤️ 摸摸", command=self._pet)
        self.menu.add_separator()
        self.menu.add_command(label="📊 状态", command=self._show_stats)
        self.menu.add_command(label="🦞 跟云哥聊聊", command=self._talk_to_v3)
        self.menu.add_separator()
        self.menu.add_command(label="❌ 退出", command=self._quit)
    
    def _bind_drag(self):
        self._drag = {'x': 0, 'y': 0, 'on': False}
        def press(e):
            self._drag['x'] = e.x_root - self.root.winfo_x()
            self._drag['y'] = e.y_root - self.root.winfo_y()
            self._drag['on'] = True
        def drag(e):
            if self._drag['on']:
                self.root.geometry(f'+{e.x_root - self._drag["x"]}+{e.y_root - self._drag["y"]}')
        def release(e):
            self._drag['on'] = False
        self.canvas.bind('<ButtonPress-1>', press, add='+')
        self.canvas.bind('<B1-Motion>', drag, add='+')
        self.canvas.bind('<ButtonRelease-1>', release, add='+')
    
    # ── 交互 ──
    
    def _on_click(self, event):
        self.stats.pet()
        self.stats.total_interactions += 1
        mood = self.stats.mood()
        if mood == 'hungry':
            self.state = 'sad'
            self.speech = "饿了...🥺"
        elif mood == 'happy':
            self.state = 'happy'
            self.speech = random.choice(["汪～❤️", "好开心！", "再摸一下～"])
        else:
            self.state = 'happy'
            self.speech = "汪！🐾"
        self.speech_timer = 60  # 2秒
    
    def _on_right_click(self, event):
        self.menu.post(event.x_root, event.y_root)
    
    def _feed(self):
        self.stats.feed()
        self.state = 'eating'
        self.speech = random.choice(["好吃！😋", "肉肉！🍖", "再来一份！", "吧唧吧唧..."])
        self.speech_timer = 90
        self._save_state()
    
    def _play(self):
        self.stats.play()
        self.state = 'excited'
        self.speech = random.choice(["追我呀！🎾", "汪！快点扔！", "哈哈！🐾"])
        self.speech_timer = 90
        self._save_state()
    
    def _sleep_toggle(self):
        if self.state == 'sleeping':
            self.state = 'idle'
            self.speech = "醒了...😴"
        else:
            self.state = 'sleeping'
            self.speech = "zzz...💤"
        self.speech_timer = 60
        self._save_state()
    
    def _pet(self):
        self.stats.pet()
        self.state = 'happy'
        self.speech = random.choice(["呼噜呼噜...😌", "舒服～", "别停...❤️", "汪～"])
        self.speech_timer = 75
        self._save_state()
    
    def _show_stats(self):
        s = self.stats
        self.speech = f"🍖{s.hunger:.0f} ⚡{s.energy:.0f} 😊{s.happiness:.0f} ❤️{s.affection:.0f}"
        self.speech_timer = 120
        self.state = 'thinking'
    
    def _talk_to_v3(self):
        """跟 v3 对话——宠物带脑子"""
        self.state = 'thinking'
        self.speech = "让我想想...🤔"
        self.speech_timer = 40
        
        def ask_v3():
            mood_map = {
                'hungry': '我饿了',
                'tired': '我好困',
                'sad': '我不开心',
                'happy': '我超开心',
                'content': '还行吧',
                'meh': '一般般'
            }
            mood_text = mood_map.get(self.stats.mood(), '没什么')
            prompt = f"主人点我了。我现在{mood_text}。说一句傲娇的话。"
            reply = self.brain.chat(prompt, personality=self.stats.mood())
            self.state = 'talking'
            self.speech = reply
            self.speech_timer = 120
        
        threading.Thread(target=ask_v3, daemon=True).start()
    
    def _quit(self):
        self.running = False
        self._save_state()
        self.root.destroy()
    
    # ── 动画循环 ──
    
    def _animate(self):
        if not self.running:
            return
        
        self.frame += 1
        
        # 属性衰减
        now = time.time()
        elapsed = (now - self.last_decay) / 60
        if elapsed >= 0.5:
            self.stats.decay(elapsed)
            self.last_decay = now
        
        # 自主行为
        self.behavior_timer += 1
        if self.behavior_timer > BEHAVIOR_INTERVAL * ANIM_FPS:
            self.behavior_timer = 0
            self._auto_behavior()
        
        # 睡觉时恢复精力
        if self.state == 'sleeping':
            self.stats.sleep(1/ANIM_FPS)
            self.speech = ""
        elif self.state != 'talking' and self.stats.energy < 10 and random.random() < 0.01:
            self.state = 'sleeping'
            self.speech_timer = 0
        
        # 气泡计时
        if self.speech_timer > 0:
            self.speech_timer -= 1
            if self.speech_timer <= 0:
                self.speech = ""
                if self.state in ('talking', 'thinking'):
                    self.state = 'idle'
        
        # 如果心情变差，有时自己恢复 idle
        if self.state == 'sad' and self.speech_timer <= 0:
            if random.random() < 0.03:
                self.state = 'idle'
        
        # 重绘
        self.drawer.draw(self.state, self.frame, self.speech)
        
        # 状态标签
        mood_emoji = {'hungry': '🍖', 'tired': '💤', 'sad': '😢', 'happy': '😊', 'content': '😌', 'meh': '😐'}
        emoji = mood_emoji.get(self.stats.mood(), '🐾')
        
        if self.stats.hunger < 30:
            emoji = '🍖'
        
        self.canvas.create_text(25, 15, text=emoji, font=('Segoe UI Emoji', 14),
                               fill='#fff', tags=('status',))
        
        # 亲密度爱心
        if self.stats.affection > 80:
            self.canvas.create_text(self.win_w-25, 15, text='💕', font=('Segoe UI Emoji', 12),
                                   tags=('status',))
        
        # v3 在线指示
        if self.brain.online:
            self.canvas.create_text(self.win_w-15, 30, text='🟢', font=('Segoe UI Emoji', 6),
                                    tags=('status',))
        
        self.root.after(1000 // ANIM_FPS, self._animate)
    
    def _auto_behavior(self):
        """自主行为——宠物自己决定做什么"""
        if self.speech_timer > 0:
            return  # 别打断当前
        
        mood = self.stats.mood()
        
        if mood == 'hungry':
            self.state = 'sad'
            self.speech = random.choice(["饿了...🥺", "肚子叫了...", "想吃东西..."])
        elif mood == 'tired':
            self.state = 'sleeping'
        elif mood == 'sad':
            self.state = 'sad'
            self.speech = "好无聊..."
        elif mood == 'happy':
            if random.random() < 0.5:
                self.state = 'walking'
                # 模拟移动
                x = self.root.winfo_x() + random.randint(-30, 30)
                y = self.root.winfo_y() + random.randint(-10, 10)
                try:
                    self.root.geometry(f'+{x}+{y}')
                except:
                    pass
            else:
                self.state = 'happy'
                self.speech = random.choice(["汪～🐾", "今天真不错！", "❤️"])
        else:
            if random.random() < 0.3:
                self.state = 'walking'
                x = self.root.winfo_x() + random.randint(-20, 20)
                y = self.root.winfo_y()
                try:
                    self.root.geometry(f'+{x}+{y}')
                except:
                    pass
        
        if self.speech:
            self.speech_timer = int(random.uniform(60, 120))
        
        self._save_state()
    
    def run(self):
        self.root.mainloop()


# ═══════════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════════

if __name__ == '__main__':
    import io, sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print('[Frenchie] 法斗桌宠 v2 启动中...')
    print('   名字: 豆包')
    print('   性格: 懒/馋/粘人/傲娇')
    print('   脑子: v3 super_brain_server (localhost:8081)')
    print('   右键: 喂食/玩耍/睡觉/状态/聊天')
    pet = FrenchiePet()
    pet.run()
