"""
v3 Pet Engine — Achilles死标值驱动的法斗引擎
==============================================
从achilles参数库读取动作/情绪/口型/物理标值
→ 映射为法斗V6点阵的实时变换
→ 时间驱动 = 活的法斗

架构: achilles参数 → 骨架变换 → 点阵重投影 → Canvas渲染
"""
import json
import math
import time
import sys

# 偷懒: 不import achilles (太大了), 直接定义pet专用的精简标值映射
sys.path.insert(0, r'C:\Users\Administrator\brain_1GB')

class SkeletonJoint:
    """法斗骨架关节点"""
    def __init__(self, name, x, y, z, parent=None):
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.base = (x, y, z)
        self.parent = parent
        self.children = []
        if parent:
            parent.children.append(self)
    
    def world_pos(self):
        if self.parent:
            px, py, pz = self.parent.world_pos()
            return (px + self.x, py + self.y, pz + self.z)
        return (self.x, self.y, self.z)

class FrenchieSkeleton:
    """法斗骨架: 7点简易骨架 → 驱动点阵变形"""
    
    def __init__(self):
        # 骨架定义 (与V6 buildFrenchie坐标系一致)
        # x=左右, y=上下, z=前后
        self.root = SkeletonJoint("root", 0, 0, 0)
        self.spine = SkeletonJoint("spine", 0, 0, 0, self.root)
        self.neck = SkeletonJoint("neck", 0, -60, 40, self.spine)
        self.head = SkeletonJoint("head", 0, -30, 25, self.neck)
        self.nose = SkeletonJoint("nose", 0, -5, 18, self.head)
        
        # 四肢 (相对于spine)
        self.hip = SkeletonJoint("hip", 0, 25, -10, self.spine)
        self.leg_L = SkeletonJoint("leg_L", -30, 40, 0, self.hip)
        self.leg_R = SkeletonJoint("leg_R", 30, 40, 0, self.hip)
        self.paw_L = SkeletonJoint("paw_L", 0, 20, 5, self.leg_L)
        self.paw_R = SkeletonJoint("paw_R", 0, 20, 5, self.leg_R)
        
        self.front_hip = SkeletonJoint("front_hip", 0, -10, 55, self.spine)
        self.arm_L = SkeletonJoint("arm_L", -25, 30, 5, self.front_hip)
        self.arm_R = SkeletonJoint("arm_R", 25, 30, 5, self.front_hip)
        self.front_paw_L = SkeletonJoint("front_paw_L", 0, 20, 3, self.arm_L)
        self.front_paw_R = SkeletonJoint("front_paw_R", 0, 20, 3, self.arm_R)
        
        # 耳朵
        self.ear_L = SkeletonJoint("ear_L", -20, -15, 8, self.head)
        self.ear_R = SkeletonJoint("ear_R", 20, -15, 8, self.head)
        self.ear_tip_L = SkeletonJoint("ear_tip_L", 0, -25, 5, self.ear_L)
        self.ear_tip_R = SkeletonJoint("ear_tip_R", 0, -25, 5, self.ear_R)
        
        # 尾巴
        self.tail_base = SkeletonJoint("tail_base", 0, 30, -15, self.spine)
        self.tail_tip = SkeletonJoint("tail_tip", 0, -5, 8, self.tail_base)
        
        # 面部特征
        self.mouth = SkeletonJoint("mouth", 0, -10, 22, self.head)
        self.eye_L = SkeletonJoint("eye_L", -18, -5, 14, self.head)
        self.eye_R = SkeletonJoint("eye_R", 18, -5, 14, self.head)
        
        self.joints = {}
        self._collect_joints(self.root)
    
    def _collect_joints(self, joint):
        self.joints[joint.name] = joint
        for child in joint.children:
            self._collect_joints(child)
    
    def reset(self):
        for j in self.joints.values():
            j.x, j.y, j.z = j.base
    
    def to_dict(self):
        return {name: {"x": j.x, "y": j.y, "z": j.z} for name, j in self.joints.items()}


# ═══════════════════════════════════════════
# 宠物动作库 (从achilles CHARACTER_ACTIONS 精简映射)
# ═══════════════════════════════════════════

