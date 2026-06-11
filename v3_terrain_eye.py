"""
v3 地形视觉 — 万物死·马赛克的地形学分析
画面 = 高度场 → 山峰/山谷/鞍部/等高线 → 不需要AI模型就能"看见"

原理:
  Z轴 = 亮度(0~255)
  → 亮的地方凸起(山峰), 暗的地方凹陷(谷底)
  → 每个物体是一个地形特征
  → 豆包 = 一系列特征峰+特征坑的特定空间排列

地形学工具:
  - 等高线: 同一亮度层的边界线
  - 山峰: 局部最大值
  - 谷底: 局部最小值
  - 分水岭: 把相邻山峰划分开
  - 坡向: 亮度梯度方向
  - 面积-体积: 色块集群的大小
"""

import json, math
from collections import defaultdict
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    Image = None


class TerrainEye:
    """地形学视觉 — 把画面当高度场分析"""
    
    def __init__(self, image_path=None, image_array=None):
        if image_path:
            self.img = Image.open(image_path).convert('RGB')
        elif image_array:
            self.img = image_array
        else:
            raise ValueError("need image_path or image_array")
        
        self.w, self.h = self.img.size
        self.px = self.img.load()
        
        # 高度场 (亮度)
        self.heightmap = None  # 2D array [h][w] = 0~255
        # 坡度场
        self.slope = None
        # 坡向
        self.aspect = None
        # 地形特征
        self.peaks = []
        self.valleys = []
        self.contours = {}
        self.plateaus = []
        
    # ═══ 高度场构建 ═══
    
    def build_heightmap(self, channel='luminance'):
        """构建高度场
        
        channel: luminance | red | green | blue | warmth
        """
        hmap = [[0]*self.w for _ in range(self.h)]
        
        for y in range(self.h):
            for x in range(self.w):
                r, g, b = self.px[x, y]
                if channel == 'luminance':
                    hmap[y][x] = int(0.299*r + 0.587*g + 0.114*b)
                elif channel == 'red':
                    hmap[y][x] = r
                elif channel == 'green':
                    hmap[y][x] = g
                elif channel == 'blue':
                    hmap[y][x] = b
                elif channel == 'warmth':
                    hmap[y][x] = max(0, min(255, 128 + (r - b)))
        
        self.heightmap = hmap
        return hmap
    
    def build_slope(self):
        """计算坡度场 (亮度梯度大小)"""
        if not self.heightmap:
            self.build_heightmap()
        
        slope = [[0]*self.w for _ in range(self.h)]
        
        for y in range(1, self.h-1):
            for x in range(1, self.w-1):
                h = self.heightmap
                dx = (h[y][x+1] - h[y][x-1]) / 2
                dy = (h[y+1][x] - h[y-1][x]) / 2
                slope[y][x] = min(255, int(math.sqrt(dx*dx + dy*dy)))
        
        self.slope = slope
        return slope
    
    def build_aspect(self):
        """计算坡向 (亮度梯度的方向, 0-360度)"""
        if not self.heightmap:
            self.build_heightmap()
        
        aspect = [[0]*self.w for _ in range(self.h)]
        
        for y in range(1, self.h-1):
            for x in range(1, self.w-1):
                h = self.heightmap
                dx = (h[y][x+1] - h[y][x-1]) / 2
                dy = (h[y+1][x] - h[y-1][x]) / 2
                
                if dx == 0 and dy == 0:
                    aspect[y][x] = -1  # 平地
                else:
                    angle = math.degrees(math.atan2(dy, dx))
                    aspect[y][x] = (angle + 360) % 360
        
        self.aspect = aspect
        return aspect
    
    # ═══ 地形特征提取 ═══
    
    def find_peaks(self, min_prominence=15, neighborhood=5):
        """找山峰 (局部亮度极大值)
        
        prominence: 山峰突出度 (峰顶 - 周围最低鞍部)
        """
        if not self.heightmap:
            self.build_heightmap()
        
        h = self.heightmap
        peaks = []
        
        for y in range(neighborhood, self.h - neighborhood):
            for x in range(neighborhood, self.w - neighborhood):
                val = h[y][x]
                is_peak = True
                
                # 检查邻域
                for dy in range(-neighborhood, neighborhood+1):
                    for dx in range(-neighborhood, neighborhood+1):
                        if dx == 0 and dy == 0:
                            continue
                        if h[y+dy][x+dx] > val:
                            is_peak = False
                            break
                    if not is_peak:
                        break
                
                if is_peak and val > 30:  # 过滤暗像素噪声
                    # 算突出度
                    base = min(h[y+dy][x+dx] 
                              for dy in range(-neighborhood, neighborhood+1)
                              for dx in range(-neighborhood, neighborhood+1))
                    prominence = val - base
                    
                    if prominence >= min_prominence:
                        peaks.append({
                            'pos': (x, y),
                            'height': val,
                            'prominence': prominence,
                            'color': self.px[x, y],
                        })
        
        # 按高度排序
        peaks.sort(key=lambda p: p['height'], reverse=True)
        self.peaks = peaks
        return peaks
    
    def find_valleys(self, min_depth=15, neighborhood=5):
        """找谷底 (局部亮度极小值)"""
        if not self.heightmap:
            self.build_heightmap()
        
        h = self.heightmap
        valleys = []
        
        for y in range(neighborhood, self.h - neighborhood):
            for x in range(neighborhood, self.w - neighborhood):
                val = h[y][x]
                is_valley = True
                
                for dy in range(-neighborhood, neighborhood+1):
                    for dx in range(-neighborhood, neighborhood+1):
                        if dx == 0 and dy == 0:
                            continue
                        if h[y+dy][x+dx] < val:
                            is_valley = False
                            break
                    if not is_valley:
                        break
                
                if is_valley and val < 220:
                    rim = max(h[y+dy][x+dx]
                             for dy in range(-neighborhood, neighborhood+1)
                             for dx in range(-neighborhood, neighborhood+1))
                    depth = rim - val
                    
                    if depth >= min_depth:
                        valleys.append({
                            'pos': (x, y),
                            'height': val,
                            'depth': depth,
                            'color': self.px[x, y],
                        })
        
        valleys.sort(key=lambda v: v['depth'], reverse=True)
        self.valleys = valleys
        return valleys
    
    def find_contours(self, levels=10):
        """提取等高线"""
        if not self.heightmap:
            self.build_heightmap()
        
        h = self.heightmap
        step = 256 // levels
        
        contours = {}
        for level_idx in range(levels):
            threshold = level_idx * step
            pixels = []
            for y in range(self.h):
                for x in range(self.w):
                    if abs(h[y][x] - threshold) < 8:  # 等高线带宽度
                        # 检查相邻像素是否在阈值两侧
                        on_edge = False
                        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                            nx, ny = x+dx, y+dy
                            if 0 <= nx < self.w and 0 <= ny < self.h:
                                if (h[y][x] >= threshold and h[ny][nx] < threshold) or \
                                   (h[y][x] < threshold and h[ny][nx] >= threshold):
                                    on_edge = True
                                    break
                        if on_edge:
                            pixels.append((x, y))
            contours[threshold] = pixels
        
        self.contours = contours
        return contours
    
    def find_plateaus(self, min_size=500, flatness=8):
        """找台地/高原 (大片平坦高亮区域)
        
        豆包窗口 = 白色浏览器背景 → 大片平坦白色区域
        """
        if not self.heightmap:
            self.build_heightmap()
        
        h = self.heightmap
        visited = set()
        plateaus = []
        
        for y in range(0, self.h, 4):
            for x in range(0, self.w, 4):
                if (x, y) in visited:
                    continue
                
                val = h[y][x]
                
                # BFS 同高度区域
                region = []
                queue = [(x, y)]
                min_v, max_v = val, val
                
                while queue and len(region) < 50000:
                    cx, cy = queue.pop(0)
                    if (cx, cy) in visited:
                        continue
                    if not (0 <= cx < self.w and 0 <= cy < self.h):
                        continue
                    
                    cv = h[cy][cx]
                    if abs(cv - val) > flatness:
                        continue
                    
                    visited.add((cx, cy))
                    region.append((cx, cy))
                    min_v = min(min_v, cv)
                    max_v = max(max_v, cv)
                    
                    if len(region) >= 50000:
                        break
                    
                    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                        nx, ny = cx+dx, cy+dy
                        if (nx, ny) not in visited:
                            queue.append((nx, ny))
                
                if len(region) >= min_size:
                    xs = [p[0] for p in region]
                    ys = [p[1] for p in region]
                    avg_h = sum(h[py][px] for px, py in region) // len(region)
                    colors = [self.px[px, py] for px, py in region[:100]]  # 采样
                    avg_r = sum(c[0] for c in colors) // len(colors)
                    avg_g = sum(c[1] for c in colors) // len(colors)
                    avg_b = sum(c[2] for c in colors) // len(colors)
                    
                    plateaus.append({
                        'bbox': (min(xs), min(ys), max(xs), max(ys)),
                        'center': (sum(xs)//len(xs), sum(ys)//len(ys)),
                        'size': len(region),
                        'avg_height': avg_h,
                        'range': (min_v, max_v),
                        'avg_color': (avg_r, avg_g, avg_b),
                        'width': max(xs)-min(xs),
                        'height_px': max(ys)-min(ys),
                    })
        
        plateaus.sort(key=lambda p: p['size'], reverse=True)
        self.plateaus = plateaus
        return plateaus
    
    # ═══ 专找豆包 ═══
    
    def find_pet_terrain(self):
        """用地形特征找豆包
        
        豆包特征:
          - 白色高原 (浏览器窗口, ~280x340, 亮度>200)
          - 高原上有奶油色丘陵 (法斗身体, 亮度~180-210)
          - 丘陵上有深色洼地 (面罩, 亮度<60)
          - 洼地里有褐色斑点 (鼻子/耳朵, 亮度~80-140)
        
        地形签名: 高原 → 丘陵 → 洼地 → 斑点 (嵌套地形)
        """
        self.build_heightmap()
        self.find_plateaus(min_size=200, flatness=15)
        self.find_peaks(min_prominence=20, neighborhood=3)
        self.find_valleys(min_depth=20, neighborhood=3)
        
        candidates = []
        
        # 在台地中找嵌套特征
        for p in self.plateaus:
            bx, by, bx2, by2 = p['bbox']
            
            # 只看接近豆包窗口大小的台地
            w_range = abs(p['width'] - 300) < 200
            h_range = abs(p['height_px'] - 360) < 200
            if not (w_range and h_range):
                continue
            
            # 检查台地内的山峰和谷底
            peaks_in = [pk for pk in self.peaks 
                       if bx <= pk['pos'][0] <= bx2 and by <= pk['pos'][1] <= by2]
            valleys_in = [v for v in self.valleys
                         if bx <= v['pos'][0] <= bx2 and by <= v['pos'][1] <= by2]
            
            # 豆包特征: 丘陵颜色偏奶油, 洼地偏深
            cream_peaks = [pk for pk in peaks_in 
                          if 180 < pk['color'][0] < 250 
                          and 150 < pk['color'][1] < 220]
            dark_valleys = [v for v in valleys_in 
                           if v['color'][0] < 90 and v['color'][1] < 65]
            
            score = len(cream_peaks) * 50 + len(dark_valleys) * 30
            score += p['avg_height'] * 0.5  # 白色高原加分
            
            if score > 100:
                candidates.append({
                    'position': (bx, by),
                    'size': f"{p['width']}x{p['height_px']}",
                    'avg_height': p['avg_height'],
                    'cream_peaks': len(cream_peaks),
                    'dark_valleys': len(dark_valleys),
                    'score': score,
                    'color': p['avg_color'],
                    'elevation_range': p['range'],
                })
        
        candidates.sort(key=lambda c: c['score'], reverse=True)
        return candidates[:5]
    
    # ═══ 渲染 ═══
    
    def render_heightmap(self, normalize=True):
        """把高度场渲染成灰度地形图"""
        if not self.heightmap:
            self.build_heightmap()
        
        result = Image.new('L', (self.w, self.h))
        rpx = result.load()
        
        h = self.heightmap
        for y in range(self.h):
            for x in range(self.w):
                if normalize:
                    rpx[x, y] = h[y][x]
                else:
                    rpx[x, y] = h[y][x]
        
        return result
    
    def render_slope(self):
        """坡度图 — 边缘检测"""
        if not self.slope:
            self.build_slope()
        
        result = Image.new('L', (self.w, self.h))
        rpx = result.load()
        
        for y in range(self.h):
            for x in range(self.w):
                rpx[x, y] = self.slope[y][x]
        
        return result
    
    def render_terrain_analysis(self, mark_peaks=True, mark_valleys=True, mark_contours=True):
        """渲染地形分析图: 在原图上标注山峰/谷底/等高线"""
        result = self.img.copy()
        draw = ImageDraw.Draw(result)
        
        # 等高线
        if mark_contours and self.contours:
            for level, pixels in self.contours.items():
                if len(pixels) > 1000:
                    # 用采样点画
                    sample = pixels[::max(1, len(pixels)//500)]
                    for x, y in sample:
                        draw.point((x, y), fill=(0, 255, 255) if level < 128 else (0, 0, 0))
        
        # 山峰标记
        if mark_peaks and self.peaks:
            for p in self.peaks[:50]:
                x, y = p['pos']
                r = max(1, p['prominence']//20)
                draw.ellipse([x-r, y-r, x+r, y+r], outline=(255, 0, 0), width=1)
        
        # 谷底标记
        if mark_valleys and self.valleys:
            for v in self.valleys[:50]:
                x, y = v['pos']
                r = max(1, v['depth']//20)
                draw.ellipse([x-r, y-r, x+r, y+r], outline=(0, 0, 255), width=1)
        
        return result
    
    # ═══ 报告 ═══
    
    def analyze(self):
        """全地形分析"""
        self.build_heightmap()
        self.build_slope()
        self.find_peaks(min_prominence=15)
        self.find_valleys(min_depth=15)
        self.find_plateaus(min_size=300)
        self.find_contours(levels=8)
        
        pet = self.find_pet_terrain()
        
        # 统计
        h = self.heightmap
        all_heights = [h[y][x] for y in range(self.h) for x in range(self.w)]
        avg_height = sum(all_heights) / len(all_heights)
        max_height = max(all_heights)
        min_height = min(all_heights)
        
        return {
            'terrain': {
                'avg_elevation': round(avg_height, 1),
                'max_elevation': max_height,
                'min_elevation': min_height,
                'relief': max_height - min_height,
                'peaks_found': len(self.peaks),
                'valleys_found': len(self.valleys),
                'plateaus_found': len(self.plateaus),
            },
            'top_peaks': self.peaks[:10],
            'deepest_valleys': self.valleys[:10],
            'largest_plateaus': self.plateaus[:5],
            'pet_candidates': pet[:3],
            'contour_levels': len(self.contours),
        }
    
    def print_report(self):
        r = self.analyze()
        sep = '=' * 60
        
        print(f"\n{sep}")
        print(f"  v3 TERRAIN EYE REPORT")
        print(f"{sep}")
        print(f"  Elevation: avg={r['terrain']['avg_elevation']:.0f}  "
              f"min={r['terrain']['min_elevation']}  max={r['terrain']['max_elevation']}  "
              f"relief={r['terrain']['relief']}")
        print(f"  Features: {r['terrain']['peaks_found']} peaks  "
              f"{r['terrain']['valleys_found']} valleys  "
              f"{r['terrain']['plateaus_found']} plateaus  "
              f"{r['contour_levels']} contour levels")
        
        print(f"\n  [Top Peaks]")
        for p in r['top_peaks'][:10]:
            c = p['color']
            print(f"    ({p['pos'][0]:4d},{p['pos'][1]:4d}) "
                  f"h={p['height']:3d}  prominence={p['prominence']:3d}  "
                  f"color=#{c[0]:02x}{c[1]:02x}{c[2]:02x}")
        
        print(f"\n  [Deepest Valleys]")
        for v in r['deepest_valleys'][:10]:
            c = v['color']
            print(f"    ({v['pos'][0]:4d},{v['pos'][1]:4d}) "
                  f"h={v['height']:3d}  depth={v['depth']:3d}  "
                  f"color=#{c[0]:02x}{c[1]:02x}{c[2]:02x}")
        
        if r['pet_candidates']:
            print(f"\n  [Pet Terrain Candidates]")
            for p in r['pet_candidates']:
                print(f"    pos={p['position']}  size={p['size']}  "
                      f"elevation={p['elevation_range'][0]}-{p['elevation_range'][1]}  "
                      f"score={p['score']:.0f}  "
                      f"peaks={p['cream_peaks']}  valleys={p['dark_valleys']}")
        else:
            print(f"\n  [Pet] Not found in terrain")
        
        print(f"\n{sep}\n")
        return r


# ═══ 命令行 ═══
if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Administrator\brain_1GB\_scr_now.png"
    
    eye = TerrainEye(path)
    eye.build_heightmap()
    
    # 分析
    eye.print_report()
    
    # 渲染输出
    out_dir = Path(path).parent
    
    # 高度场灰度图
    hm = eye.render_heightmap()
    hm_path = out_dir / "_terrain_heightmap.png"
    hm.save(hm_path)
    print(f"Heightmap: {hm_path}")
    
    # 坡度图
    sl = eye.render_slope()
    sl_path = out_dir / "_terrain_slope.png"
    sl.save(sl_path)
    print(f"Slope map: {sl_path}")
    
    # 地形分析标注图
    ta = eye.render_terrain_analysis()
    ta_path = out_dir / "_terrain_analysis.png"
    ta.save(ta_path)
    print(f"Analysis overlay: {ta_path}")
    
    # 等高线图
    eye.find_contours(levels=8)
    ct = eye.render_heightmap()
    ct_path = out_dir / "_terrain_contours.png"
    ct.save(ct_path)
    print(f"Contours: {ct_path}")
