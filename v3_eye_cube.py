"""
v3 立方体视觉 — 万物死·马赛克理论的视觉实现
2D 画面 → 3D 立方体(voxel) → 多维度多角度提取

原理：
  画面 = (x, y, r, g, b) 5维点云
  每个像素 = 一个马赛克色块
  放入立方体后可以从任意角度切片观察

深度轴(Z)可以绑定：
  - Z=brightness → 亮度地形图（亮的凸起，暗的凹陷）
  - Z=R-G → 红-绿对比（暖色凸起，冷色凹陷）
  - Z=edge_strength → 边缘高度场（物体轮廓凸起）
  - Z=time → 时间维度（视频帧堆叠）

用法：
  import v3_eye_cube
  cube = V3EyeCube("screenshot.png")
  cube.analyze()                        # 全维度分析
  cube.project("top")                   # 俯瞰（就像看地图）
  cube.project("front")                 # 从前面看（高度剖面）
  cube.project("side")                  # 从侧面看
  cube.find_objects()                   # 在立方体里找物体
  cube.find_pet()                       # 找豆包
"""

import json
import math
from pathlib import Path
from collections import defaultdict

try:
    from PIL import Image
except ImportError:
    Image = None


class V3EyeCube:
    """把 2D 画面当立方体看"""

    def __init__(self, image_path=None, image_array=None):
        """加载画面，映射到立方体坐标系
        
        坐标系:
          x: 水平位置 (0~w)
          y: 垂直位置 (0~h)  
          z: 深度/属性轴 (0~255, 由属性决定)
        """
        if image_path:
            self.img = Image.open(image_path).convert('RGB')
        elif image_array is not None:
            self.img = image_array
        else:
            raise ValueError("需要 image_path 或 image_array")

        self.w, self.h = self.img.size
        self.pixels = self.img.load()
        
        # 立方体数据: voxels[{z}][{y}][{x}] = (r, g, b) 
        # 懒加载，analyze() 时填充
        self.voxels = {}
        self._z_max = 255
        
        # 统计
        self.color_clusters = []
        self.objects = []
        
    # ── 立方体构建 ──
    
    def build_cube(self, z_mode="brightness", bins=32):
        """把 2D 画面拉成 3D 立方体
        
        z_mode 选深度轴绑定什么属性:
          - "brightness"  : z = R+G+B/3 （亮度地形图）
          - "red"         : z = R （红色通道地形）
          - "warmth"      : z = R - B （暖度地形，暖色凸起）
          - "edge"        : z = 边缘强度 （物体轮廓凸起）
          - "flat"        : z = 常数 （平面展开，只看x,y,color）
        """
        if z_mode == "flat":
            self.voxels = {}
            for y in range(self.h):
                for x in range(self.w):
                    r, g, b = self.pixels[x, y]
                    z = 0
                    self.voxels.setdefault(z, {}).setdefault(y, {})[x] = (r, g, b)
            self._z_max = 0
            return self
        
        if z_mode == "brightness":
            for y in range(self.h):
                for x in range(self.w):
                    r, g, b = self.pixels[x, y]
                    z = min(int((r + g + b) / 3 / (255 / bins)), bins - 1)
                    self.voxels.setdefault(z, {}).setdefault(y, {})[x] = (r, g, b)
            self._z_max = bins - 1
            
        elif z_mode == "red":
            for y in range(self.h):
                for x in range(self.w):
                    r, g, b = self.pixels[x, y]
                    z = min(int(r / (255 / bins)), bins - 1)
                    self.voxels.setdefault(z, {}).setdefault(y, {})[x] = (r, g, b)
            self._z_max = bins - 1
            
        elif z_mode == "warmth":
            for y in range(self.h):
                for x in range(self.w):
                    r, g, b = self.pixels[x, y]
                    warmth = max(0, min(255, 128 + (r - b)))
                    z = min(int(warmth / (255 / bins)), bins - 1)
                    self.voxels.setdefault(z, {}).setdefault(y, {})[x] = (r, g, b)
            self._z_max = bins - 1
            
        elif z_mode == "edge":
            # 先算边缘强度
            edge_map = self._compute_edges()
            for y in range(self.h):
                for x in range(self.w):
                    r, g, b = self.pixels[x, y]
                    e = edge_map.get((x, y), 0)
                    z = min(int(e / (255 / bins)), bins - 1)
                    self.voxels.setdefault(z, {}).setdefault(y, {})[x] = (r, g, b)
            self._z_max = bins - 1
        
        # 统计每层体素数
        self.layer_sizes = {z: sum(len(row) for row in rows.values()) 
                           for z, rows in self.voxels.items()}
        return self
    
    def _compute_edges(self):
        """Sobel 边缘检测，返回 {(x,y): strength}"""
        edges = {}
        for y in range(1, self.h - 1):
            for x in range(1, self.w - 1):
                # 获取 3x3 邻居亮度
                def lum(ox, oy):
                    r, g, b = self.pixels[x + ox, y + oy]
                    return (r + g + b) / 3
                
                gx = lum(1,0)-lum(-1,0) + 2*(lum(1,1)-lum(-1,1)) + 2*(lum(1,-1)-lum(-1,-1)) + lum(1,0)-lum(-1,0)
                gy = lum(0,1)-lum(0,-1) + 2*(lum(1,1)-lum(1,-1)) + 2*(lum(-1,1)-lum(-1,-1)) + lum(0,1)-lum(0,-1)
                strength = min(255, int(math.sqrt(gx*gx + gy*gy)))
                if strength > 10:
                    edges[(x, y)] = strength
        return edges
    
    # ── 多维度投影 ──
    
    def project(self, view="top", z_slice=None):
        """从不同角度投影立方体
        
        view:
          "top"     → 俯瞰（X-Y平面，忽略Z）——原始画面
          "front"   → 从前面看（X-Z平面，压扁Y）
          "side"    → 从侧面看（Y-Z平面，压扁X）  
          "slice"   → 切一个 Z 层（只看某个深度）
          "diagonal"→ 斜45度俯瞰
        
        z_slice: 如果 view="slice"，指定看哪一层
        """
        if not self.voxels:
            self.build_cube()
        
        w, h = 400, 300
        
        if view == "top":
            # 俯瞰 = 原图缩小
            return self.img.resize((w, h))
        
        elif view == "front":
            # 从前面看：X轴=宽度, Z轴=高度, 每列是Y轴的平均色
            result = Image.new('RGB', (w, h), (0, 0, 0))
            res_px = result.load()
            
            for z in sorted(self.voxels.keys()):
                rz = int(z / max(1, self._z_max) * (h - 1))
                for x_bin in range(w):
                    orig_x = int(x_bin / w * self.w)
                    # 收集 Y 轴所有像素的色
                    colors = []
                    for row_y, row in self.voxels.get(z, {}).items():
                        if orig_x in row:
                            colors.append(row[orig_x])
                    if colors:
                        avg_r = sum(c[0] for c in colors) // len(colors)
                        avg_g = sum(c[1] for c in colors) // len(colors)
                        avg_b = sum(c[2] for c in colors) // len(colors)
                        res_px[x_bin, h - 1 - rz] = (avg_r, avg_g, avg_b)
            return result
        
        elif view == "side":
            # 从侧面看：Y轴=高度, Z轴=深度, 每行是X轴平均色
            result = Image.new('RGB', (w, h), (0, 0, 0))
            res_px = result.load()
            
            for z in sorted(self.voxels.keys()):
                rz = int(z / max(1, self._z_max) * (h - 1))
                for y_bin in range(h):
                    orig_y = int(y_bin / h * self.h)
                    colors = []
                    for zz, zdata in self.voxels.items():
                        if orig_y in zdata:
                            for x, col in zdata[orig_y].items():
                                colors.append(col)
                    if colors:
                        avg_r = sum(c[0] for c in colors) // len(colors)
                        avg_g = sum(c[1] for c in colors) // len(colors)
                        avg_b = sum(c[2] for c in colors) // len(colors)
                        res_px[h - 1 - rz, y_bin] = (avg_r, avg_g, avg_b)
            return result
            
        elif view == "slice":
            # 切一片 Z 层
            if z_slice is None:
                z_slice = max(self.layer_sizes, key=self.layer_sizes.get) if self.layer_sizes else 0
            
            z_data = self.voxels.get(z_slice, {})
            result = Image.new('RGB', (self.w, self.h), (0, 0, 0))
            res_px = result.load()
            for y, row in z_data.items():
                for x, col in row.items():
                    res_px[x, y] = col
            return result
        
        elif view == "diagonal":
            # 斜45度：X-Y做透视，Z做高度偏移
            # 简化：top view + brightness overlay
            result = self.img.copy().resize((w, h))
            return result
        
        return self.img.resize((w, h))
    
    # ── 色块聚类 ──
    
    def cluster_colors(self, n_clusters=8):
        """在 RGB 色彩空间立方体里做聚类
        
        把 RGB(0-255)^3 当立方体，每个像素是一点
        找到点云最密集的区域 → 主色调
        """
        # 颜色量化到 16 级
        quantized = defaultdict(int)
        for y in range(self.h):
            for x in range(self.w):
                r, g, b = self.pixels[x, y]
                qr, qg, qb = r // 16, g // 16, b // 16
                quantized[(qr, qg, qb)] += 1
        
        # 按频率排序取 top N
        sorted_colors = sorted(quantized.items(), key=lambda x: x[1], reverse=True)
        
        self.color_clusters = []
        for i, ((qr, qg, qb), count) in enumerate(sorted_colors[:n_clusters]):
            pct = count / (self.w * self.h) * 100
            self.color_clusters.append({
                'rank': i + 1,
                'color': (qr * 16 + 8, qg * 16 + 8, qb * 16 + 8),
                'cube_pos': (qr, qg, qb),  # 在 RGB 立方体里的位置
                'pixels': count,
                'coverage': round(pct, 2),
            })
        
        return self.color_clusters
    
    # ── 物体找 ──
    
    def find_objects(self, min_size=500):
        """在立方体里找物体（连通色块区域）
        
        策略：用 Z=亮度 构建立方体
        → 找到亮度突变的地方（物体边界）
        → 对每个边界围起来的区域做连通判定
        """
        if not self.voxels or 'edge' not in str(getattr(self, '_last_z_mode', '')):
            self.build_cube(z_mode="brightness")
            self._last_z_mode = "brightness"
        
        # 简化版：在 2D 层面做连通域标记
        # 用 BFS 找同色连通块
        visited = set()
        self.objects = []
        
        # 只采样（全图太慢）
        sample_rate = 4
        color_threshold = 30  # 颜色相近容忍度
        
        for y in range(0, self.h, sample_rate):
            for x in range(0, self.w, sample_rate):
                if (x, y) in visited:
                    continue
                
                # BFS 扩展
                seed_r, seed_g, seed_b = self.pixels[x, y]
                cluster = []
                queue = [(x, y)]
                
                while queue:
                    cx, cy = queue.pop(0)
                    if (cx, cy) in visited:
                        continue
                    if not (0 <= cx < self.w and 0 <= cy < self.h):
                        continue
                    
                    cr, cg, cb = self.pixels[cx, cy]
                    dist = abs(cr - seed_r) + abs(cg - seed_g) + abs(cb - seed_b)
                    if dist > color_threshold:
                        continue
                    
                    visited.add((cx, cy))
                    cluster.append((cx, cy))
                    
                    if len(cluster) > 5000:  # 太大就别扩了
                        break
                    
                    # 4-邻域
                    for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                        nx, ny = cx + dx, cy + dy
                        if (nx, ny) not in visited:
                            queue.append((nx, ny))
                
                if len(cluster) > min_size:
                    xs = [p[0] for p in cluster]
                    ys = [p[1] for p in cluster]
                    cs = [self.pixels[p[0], p[1]] for p in cluster]
                    avg_r = sum(c[0] for c in cs) // len(cs)
                    avg_g = sum(c[1] for c in cs) // len(cs)
                    avg_b = sum(c[2] for c in cs) // len(cs)
                    
                    self.objects.append({
                        'bbox': (min(xs), min(ys), max(xs), max(ys)),
                        'center': (sum(xs) // len(xs), sum(ys) // len(ys)),
                        'size': len(cluster) * (sample_rate ** 2),
                        'avg_color': (avg_r, avg_g, avg_b),
                        'width': max(xs) - min(xs),
                        'height': max(ys) - min(ys),
                    })
        
        # 按大小排序
        self.objects.sort(key=lambda o: o['size'], reverse=True)
        return self.objects
    
    def find_pet(self):
        """专门找豆包 — 奶油色+深色面罩的矩形窗口
        
        策略：
        1. 不是找连通域（太慢）
        2. 用颜色特征 + 窗口形状匹配
        3. 豆包特征: 白色窗口背景 + 奶油色狗身 + 深色狗脸
        """
        w, h = self.w, self.h
        
        # 窗口候选
        candidates = []
        
        # 滑动窗口法
        win_w, win_h = 280, 340
        for y in range(0, h - win_h, 30):
            for x in range(0, w - win_w, 30):
                # 采样窗口内颜色
                sample = []
                for sy in range(y, y + win_h, 8):
                    for sx in range(x, x + win_w, 8):
                        r, g, b = self.pixels[sx, sy]
                        sample.append((r, g, b))
                
                if not sample:
                    continue
                
                # 特征统计
                white = sum(1 for r,g,b in sample if r>235 and g>235 and b>235)
                cream = sum(1 for r,g,b in sample if 185<r<250 and 155<g<220 and 120<b<185)
                dark = sum(1 for r,g,b in sample if r<90 and g<65 and b<55)
                brown = sum(1 for r,g,b in sample if 80<r<160 and 40<g<100 and 20<b<70)
                
                total = len(sample)
                
                # 豆包特征分
                score = 0
                score += cream * 3       # 奶油色身体（核心特征）
                score += dark * 2        # 深色面罩
                score += brown * 2       # 棕色耳朵/鼻子
                score += min(white, total * 0.3) * 0.5  # 适量白色
                
                if score > 500:
                    candidates.append({
                        'position': (x, y),
                        'score': score,
                        'white_pct': white / total * 100,
                        'cream_pct': cream / total * 100,
                        'dark_pct': dark / total * 100,
                        'brown_pct': brown / total * 100,
                    })
        
        # 排序
        candidates.sort(key=lambda c: c['score'], reverse=True)
        return candidates[:5]
    
    # ── 分析报告 ──
    
    def analyze(self):
        """全维度分析报告"""
        if not self.voxels:
            self.build_cube()
        
        self.cluster_colors()
        self.find_objects()
        pet_candidates = self.find_pet()
        
        report = {
            'image_size': f'{self.w}x{self.h}',
            'total_pixels': self.w * self.h,
            'cube_layers': len(self.voxels),
            'layer_distribution': {str(k): v for k, v in sorted(self.layer_sizes.items())},
            'dominant_colors': self.color_clusters[:5],
            'objects_found': len(self.objects),
            'top_objects': self.objects[:5],
            'pet_search': pet_candidates[:3] if pet_candidates else [],
        }
        
        self.report = report
        return report
    
    def print_report(self):
        """打印分析报告"""
        r = self.analyze()
        sep = '=' * 60
        print(f"\n{sep}")
        print(f"  v3 CUBE VISION REPORT")
        print(f"{sep}")
        print(f"  Image: {r['image_size']}  ({r['total_pixels']:,} pixels)")
        print(f"  Cube layers: {r['cube_layers']}")
        print(f"\n  [Color Clusters in RGB Cube]")
        for c in r['dominant_colors']:
            bar = '#' * max(1, int(c['coverage'] * 2))
            print(f"     #{c['color'][0]:02x}{c['color'][1]:02x}{c['color'][2]:02x}  "
                  f"pos({c['cube_pos'][0]},{c['cube_pos'][1]},{c['cube_pos'][2]})  "
                  f"{c['coverage']:.1f}%  {bar}")
        
        if r['objects_found']:
            print(f"\n  [Objects Found: {r['objects_found']}]")
            for obj in r['top_objects']:
                print(f"     ({obj['bbox'][0]},{obj['bbox'][1]})-({obj['bbox'][2]},{obj['bbox'][3]})  "
                      f"{obj['width']}x{obj['height']}px  "
                      f"~{obj['size']}px2  "
                      f"#{obj['avg_color'][0]:02x}{obj['avg_color'][1]:02x}{obj['avg_color'][2]:02x}")
        
        if r['pet_search']:
            print(f"\n  [Pet Search Result]")
            for p in r['pet_search']:
                print(f"     pos({p['position'][0]},{p['position'][1]})  "
                      f"score={p['score']:.0f}  "
                      f"cream={p['cream_pct']:.1f}%  dark={p['dark_pct']:.1f}%  "
                      f"brown={p['brown_pct']:.1f}%")
        else:
            print(f"\n  [Pet Search] NOT FOUND")
        
        print(f"\n{sep}\n")
        return r
    
    def save_projections(self, prefix="proj"):
        """保存所有投影视角"""
        views = {
            'top': "俯瞰(X-Y)",
            'front': "前面(X-Z)", 
            'side': "侧面(Y-Z)",
        }
        saved = []
        for view, label in views.items():
            img = self.project(view=view)
            path = f"C:\\Users\\Administrator\\brain_1GB\\_{prefix}_{view}.jpg"
            img.save(path, quality=70)
            saved.append((path, label))
        return saved


# ─── 快速测试 ───
if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Administrator\brain_1GB\_screenshot.png"
    
    cube = V3EyeCube(path)
    cube.build_cube(z_mode="brightness")
    
    # 全分析
    cube.print_report()
    
    # 保存多角度投影
    saved = cube.save_projections()
    print("\nProjections saved:")
    for p, label in saved:
        print(f"  {label}: {p}")
    
    # 切换视角：边缘地形
    print("\n--- Switching view: edge terrain ---")
    cube.build_cube(z_mode="edge")
    pet = cube.find_pet()
    print(f"Edge-view pet search: {pet[:2] if pet else 'not found'}")