PET_ACTIONS = {
    "idle": {
        "name": "待机",
        "duration_s": 2.0, "loop": True,
        "spine": {"y_sway": 3, "period_s": 2.0},
        "head": {"tilt_deg": 3, "period_s": 3.5},
        "ears": {"flop_deg": 5, "period_s": 1.5},
        "tail": {"wag_deg": 10, "period_s": 0.8},
        "breath": {"amplitude_mm": 3, "period_s": 2.0},
        "eye": {"blink_every_s": 3.0, "blink_duration_s": 0.15},
        "mouth": "M_CLOSED",
        "body_bounce_mm": 0,
    },
    "walk": {
        "name": "走路",
        "duration_s": 1.5, "loop": True,
        "leg_L": {"phase_deg": 0, "amplitude_deg": 25},
        "leg_R": {"phase_deg": 180, "amplitude_deg": 25},
        "arm_L": {"phase_deg": 180, "amplitude_deg": 20},
        "arm_R": {"phase_deg": 0, "amplitude_deg": 20},
        "body_bounce_mm": 15,
        "tail": {"wag_deg": 15, "period_s": 0.5},
        "head": {"bob_mm": 10},
        "mouth": "M_SLIGHT",
    },
    "run": {
        "name": "跑",
        "duration_s": 0.7, "loop": True,
        "leg_L": {"phase_deg": 0, "amplitude_deg": 40},
        "leg_R": {"phase_deg": 180, "amplitude_deg": 40},
        "arm_L": {"phase_deg": 180, "amplitude_deg": 35},
        "arm_R": {"phase_deg": 0, "amplitude_deg": 35},
        "body_bounce_mm": 40,
        "tail": {"wag_deg": 20, "period_s": 0.3},
        "head": {"bob_mm": 20},
        "mouth": "M_WIDE",
        "ear_flop_mm": 20,
    },
    "sit": {
        "name": "坐下",
        "duration_s": 1.0, "transition": True,
        "hip_drop_mm": 40,
        "leg_L": {"bend_deg": 90},
        "leg_R": {"bend_deg": 90},
        "spine": {"tilt_deg": 15},
        "head": {"tilt_deg": 5},
        "tail": {"wag_deg": 8, "period_s": 1.5},
        "mouth": "M_CLOSED",
    },
    "sleep": {
        "name": "睡觉",
        "duration_s": 3.0, "loop": True,
        "spine": {"compress_mm": 30},
        "leg_L": {"bend_deg": 45},
        "leg_R": {"bend_deg": 45},
        "arm_L": {"bend_deg": 60},
        "arm_R": {"bend_deg": 60},
        "head": {"tilt_deg": -20, "drop_mm": 30},
        "body_bounce_mm": 0,
        "eye": {"closed": True},
        "mouth": "M_CLOSED",
        "breath": {"amplitude_mm": 8, "period_s": 3.0},
        "tail": {"wag_deg": 0},
    },
    "happy": {
        "name": "开心",
        "duration_s": 1.0, "loop": True,
        "tail": {"wag_deg": 30, "period_s": 0.25},
        "body_bounce_mm": 10,
        "head": {"tilt_deg": 8, "period_s": 0.8},
        "ears": {"flop_deg": 15, "period_s": 0.5},
        "mouth": "M_WIDE",
        "eye": {"blink_every_s": 1.5},
        "spine": {"y_sway": 8, "period_s": 0.6},
    },
    "excited": {
        "name": "兴奋",
        "duration_s": 0.5, "loop": True,
        "tail": {"wag_deg": 45, "period_s": 0.12},
        "body_bounce_mm": 25,
        "head": {"tilt_deg": 12, "period_s": 0.4},
        "ears": {"flop_deg": 25, "period_s": 0.3},
        "mouth": "M_WIDE",
        "eye": {"blink_every_s": 1.0, "wide": True},
        "leg_L": {"phase_deg": 0, "amplitude_deg": 10},
        "leg_R": {"phase_deg": 180, "amplitude_deg": 10},
    },
    "sad": {
        "name": "难过",
        "duration_s": 2.0, "loop": True,
        "head": {"tilt_deg": -10, "drop_mm": 15},
        "tail": {"wag_deg": 3, "period_s": 2.0},
        "ears": {"flop_deg": -15},
        "body_bounce_mm": 0,
        "eye": {"blink_every_s": 5.0, "half_closed": True},
        "mouth": "M_SLIGHT",
        "spine": {"compress_mm": 10},
    },
    "eat": {
        "name": "吃东西",
        "duration_s": 0.8, "loop": True,
        "head": {"nod_deg": 15, "period_s": 0.5},
        "mouth": "M_ROUND_OPEN",
        "jaw": {"open_mm": 5},
        "tail": {"wag_deg": 15, "period_s": 0.4},
        "ears": {"flop_deg": 10},
    },
    "think": {
        "name": "想事情",
        "duration_s": 2.0, "loop": True,
        "head": {"tilt_deg": 15, "hold": True},
        "eye": {"blink_every_s": 4.0},
        "ears": {"flop_deg": 8},
        "tail": {"wag_deg": 4, "period_s": 2.5},
        "mouth": "M_CLOSED",
        "body_bounce_mm": 0,
        "spine": {"y_sway": 2, "period_s": 4.0},
    },
}

