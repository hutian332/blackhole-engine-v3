"""
v3 Visual Memory Expander — 喂数据, 长记忆
三种模式:
  1. 截屏轰炸 → 打开不同窗口/网页 → 批量截图学习
  2. 视频拆帧 → 下载视频 → FFmpeg拆帧 → 逐帧学习
  3. 桌面录制 → 长时间录屏 → 事后全量分析
"""

import cv2, numpy as np, time, json, io, base64, subprocess, os, glob
from PIL import ImageGrab, Image
from pathlib import Path
from collections import defaultdict

try:
    import ollama
except:
    ollama = None

MEMORY_FILE = Path(r"C:\Users\Administrator\brain_1GB\visual_memory\live_patterns.json")
MEMORY_FILE.parent.mkdir(exist_ok=True)


def fingerprint(img):
    """感知哈希指纹"""
    if isinstance(img, np.ndarray):
        gray = cv2.cvtColor(cv2.resize(img, (8,8)), cv2.COLOR_BGR2GRAY)
    else:
        gray = np.array(img.resize((8,8)).convert('L'))
    avg = gray.mean()
    bits = (gray > avg).flatten()
    return ''.join('1' if b else '0' for b in bits)


def load_memory():
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text())
    return {}


def save_memory(mem):
    MEMORY_FILE.write_text(json.dumps(mem, ensure_ascii=False, indent=2))


def scan_single(img, x, y, w, h):
    """扫描单张图的单个区域"""
    if isinstance(img, Image.Image):
        crop = img.crop((x, y, x+w, y+h))
    else:
        crop = img[y:y+h, x:x+w]
    return fingerprint(crop), crop


def identify_with_model(crop, model='minicpm-v:8b'):
    """用视觉模型识别一个区域"""
    if ollama is None:
        return "no_model"
    
    if isinstance(crop, np.ndarray):
        pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    else:
        pil = crop
    
    buf = io.BytesIO()
    pil.save(buf, format='JPEG', quality=60)
    
    try:
        resp = ollama.chat(
            model=model,
            messages=[{
                'role': 'user',
                'content': 'What is this? Answer in 3-5 words.',
                'images': [base64.b64encode(buf.getvalue()).decode()]
            }],
            options={'temperature': 0, 'num_predict': 30}
        )
        return resp.message.content.strip()
    except:
        return "model_error"


# ═══════════ 模式1: 截屏轰炸 ═══════════

def grid_scan_screenshot(screenshot_path=None, grid=8, min_size=20):
    """把一张截图切成网格, 学习每个格子
    
    参数: grid=8 → 8x8=64个格子
    """
    if screenshot_path:
        img = Image.open(screenshot_path)
    else:
        img = ImageGrab.grab()
    
    w, h = img.size
    gw, gh = w // grid, h // grid
    
    mem = load_memory()
    new_count = 0
    total = 0
    
    print(f"Grid scan: {grid}x{grid} = {grid*grid} cells, each {gw}x{gh}px")
    
    for row in range(grid):
        for col in range(grid):
            x, y = col * gw, row * gh
            total += 1
            
            fp, crop = scan_single(img, x, y, gw, gh)
            
            # 检查是否值得学习(非纯色)
            if isinstance(crop, Image.Image):
                cv_crop = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2GRAY)
            else:
                cv_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            
            std = np.std(cv_crop)
            if std < 15:  # 太均匀, 跳过
                continue
            
            if fp in mem:
                mem[fp]['seen_count'] += 1
                continue
            
            # 新图案 → 识别
            label = identify_with_model(crop)
            mem[fp] = {
                'label': label[:40],
                'description': label,
                'first_seen': time.strftime('%Y-%m-%d %H:%M:%S'),
                'seen_count': 1,
                'source': f'grid_scan({x},{y})',
            }
            new_count += 1
            
            if new_count % 5 == 0:
                print(f"  [{new_count}] learned: ({x},{y}) → {label[:50]}")
    
    save_memory(mem)
    print(f"\nGrid scan done: {new_count} new patterns, memory={len(mem)} total")
    return new_count


# ═══════════ 模式2: 视频拆帧 ═══════════

