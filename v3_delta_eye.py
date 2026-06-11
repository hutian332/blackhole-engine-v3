"""
v3 Delta Eye — 帧间差异检测
不看"有什么"，看"变了什么"

原理: 万物是死色块，变化 = 色块空间重排
      → frame_t vs frame_t-1 的像素差 = 变化事件
"""

import cv2, numpy as np, time
from PIL import ImageGrab
from collections import defaultdict
from pathlib import Path

class DeltaEye:
    """帧差检测器 — 看变化不看静态"""
    
    def __init__(self, sample_rate=2, change_threshold=30):
        """
        sample_rate: 每秒采样帧数
        change_threshold: 变化像素阈值 (0-255)
        """
        self.sample_rate = sample_rate
        self.threshold = change_threshold
        self.prev_frame = None
        self.prev_time = None
        self.events = []
        self.regions = defaultdict(list)  # 区域变化历史
        
    def capture(self):
        """捕获当前帧"""
        img = ImageGrab.grab()
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    
    def diff(self, frame_a, frame_b):
        """计算两帧差异，返回变化区域"""
        # 绝对差
        delta = cv2.absdiff(frame_a, frame_b)
        
        # 二值化
        _, thresh = cv2.threshold(delta, self.threshold, 255, cv2.THRESH_BINARY)
        
        # 膨胀连接碎片
        kernel = np.ones((5,5), np.uint8)
        dilated = cv2.dilate(thresh, kernel, iterations=2)
        
        # 找变化区域轮廓
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        regions = []
        for c in contours:
            area = cv2.contourArea(c)
            if area > 100:  # 过滤噪点
                x, y, w, h = cv2.boundingRect(c)
                regions.append({
                    'bbox': (x, y, w, h),
                    'area': int(area),
                    'center': (x + w//2, y + h//2),
                })
        
        return regions, delta, dilated
    
    def step(self):
        """采样一帧，与前帧比较"""
        current = self.capture()
        now = time.time()
        
        if self.prev_frame is None:
            self.prev_frame = current
            self.prev_time = now
            return None
        
        regions, delta_raw, delta_mask = self.diff(self.prev_frame, current)
        
        total_changed = np.count_nonzero(delta_mask)
        pct_changed = total_changed / delta_mask.size * 100
        
        event = {
            'time': now,
            'dt': now - self.prev_time,
            'changed_pixels': int(total_changed),
            'change_pct': round(pct_changed, 3),
            'regions': regions,
            'region_count': len(regions),
            'delta_frame': delta_raw,
            'delta_mask': delta_mask,
        }
        
        self.events.append(event)
        self.prev_frame = current
        self.prev_time = now
        
        return event
    
    def classify_change(self, event):
        """分类变化类型"""
        if event is None or event['region_count'] == 0:
            return 'static'
        
        pct = event['change_pct']
        count = event['region_count']
        
        if pct > 30:
            return 'scene_change'    # 大范围变化（切窗口/切桌面）
        elif pct > 10:
            return 'major_change'    # 显著变化
        elif count > 10:
            return 'multi_motion'    # 多点运动
        elif count > 1:
            return 'small_motion'    # 小幅移动
        elif pct > 0.01:
            return 'micro_change'    # 微小变化（鼠标/光标）
        else:
            return 'static'
    
    def track_region(self, event, label='unknown'):
        """追踪变化区域的历史"""
        if event:
            for r in event['regions']:
                self.regions[label].append({
                    'time': event['time'],
                    'bbox': r['bbox'],
                    'area': r['area'],
                })
    
    def watch(self, duration=10):
        """持续监控指定时长，实时报告变化"""
        print(f"[DeltaEye] Watching for {duration}s @ {self.sample_rate}fps...")
        
        interval = 1.0 / self.sample_rate
        start = time.time()
        frames = 0
        changes = 0
        last_report = start
        
        while time.time() - start < duration:
            event = self.step()
            frames += 1
            
            if event and event['region_count'] > 0:
                changes += 1
                cat = self.classify_change(event)
                
                # 每秒报告一次
                if time.time() - last_report > 1:
                    print(f"  t={time.time()-start:.1f}s  "
                          f"changed={event['change_pct']:.2f}%  "
                          f"regions={event['region_count']}  "
                          f"type={cat}")
                    last_report = time.time()
            
            time.sleep(max(0, interval - (time.time() % interval)))
        
        print(f"\n[DeltaEye] Done. {frames} frames, {changes} changed ({changes/max(1,frames)*100:.1f}%)")
        return self.events
    
    def find_moving_objects(self, min_displacement=20):
        """从事件序列中找移动物体
        
        同一位置连续出现变化 → 物体在动
        """
        if len(self.events) < 2:
            return []
        
        tracks = []
        prev_regions = self.events[0]['regions'] if self.events[0] else []
        
        for i, ev in enumerate(self.events[1:], 1):
            if not ev or not ev['regions']:
                continue
            
            for curr in ev['regions']:
                cx, cy = curr['center']
                for prev in prev_regions:
                    px, py = prev['center']
                    dist = np.sqrt((cx-px)**2 + (cy-py)**2)
                    
                    if dist > min_displacement:
                        tracks.append({
                            'from': prev['center'],
                            'to': curr['center'],
                            'distance': round(dist, 1),
                            'time': ev['time'] - self.events[0]['time'],
                            'bbox_size': f"{curr['bbox'][2]}x{curr['bbox'][3]}",
                        })
            
            prev_regions = ev['regions']
        
        return tracks
    
    def save_debug_frame(self, event, path="delta_debug.jpg"):
        """保存差异帧用于调试"""
        if event is None:
            return
        
        h, w = event['delta_frame'].shape
        result = np.zeros((h, w, 3), dtype=np.uint8)
        
        # 红色 = 变化区域
        result[:,:,2] = event['delta_mask']
        # 绿色 = 原图覆盖
        result[:,:,1] = cv2.addWeighted(self.prev_frame, 0.3, 
                                         np.zeros_like(self.prev_frame), 0, 0)
        
        cv2.imwrite(path, result)
        return path


# ── 命令行 ──
if __name__ == "__main__":
    import sys
    
    eye = DeltaEye(sample_rate=2)
    
    # 快速测试: 监控5秒
    print("Starting delta eye... move a window or type something!")
    eye.watch(duration=5)
    eye.save_debug_frame(eye.events[-1] if eye.events else None, 
                         r"C:\Users\Administrator\brain_1GB\_delta_debug.jpg")
    
    # 找移动物体
    tracks = eye.find_moving_objects()
    if tracks:
        print(f"\n[Moving Objects Detected]")
        for t in tracks[:10]:
            print(f"  {t['from']} -> {t['to']}  d={t['distance']}px  size={t['bbox_size']}")
    
    # 统计
    cats = defaultdict(int)
    for ev in eye.events:
        if ev:
            cats[eye.classify_change(ev)] += 1
    print(f"\n[Change Categories]")
    for cat, count in sorted(cats.items()):
        print(f"  {cat}: {count}")
