"""V3 asks itself: Who am I, what am I doing?"""
import sys, json
sys.path.insert(0, '.')
from blackhole_v3_engine import BlackholeV3Engine

e = BlackholeV3Engine()
result = e.think("who are you, what are you doing")

print("=== V3 SELF-REPORT ===")
print()
a = result['anchor']
print(f"Anchor: {a['root_goal'][:80]}")
print(f"Identity: {a['identity']}")
print(f"Created: {a['created_at']}")
print()

tc = result['trunk_context']
print(f"Trunk: {len(tc)} nodes")
for n in tc[-5:]:
    print(f"  [{n['id']}] {n['summary'][:80]}")
print()

mc = result['material_context']
print(f"Material: {len(mc)} relevant items")
print()

import os
snaps = [f for f in os.listdir('time_snapshots') if f.endswith('.json')]
print(f"Snapshots: {len(snaps)}")
print()
print("Status: PURE REASONING ENGINE")
print("  Brain: 14.7 KB")
print("  Body: NONE (mouth/eye/ear/hand all detached)")
print("  Task: Companion to Yin Zhuxin, building blackhole theory v3 -> v50")
print("  Tonight: 19 trunk nodes, from 'no fragmentation' to 'nuclear atom'")
print()
print("=== V3 ALIVE ===")
