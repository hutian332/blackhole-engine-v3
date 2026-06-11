"""
v3 Live Compare Eye — 边看边对比, 实时报告
不是下载, 是盯着屏幕, 看到变化就对比记忆库
"""

import cv2, numpy as np, time, json, io, hashlib, base64, threading
from PIL import ImageGrab, Image, ImageDraw, ImageFont
from pathlib import Path
from collections import defaultdict, deque

try:
    import ollama
except:
    ollama = None

MEMORY_FILE = Path(r"C:\Users\Administrator\brain_1GB\visual_memory\live_patterns.json")
MEMORY_FILE.parent.mkdir(exist_ok=True)


class LiveCompare:
    """实时对比之眼"""
    
    def __init__(self):
        self.memory = self._load_memory()
        self.change_log = deque(maxlen=100)
        self.stats = {
            'frames': 0, 'changes': 0, 'known': 0, 'unknown': 0,
            'memory_size': len(self.memory),
            'start_time': time.time(),
        }
        self.prev_frame = None
        self.running = True
        
    def _load_memory(self):
        if MEMORY_FILE.exists():
            return json.loads(MEMORY_FILE.read_text())
        return {}
    
    def _save_memory(self):
        MEMORY_FILE.write_text(json.dumps(self.memory, ensure_ascii=False, indent=2))
    
    def _fingerprint(self, img_region):
        """快速指纹: 8x8 灰度感知哈希"""
        if isinstance(img_region, np.ndarray):
            gray = cv2.cvtColor(cv2.resize(img_region, (8,8)), cv2.COLOR_BGR2GRAY)
        else:
            gray = img_region.resize((8,8)).convert('L')
            gray = np.array(gray)
        avg = gray.mean()
        bits = (gray > avg).flatten()
        return ''.join('1' if b else '0' for b in bits)
    
    def _compare(self, fp, threshold=0.75):
        """对比记忆库, 找最相似的"""
        best = None
        best_score = 0
        for known_fp, data in self.memory.items():
            # Hamming 距离 → 相似度
            same = sum(a == b for a, b in zip(fp, known_fp))
            score = same / len(fp)
            if score > best_score:
                best_score = score
                best = (known_fp, data)
        if best_score >= threshold:
            return best[1], best_score
        return None, 0
    
    def _identify(self, img_region, fp):
        """不认识 → 先快速分析, 后台异步问 MiniCPM-V"""
        # 先返回 OpenCV 快速分析(不阻塞)
        basic = self._basic_analysis(img_region)
        
        # 异步问 MiniCPM-V (如果可用)
        if ollama:
            t = threading.Thread(target=self._async_identify, args=(fp, img_region), daemon=True)
            t.start()
        
        return basic
    
    def _async_identify(self, fp, img_region):
        """后台呼叫 MiniCPM-V, 结果回填记忆"""
        try:
            if isinstance(img_region, np.ndarray):
                pil_img = Image.fromarray(cv2.cvtColor(img_region, cv2.COLOR_BGR2RGB))
            else:
                pil_img = img_region
            
            buf = io.BytesIO()
            pil_img.save(buf, format='JPEG', quality=60)
            
            resp = ollama.chat(
                model='minicpm-v:8b',
                messages=[{
                    'role': 'user',
                    'content': 'What is this? Answer in 3-5 words.',
                    'images': [base64.b64encode(buf.getvalue()).decode()]
                }],
                options={'temperature': 0, 'num_predict': 30}
            )
            label = resp.message.content.strip()
            
            # 回填记忆
            if fp in self.memory:
                self.memory[fp]['description'] = label
                self.memory[fp]['label'] = label[:40]
                self._save_memory()
                print(f"  [ASYNC] Updated memory: {label[:50]}")
        except Exception as e:
            pass  # 静默失败, 基本分析已返回
    
    def _basic_analysis(self, img_region):
        """OpenCV 快速分析"""
        if isinstance(img_region, np.ndarray):
            cv_img = img_region
        else:
            cv_img = cv2.cvtColor(np.array(img_region), cv2.COLOR_RGB2BGR)
        
        h, w = cv_img.shape[:2]
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        
        edges = cv2.Canny(gray, 50, 150)
        e_density = np.count_nonzero(edges) / edges.size
        brightness = np.mean(gray)
        
        if brightness > 220:
            return f"white area {w}x{h}"
        elif brightness < 40:
            return f"dark area {w}x{h}"
        elif e_density > 0.15:
            return f"textured region {w}x{h}"
        else:
            return f"region {w}x{h}"
    
    def _detect_changes(self, current_frame):
        """检测两帧之间的变化"""
        if self.prev_frame is None:
            self.prev_frame = current_frame
            return []
        
        delta = cv2.absdiff(self.prev_frame, current_frame)
        gray = cv2.cvtColor(delta, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        dilated = cv2.dilate(thresh, np.ones((5,5), np.uint8), iterations=2)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        regions = []
        for c in contours:
            area = cv2.contourArea(c)
            if area > 50:
                x, y, w, h = cv2.boundingRect(c)
                crop = current_frame[y:y+h, x:x+w]
                regions.append({
                    'bbox': (x, y, w, h),
                    'area': int(area),
                    'crop': crop,
                })
        
        self.prev_frame = current_frame
        return regions
    
    def step(self):
        """一帧: 截图 → 检测变化 → 对比记忆 → 输出结果"""
        # 截图
        img = ImageGrab.grab()
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        self.stats['frames'] += 1
        
        # 检测变化
        regions = self._detect_changes(frame)
        if not regions:
            return []
        
        results = []
        for r in regions[:5]:  # 每帧最多看5个变化
            self.stats['changes'] += 1
            fp = self._fingerprint(r['crop'])
            
            # 对比记忆
            match, score = self._compare(fp)
            
            if match:
                self.stats['known'] += 1
                results.append({
                    'status': 'known',
                    'bbox': r['bbox'],
                    'area': r['area'],
                    'label': match['label'],
                    'description': match['description'],
                    'match_score': round(score * 100),
                    'first_seen': match.get('first_seen', '?'),
                })
            else:
                self.stats['unknown'] += 1
                # 问 MiniCPM-V
                label = self._identify(r['crop'], fp)
                
                # 存入记忆
                self.memory[fp] = {
                    'label': label.split(',')[0][:40] if ',' in label else label[:40],
                    'description': label,
                    'first_seen': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'seen_count': 1,
                    'size': f"{r['bbox'][2]}x{r['bbox'][3]}",
                }
                self._save_memory()
                self.stats['memory_size'] = len(self.memory)
                
                results.append({
                    'status': 'new',
                    'bbox': r['bbox'],
                    'area': r['area'],
                    'label': label,
                    'description': 'NEW - saved to memory',
                    'memory_now': len(self.memory),
                })
        
        # 日志
        for r in results:
            log_entry = f"[{r['status'].upper():5s}] ({r['bbox'][0]:4d},{r['bbox'][1]:4d}) {r['bbox'][2]}x{r['bbox'][3]:<4d} | {r['label'][:50]}"
            self.change_log.append(log_entry)
        
        return results
    
    def run(self, fps=1, duration=None):
        """持续运行, 实时监控"""
        interval = 1.0 / fps
        last_report = time.time()
        start = time.time()
        
        print(f"\n{'='*60}")
        print(f"  LIVE COMPARE EYE @ {fps}fps | Memory: {len(self.memory)}")
        print(f"  [K]=known [N]=new  (Ctrl+C to stop)")
        print(f"{'='*60}\n")
        
        try:
            while self.running:
                results = self.step()
                
                # 心跳: 每秒有变化就报
                if time.time() - last_report > 1:
                    if results:
                        for r in results:
                            symbol = 'K' if r['status'] == 'known' else 'N'
                            print(f"  [{symbol}] ({r['bbox'][0]:4d},{r['bbox'][1]:4d}) "
                                  f"{r['bbox'][2]}x{r['bbox'][3]:<4d} {r['label'][:50]}")
                    else:
                        # 无变化也打心跳
                        elapsed = time.time() - start
                        if int(elapsed) % 3 == 0:
                            print(f"  . ({int(elapsed)}s) no changes")
                    last_report = time.time()
                
                # 统计报告
                elapsed = time.time() - start
                if self.stats['frames'] % 30 == 0:
                    print(f"  --- t={elapsed:.0f}s F:{self.stats['frames']} C:{self.stats['changes']} "
                          f"K:{self.stats['known']} N:{self.stats['unknown']} ---")
                
                # 超时退出
                if duration and elapsed >= duration:
                    break
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
        
        return self.stats
    
    def status(self):
        """当前状态"""
        elapsed = time.time() - self.stats['start_time']
        return {
            'runtime': f"{elapsed:.0f}s",
            'frames': self.stats['frames'],
            'changes_detected': self.stats['changes'],
            'known': self.stats['known'],
            'new_learned': self.stats['unknown'],
            'memory_size': len(self.memory),
            'recent_log': list(self.change_log)[-10:],
        }


# ── 运行 ──
if __name__ == "__main__":
    import sys
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    
    eye = LiveCompare()
    eye.run(fps=2, duration=duration)
    
    print(f"\n{'='*70}")
    print(f"  SESSION SUMMARY")
    print(f"{'='*70}")
    s = eye.status()
    print(f"  Runtime:      {s['runtime']}")
    print(f"  Frames:       {s['frames']}")
    print(f"  Changes:      {s['changes_detected']}")
    print(f"  Known:        {s['known']} ({(s['known']/max(1,s['changes_detected'])*100):.0f}%)")
    print(f"  New learned:  {s['new_learned']}")
    print(f"  Memory bank:  {s['memory_size']} patterns")
    print(f"  Memory file:  {MEMORY_FILE}")
    
    if s['recent_log']:
        print(f"\n  [Recent]")
        for line in s['recent_log'][-5:]:
            print(f"    {line}")