# 口型映射
MOUTH_SCALE = {
    "M_CLOSED": 1.0,
    "M_SLIGHT": 0.3,
    "M_HALF": 0.5,
    "M_WIDE": 0.8,
    "M_ROUND": 0.6,
    "M_STRETCHED": 0.4,
    "M_TIGHT": 0.2,
    "M_TEETH_LIP": 0.1,
    "M_TEETH": 0.3,
    "M_ROUND_OPEN": 0.7,
    "M_SEMI_WIDE": 0.65,
}

# ═══════════════════════════════════════════
# 宠物状态引擎
# ═══════════════════════════════════════════

class PetState:
    """宠物状态 — 属性衰减 + 自主行为"""
    def __init__(self):
        self.hunger = 50.0      # 0=饱 100=饿
        self.energy = 80.0      # 0=累 100=精神
        self.happiness = 60.0   # 0=难过 100=开心
        self.bond = 50.0        # 亲密度
        self.current_action = "idle"
        self.action_start_time = time.time()
        self.last_blink = time.time()
        self.blinking = False
        self.blink_start = 0
        
        self.action_history = []
    
    def decay(self, dt_s):
        """每分钟自然衰减"""
        decay_rate = dt_s / 60.0
        self.hunger = min(100, self.hunger + 2 * decay_rate)
        self.energy = max(0, self.energy - 1 * decay_rate)
        self.happiness = max(0, self.happiness - 0.5 * decay_rate)
    
    def decide_action(self):
        """自主行为决策"""
        now = time.time()
        action = PET_ACTIONS.get(self.current_action, PET_ACTIONS["idle"])
        duration = action.get("duration_s", 2.0)
        
        # 当前动作还在执行中（非loop动作不被打断）
        if not action.get("loop") and now - self.action_start_time < duration:
            return self.current_action
        
        # 饥饿优先（打断任何动作）
        if self.hunger > 70:
            if self.current_action != "eat":
                return "eat"
            elif now - self.action_start_time > 3.0:  # 吃了3秒还没饱，继续
                return "eat"
        
        # 疲惫驱动
        if self.energy < 20:
            return "sleep"
        
        # 开心驱动
        if self.happiness > 80:
            return "happy"
        
        # 难过驱动
        if self.happiness < 20:
            return "sad"
        
        # 随机小动作
        import random
        r = random.random()
        if r < 0.3:
            return "idle"
        elif r < 0.5:
            return "think"
        elif r < 0.7:
            return "walk"
        else:
            return "idle"
    
    def set_action(self, action_name):
        if action_name in PET_ACTIONS:
            self.current_action = action_name
            self.action_start_time = time.time()
            self.action_history.append((action_name, time.time()))
            if len(self.action_history) > 100:
                self.action_history = self.action_history[-50:]
    
    def interact(self, interaction_type):
        """互动: feed/play/pet"""
        if interaction_type == "feed":
            self.hunger = max(0, self.hunger - 30)
            self.happiness = min(100, self.happiness + 10)
            self.bond = min(100, self.bond + 5)
            self.set_action("eat")
        elif interaction_type == "play":
            self.happiness = min(100, self.happiness + 15)
            self.energy = max(0, self.energy - 10)
            self.bond = min(100, self.bond + 8)
            self.set_action("excited")
        elif interaction_type == "pet":
            self.happiness = min(100, self.happiness + 10)
            self.bond = min(100, self.bond + 3)
            self.set_action("happy")


# ═══════════════════════════════════════════
# 骨骼动画器 — 死标值 → 骨骼变形 → JSON输出
# ═══════════════════════════════════════════