def video_to_frames(video_path, output_dir, fps=1):
    """FFmpeg 拆视频为帧序列"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vf', f'fps={fps},scale=640:-1',
        '-q:v', '3',
        str(output_dir / 'frame_%05d.jpg'),
        '-y', '-loglevel', 'error'
    ]
    
    subprocess.run(cmd, check=True)
    frames = sorted(output_dir.glob('frame_*.jpg'))
    print(f"Extracted {len(frames)} frames @ {fps}fps")
    return frames


def learn_from_video(video_path, fps=1, max_frames=100):
    """从视频学习视觉模式"""
    temp_dir = Path(r"C:\Users\Administrator\brain_1GB\_video_frames")
    
    print(f"Learning from: {video_path}")
    frames = video_to_frames(video_path, temp_dir, fps)
    frames = frames[:max_frames]
    
    mem = load_memory()
    new_count = 0
    
    for i, frame_path in enumerate(frames):
        img = Image.open(frame_path)
        w, h = img.size
        gw, gh = w // 4, h // 4
        
        for row in range(4):
            for col in range(4):
                x, y = col * gw, row * gh
                fp, crop = scan_single(img, x, y, gw, gh)
                
                cv_crop = np.array(crop.convert('L'))
                if np.std(cv_crop) < 15:
                    continue
                
                if fp in mem:
                    mem[fp]['seen_count'] += 1
                    continue
                
                label = identify_with_model(crop)
                mem[fp] = {
                    'label': label[:40],
                    'description': label,
                    'first_seen': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'seen_count': 1,
                    'source': f'video_frame_{i}',
                }
                new_count += 1
        
        if (i+1) % 10 == 0:
            print(f"  Frame {i+1}/{len(frames)} | memory={len(mem)}")
    
    save_memory(mem)
    print(f"Video learning: {new_count} new from {len(frames)} frames → memory={len(mem)}")
    return new_count


# ═══════════ 模式3: 变化猎人 ═══════════

def hunt_changes(duration=60, fps=2):
    """长时间监控, 专门学习没见过的东西
    
    与 LiveCompare 不同: 这个模式不报已知, 只学新的
    """
    print(f"Hunting new patterns for {duration}s @ {fps}fps...")
    
    mem = load_memory()
    prev = None
    new_count = 0
    frames = 0
    start = time.time()
    
    while time.time() - start < duration:
        img = ImageGrab.grab()
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        frames += 1
        
        if prev is not None:
            delta = cv2.absdiff(prev, frame)
            gray = cv2.cvtColor(delta, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
            dilated = cv2.dilate(thresh, np.ones((5,5), np.uint8), iterations=2)
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for c in contours:
                area = cv2.contourArea(c)
                if area < 100:
                    continue
                
                x, y, w, h = cv2.boundingRect(c)
                fp, crop = scan_single(frame, x, y, w, h)
                
                std = np.std(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
                if std < 10:
                    continue
                
                if fp not in mem:
                    label = identify_with_model(crop)
                    mem[fp] = {
                        'label': label[:40],
                        'description': label,
                        'first_seen': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'seen_count': 1,
                        'bbox': f'{x},{y},{w},{h}',
                    }
                    new_count += 1
                    print(f"  [NEW {new_count}] ({x},{y}) {w}x{h} → {label[:50]}")
        
        prev = frame
        time.sleep(1.0 / fps)
    
    save_memory(mem)
    print(f"\nHunt done: {frames} frames, {new_count} new → memory={len(mem)}")
    return new_count


# ═══════════ 统计 ═══════════

def memory_stats():
    mem = load_memory()
    labels = defaultdict(int)
    for data in mem.values():
        labels[data.get('label', '?')] += 1
    
    print(f"\nVisual Memory Bank: {len(mem)} patterns")
    print(f"Top labels:")
    for label, count in sorted(labels.items(), key=lambda x: x[1], reverse=True)[:20]:
        bar = '#' * count
        print(f"  {count:4d}  {label[:50]:50s} {bar}")


# ══ 主入口 ══
if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else 'status'
    
    if mode == 'grid':
        path = sys.argv[2] if len(sys.argv) > 2 else None
        grid_scan_screenshot(path, grid=8)
        memory_stats()
    
    elif mode == 'video':
        path = sys.argv[2]
        fps = int(sys.argv[3]) if len(sys.argv) > 3 else 2
        learn_from_video(path, fps=fps)
        memory_stats()
    
    elif mode == 'hunt':
        dur = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        hunt_changes(duration=dur, fps=2)
        memory_stats()
    
    elif mode == 'status':
        memory_stats()
    
    elif mode == 'clear':
        MEMORY_FILE.write_text('{}')
        print("Memory cleared.")
    
    elif mode == 'merge':
        # 合并旧的 visual_memory 数据
        old_path = Path(r"C:\Users\Administrator\brain_1GB\visual_memory\patterns.json")
        if old_path.exists():
            old_mem = json.loads(old_path.read_text())
            new_mem = load_memory()
            merged = 0
            for fp, data in old_mem.get('patterns', {}).items():
                if fp not in new_mem:
                    new_mem[fp] = data
                    merged += 1
            save_memory(new_mem)
            print(f"Merged {merged} patterns from patterns.json → {len(new_mem)} total")
        else:
            print("No old patterns.json found")
    
    else:
        print("""
v3 Visual Memory Expander

Usage:
  python v3_memory_expand.py grid [screenshot]  — 网格扫描截图
  python v3_memory_expand.py video <file> [fps] — 从视频学习
  python v3_memory_expand.py hunt [seconds]     — 变化猎人模式
  python v3_memory_expand.py status             — 查看记忆库
  python v3_memory_expand.py merge              — 合并旧数据
  python v3_memory_expand.py clear              — 清空记忆库
""")
