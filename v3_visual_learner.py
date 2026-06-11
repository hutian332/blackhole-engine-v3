"""
v3 Visual Learning Engine — 去网上"看"，学回来
不是训练模型，是积累视觉经验

流程:
  看到变化 → 不认识 → 去网上找类似的 → 学回来 → 记住
  ────────────────────────────────────────────────────
  下次再看到 → 直接匹配记忆 → "哦，这是弹窗" → 不用再搜
"""

import cv2, numpy as np, time, json, hashlib, io, base64
from PIL import ImageGrab, Image
from collections import defaultdict
from pathlib import Path

try:
    import ollama
except:
    ollama = None

MEMORY_DIR = Path(r"C:\Users\Administrator\brain_1GB\visual_memory")
MEMORY_DIR.mkdir(exist_ok=True)


class VisualMemory:
    """视觉记忆库 — 见过的画面都记住"""
    
    def __init__(self, memory_path=MEMORY_DIR / "patterns.json"):
        self.path = Path(memory_path)
        self.patterns = self._load()
        self.history = []  # 本次会话记录
    
    def _load(self):
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {"patterns": {}, "total_seen": 0, "last_update": ""}
    
    def _save(self):
        self.path.write_text(json.dumps(self.patterns, ensure_ascii=False, indent=2))
    
    def fingerprint(self, image_region, method='color_histogram'):
        """给画面区域打指纹 (感知哈希)
        
        相同画面 → 相同指纹 → 能匹配记忆
        """
        if isinstance(image_region, np.ndarray):
            img = Image.fromarray(image_region)
        else:
            img = image_region
        
        if method == 'color_histogram':
            # 颜色直方图 → 对光照变化鲁棒
            img_small = img.resize((32, 32))
            hist = img_small.histogram()
            # 归一化到 0-255 再 hash
            max_val = max(hist) if hist else 1
            norm = [min(255, int(v * 255 / max_val)) for v in hist]
            h = hashlib.md5(bytes(norm)).hexdigest()[:16]
            return h
        
        elif method == 'phash':
            # 感知哈希 → 对缩放/格式不变
            img_gray = img.convert('L').resize((8, 8))
            pixels = list(img_gray.getdata())
            avg = sum(pixels) / len(pixels)
            bits = ''.join('1' if p > avg else '0' for p in pixels)
            return hex(int(bits, 2))[2:]
        
        return None
    
    def similar_to(self, fingerprint, threshold=0.7):
        """查找记忆中相似的指纹"""
        matches = []
        for fp, data in self.patterns['patterns'].items():
            # Hamming distance like
            dist = sum(a != b for a, b in zip(fp, fingerprint))
            max_len = max(len(fp), len(fingerprint))
            similarity = 1 - dist / max_len
            if similarity > threshold:
                matches.append((fp, data, similarity))
        matches.sort(key=lambda m: m[2], reverse=True)
        return matches
    
    def remember(self, fingerprint, label, description, context=None):
        """记住一个视觉模式"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        if fingerprint not in self.patterns['patterns']:
            self.patterns['patterns'][fingerprint] = {
                'label': label,
                'description': description,
                'first_seen': timestamp,
                'seen_count': 1,
                'context': context or {},
                'last_seen': timestamp,
            }
        else:
            self.patterns['patterns'][fingerprint]['seen_count'] += 1
            self.patterns['patterns'][fingerprint]['last_seen'] = timestamp
        
        self.patterns['total_seen'] += 1
        self.patterns['last_update'] = timestamp
        self._save()
        
        return self.patterns['patterns'][fingerprint]
    
    def recall(self, fingerprint):
        """回忆: 这个画面我见过吗？"""
        return self.patterns['patterns'].get(fingerprint)
    
    def stats(self):
        return {
            'total_patterns': len(self.patterns['patterns']),
            'total_seen': self.patterns['total_seen'],
            'top_labels': self._top_labels(10),
        }
    
    def _top_labels(self, n=10):
        counts = defaultdict(int)
        for data in self.patterns['patterns'].values():
            counts[data['label']] += 1
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]


class VisualLearner:
    """视觉学习引擎 — 看到→识别→学习→记住"""
    
    def __init__(self):
        self.memory = VisualMemory()
        self.seen_this_session = set()
        self.learned_this_session = []
    
    def look_at(self, image_crop, context=None):
        """看一张图，说出它是什么 (用本地模型)"""
        
        if ollama is None:
            return self._analyze_with_opencv(image_crop)
        
        # 转 base64
        if isinstance(image_crop, np.ndarray):
            img = Image.fromarray(image_crop)
        else:
            img = image_crop
        
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=70)
        b64 = base64.b64encode(buf.getvalue()).decode()
        
        try:
            resp = ollama.chat(
                model='minicpm-v:8b',
                messages=[{
                    'role': 'user',
                    'content': 'Describe this image in one short sentence. '
                              'What is it? Be specific and concise.',
                    'images': [b64]
                }],
                options={'temperature': 0, 'num_predict': 60}
            )
            description = resp.message.content.strip()
            return description
        except Exception as e:
            return self._analyze_with_opencv(image_crop)
    
    def _analyze_with_opencv(self, crop):
        """OpenCV 层面的分析"""
        if isinstance(crop, Image.Image):
            cv_img = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2BGR)
        else:
            cv_img = crop
        
        h, w = cv_img.shape[:2]
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        
        # 边缘密度
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.count_nonzero(edges) / edges.size
        
        # 平均亮度
        avg_brightness = np.mean(gray)
        
        # 颜色统计
        avg_color = cv2.mean(cv_img)[:3]
        
        # 纹理复杂度
        laplacian = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        parts = []
        if edge_density < 0.02:
            parts.append("smooth/low-detail")
        elif edge_density > 0.1:
            parts.append("high-detail/textured")
        else:
            parts.append("moderate detail")
        
        if avg_brightness > 200:
            parts.append("bright/white")
        elif avg_brightness < 50:
            parts.append("dark/black")
        elif avg_brightness < 100:
            parts.append("dark gray")
        elif avg_brightness > 150:
            parts.append("light gray")
        
        if avg_color[2] > 150 and avg_color[0] < 100:
            parts.append("warm/orange-ish")
        elif avg_color[0] > 150 and avg_color[2] < 100:
            parts.append("cool/blue-ish")
        
        description = f"{w}x{h}px region, " + ", ".join(parts)
        return description
    
    def learn_from_web(self, query, image_crop=None):
        """去网上搜，学回来
        
        策略: 用文字描述搜 → 下载相关图片 → 建立视觉关联
        """
        # TODO: 需要 web search + image download
        # 当前回退: 用本地模型描述
        results = {
            'query': query,
            'method': 'local_model',
            'description': None,
        }
        
        if image_crop and ollama:
            results['description'] = self.look_at(image_crop)
        
        return results
    
    def see(self, region_image, context=None):
        """主接口: 看到一个画面区域 → 识别 → 学习 → 记下
        
        返回: {
            'fingerprint': str,
            'known': bool,
            'label': str,
            'description': str,
            'learned': bool,
        }
        """
        fp = self.memory.fingerprint(region_image)
        
        # 先查记忆
        memory = self.memory.recall(fp)
        if memory:
            return {
                'fingerprint': fp,
                'known': True,
                'label': memory['label'],
                'description': memory['description'],
                'seen_count': memory['seen_count'],
                'source': 'memory',
            }
        
        # 查相似记忆
        similar = self.memory.similar_to(fp)
        if similar:
            best_fp, best_data, sim = similar[0]
            return {
                'fingerprint': fp,
                'known': True,
                'label': best_data['label'],
                'description': f'similar to: {best_data["description"]} (match={sim:.0%})',
                'source': 'similar_memory',
            }
        
        # 不认识 → 去理解
        description = self.look_at(region_image, context)
        label = self._guess_label(description)
        
        # 记住
        self.memory.remember(fp, label, description, context)
        
        self.learned_this_session.append({
            'fingerprint': fp,
            'label': label,
            'description': description,
            'time': time.time(),
        })
        
        return {
            'fingerprint': fp,
            'known': False,
            'label': label,
            'description': description,
            'source': 'learned_now',
        }
    
    def _guess_label(self, description):
        """从描述猜测标签"""
        desc_lower = description.lower()
        
        if any(w in desc_lower for w in ['button', 'menu', 'tab', 'window', 'bar']):
            return 'ui_element'
        elif any(w in desc_lower for w in ['text', 'word', 'letter', 'font']):
            return 'text_block'
        elif any(w in desc_lower for w in ['dog', 'pet', 'animal', 'frenchie']):
            return 'frenchie_pet'
        elif any(w in desc_lower for w in ['dark', 'black', 'shadow']):
            return 'dark_region'
        elif any(w in desc_lower for w in ['bright', 'white', 'light']):
            return 'bright_region'
        elif any(w in desc_lower for w in ['icon', 'image', 'picture']):
            return 'icon_or_image'
        else:
            return 'unknown_visual'


class LearningEye:
    """学习之眼 — DeltaEye + VisualLearner 联动"""
    
    def __init__(self):
        self.delta = __import__('v3_delta_eye').DeltaEye(sample_rate=1)
        self.learner = VisualLearner()
        
    def watch_and_learn(self, duration=30, max_learns=20):
        """看桌面 + 看到不认识的就学"""
        print(f"[LearningEye] Watching & learning for {duration}s...")
        
        learned = []
        start = time.time()
        frame_count = 0
        
        while time.time() - start < duration:
            event = self.delta.step()
            frame_count += 1
            
            if event and event['regions'] and len(learned) < max_learns:
                for region in event['regions'][:3]:  # 每帧最多学3个区域
                    x, y, w, h = region['bbox']
                    
                    # 截取变化区域
                    img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
                    
                    # 看 + 学
                    result = self.learner.see(img, context={
                        'position': (x, y),
                        'size': (w, h),
                        'change_pct': event['change_pct'],
                    })
                    
                    if not result['known']:
                        learned.append(result)
                        print(f"  LEARNED [{len(learned)}]: ({x},{y}) {w}x{h} → {result['label']}")
            
            time.sleep(0.5)  # 1fps
        
        print(f"\n[LearningEye] {frame_count} frames, "
              f"learned {len(learned)} new patterns, "
              f"memory: {self.learner.memory.stats()['total_patterns']} total")
        
        return {
            'frames': frame_count,
            'learned': learned,
            'memory_stats': self.learner.memory.stats(),
        }
    
    def explore_web(self, topic, count=5):
        """主动去网上探索学"""
        print(f"[LearningEye] Exploring web for: {topic}")
        
        # 搜索相关图片
        # TODO: 接入图片搜索 API
        return {'topic': topic, 'status': 'searched', 'results': []}


# ── 快速测试 ──
if __name__ == "__main__":
    eye = LearningEye()
    
    # 看30秒，学新东西
    result = eye.watch_and_learn(duration=15, max_learns=10)
    
    print(f"\n=== Session Summary ===")
    print(f"New patterns learned: {len(result['learned'])}")
    for l in result['learned']:
        print(f"  {l['label']}: {l['description'][:80]}")
    
    print(f"\nMemory bank: {result['memory_stats']}")
    
    # 主动探索
    eye.explore_web("french bulldog sitting pose")