class PetAnimator:
    """把PET_ACTIONS的标值应用到骨架"""
    
    def __init__(self):
        self.skeleton = FrenchieSkeleton()
        self.state = PetState()
        self._anim_t = 0.0
    
    def apply_action(self, action_name, anim_t, dt_s):
        """应用动作到骨架"""
        action = PET_ACTIONS.get(action_name, PET_ACTIONS["idle"])
        skel = self.skeleton
        skel.reset()
        
        t = anim_t
        
        # ─── 全身呼吸 ───
        breath = action.get("breath", {})
        if breath:
            amp = breath.get("amplitude_mm", 3)
            period = breath.get("period_s", 2.0)
            breath_offset = math.sin(t * 2 * math.pi / period) * amp
            skel.spine.y -= breath_offset * 0.5
            for j in [skel.leg_L, skel.leg_R, skel.arm_L, skel.arm_R, skel.head]:
                j.y -= breath_offset * 0.3
        
        # ─── 身体弹跳 ───
        bounce = action.get("body_bounce_mm", 0)
        if bounce > 0:
            if "leg_L" in action:
                # 走/跑 弹跳
                bounce_offset = abs(math.sin(t * 8)) * bounce
            else:
                # 兴奋弹跳
                bounce_offset = abs(math.sin(t * 6)) * bounce
            skel.spine.y -= bounce_offset
        
        # ─── 脊柱 ───
        spine_data = action.get("spine", {})
        if spine_data.get("y_sway"):
            sway = math.sin(t * 2 * math.pi / spine_data.get("period_s", 2.0)) * spine_data["y_sway"]
            skel.spine.x += sway
        if spine_data.get("tilt_deg"):
            tilt = spine_data["tilt_deg"]
            rad = math.radians(tilt)
            skel.spine.y += math.sin(rad) * 10
        if spine_data.get("compress_mm"):
            skel.spine.y += spine_data["compress_mm"]
        
        # ─── 头部 ───
        head_data = action.get("head", {})
        if head_data.get("hold"):
            skel.head.x += math.sin(math.radians(head_data.get("tilt_deg", 0))) * 10
        elif head_data.get("tilt_deg"):
            period = head_data.get("period_s", 2.0)
            phase = math.sin(t * 2 * math.pi / period)
            tilt_deg = head_data["tilt_deg"] * phase
            skel.head.x += math.sin(math.radians(tilt_deg)) * 15
        if head_data.get("bob_mm"):
            bob = math.sin(t * 10) * head_data["bob_mm"]
            skel.head.y += bob
        if head_data.get("drop_mm"):
            skel.head.y += head_data["drop_mm"]
        if head_data.get("nod_deg"):
            period = head_data.get("period_s", 0.5)
            nod = math.sin(t * 2 * math.pi / period) * head_data["nod_deg"]
            skel.head.z += math.sin(math.radians(nod)) * 5
        
        # ─── 耳朵 ───
        ear_data = action.get("ears", {})
        if ear_data.get("flop_deg"):
            period = ear_data.get("period_s", 1.5)
            flop = math.sin(t * 2 * math.pi / period) * ear_data["flop_deg"]
            skel.ear_tip_L.x -= flop * 0.5
            skel.ear_tip_R.x += flop * 0.5
            skel.ear_tip_L.y -= abs(flop) * 0.3
            skel.ear_tip_R.y -= abs(flop) * 0.3
        
        ear_flop_mm = action.get("ear_flop_mm", 0)
        if ear_flop_mm:
            flop = math.sin(t * 8) * ear_flop_mm
            skel.ear_tip_L.y -= flop
            skel.ear_tip_R.y -= flop
        
        # ─── 尾巴 ───
        tail_data = action.get("tail", {})
        if tail_data.get("wag_deg", 0) > 0 and tail_data.get("period_s", 1.0) > 0:
            wag = math.sin(t * 2 * math.pi / tail_data["period_s"]) * tail_data["wag_deg"]
            skel.tail_tip.x += wag
        
        # ─── 四肢 ───
        leg_period = 2 * math.pi / max(action.get("duration_s", 1.0), 0.1)
        for limb_name in ["leg_L", "leg_R", "arm_L", "arm_R"]:
            limb_data = action.get(limb_name, {})
            limb = skel.joints.get(limb_name)
            if not limb or not limb_data:
                continue
            
            if limb_data.get("phase_deg") is not None:
                phase = math.radians(limb_data["phase_deg"])
                amp = math.radians(limb_data.get("amplitude_deg", 0))
                angle = math.sin(t * leg_period + phase) * amp
                limb.y += math.sin(angle) * limb.base[1] * 0.3
                limb.z += math.cos(angle) * 10
            
            if limb_data.get("bend_deg"):
                bend = math.radians(limb_data["bend_deg"])
                limb.y += math.sin(bend) * 20
                limb.z -= math.cos(bend) * 10
        
        # ─── 眼睛 ───
        eye_data = action.get("eye", {})
        eyelid_offset = 0
        if eye_data.get("closed"):
            eyelid_offset = 1.0
        elif eye_data.get("half_closed"):
            eyelid_offset = 0.5
        
        # 眨眼逻辑
        blink_every = eye_data.get("blink_every_s", action.get("blink_every_s", 3.0))
        
        # ─── 口型 ───
        mouth_code = action.get("mouth", "M_CLOSED")
        mouth_scale = MOUTH_SCALE.get(mouth_code, 1.0)
        
        # ─── 下颚 ───
        jaw_data = action.get("jaw", {})
        jaw_open = jaw_data.get("open_mm", mouth_scale * 8)
        
        return {
            "skeleton": skel.to_dict(),
            "eyelid": eyelid_offset,
            "blink_every": blink_every,
            "mouth_scale": mouth_scale,
            "jaw_open_mm": jaw_open,
            "breath": action.get("breath", {}),
        }
    
    def tick(self, dt_s):
        """每帧调用"""
        self.state.decay(dt_s)
        new_action = self.state.decide_action()
        if new_action != self.state.current_action:
            self.state.set_action(new_action)
            self._anim_t = 0.0
        
        self._anim_t += dt_s
        return self.apply_action(self.state.current_action, self._anim_t, dt_s)
    
    def get_state_json(self):
        """输出给前端的JSON"""
        anim = self.tick(0.05)  # 20fps
        return json.dumps({
            "action": self.state.current_action,
            "hunger": round(self.state.hunger, 1),
            "energy": round(self.state.energy, 1),
            "happiness": round(self.state.happiness, 1),
            "bond": round(self.state.bond, 1),
            "skeleton": {k: {"x": round(v["x"], 2), "y": round(v["y"], 2), "z": round(v["z"], 2)}
                         for k, v in anim["skeleton"].items()},
            "eyelid": round(anim["eyelid"], 2),
            "blink_every": anim["blink_every"],
            "mouth_scale": round(anim["mouth_scale"], 2),
            "jaw_open_mm": round(anim["jaw_open_mm"], 1),
            "timestamp": time.time(),
        })


# ═══════════════════════════════════════════
# HTTP服务器 (提供JSON API给前端)
# ═══════════════════════════════════════════

class PetServer:
    """轻量HTTP → 前端轮询pet状态JSON"""
    
    def __init__(self, port=8766):
        self.port = port
        self.animator = PetAnimator()
        self.running = False
    
    def start(self):
        import http.server
        import threading
        
        animator = self.animator
        
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/state':
                    state = animator.get_state_json()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(state.encode('utf-8'))
                elif self.path == '/feed':
                    animator.state.interact('feed')
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                elif self.path == '/play':
                    animator.state.interact('play')
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                elif self.path == '/pet':
                    animator.state.interact('pet')
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                elif self.path == '/action':
                    # 接收 ?action=xxx
                    from urllib.parse import urlparse, parse_qs
                    qs = parse_qs(urlparse(self.path).query)
                    action = qs.get('action', ['idle'])[0]
                    animator.state.set_action(action)
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "action": action}).encode())
                elif self.path == '/':
                    # 返回宠物HTML
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    with open(r'C:\Users\Administrator\brain_1GB\frenchie_pet_v6.html', 'rb') as f:
                        self.wfile.write(f.read())
                else:
                    self.send_response(404)
                    self.end_headers()
        
        self.running = True
        self.server = http.server.HTTPServer(('127.0.0.1', self.port), Handler)
        print(f"Pet Engine on http://127.0.0.1:{self.port}/")
        print(f"  GET /state  → JSON skeleton state")
        print(f"  GET /feed   → feed the dog")
        print(f"  GET /play   → play with dog")
        print(f"  GET /pet    → pet the dog")
        print(f"  GET /action?action=happy → set action")
        
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        return thread
    
    def stop(self):
        self.running = False
        if hasattr(self, 'server'):
            self.server.shutdown()


if __name__ == "__main__":
    svr = PetServer(8766)
    svr.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        svr.stop()
        print("Pet engine stopped.")
