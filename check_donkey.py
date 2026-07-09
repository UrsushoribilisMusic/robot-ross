import xml.etree.ElementTree as ET, re, math, sys

def tokenize_path(d):
    return re.findall(
        r'[MmLlHhVvCcQqSsTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', d)

def parse_path_d(d):
    tokens = tokenize_path(d)
    segments = []
    i = 0
    cmd = None
    cx, cy = 0.0, 0.0
    sx, sy = 0.0, 0.0

    def next_nums(n):
        nonlocal i
        result = []
        for _ in range(n):
            if i < len(tokens) and re.match(r'[-+]?(?:\d+\.?\d*|\.\d+)', tokens[i]):
                result.append(float(tokens[i])); i += 1
            else:
                result.append(0.0)
        return result

    while i < len(tokens):
        t = tokens[i]
        if re.match(r'[MmLlHhVvCcQqSsTtAaZz]', t):
            cmd = t; i += 1
        if cmd is None:
            i += 1; continue
        if cmd == 'M':
            x, y = next_nums(2); cx, cy = x, y; sx, sy = x, y
            segments.append(('move', cx, cy)); cmd = 'L'
        elif cmd == 'm':
            x, y = next_nums(2); cx += x; cy += y; sx, sy = cx, cy
            segments.append(('move', cx, cy)); cmd = 'l'
        elif cmd in ('L', 'l', 'H', 'h', 'V', 'v', 'C', 'c', 'S', 's', 'Q', 'q', 'T', 't'):
            if cmd == 'L': x, y = next_nums(2); cx, cy = x, y
            elif cmd == 'l': x, y = next_nums(2); cx += x; cy += y
            elif cmd == 'H': cx = next_nums(1)[0]
            elif cmd == 'h': cx += next_nums(1)[0]
            elif cmd == 'V': cy = next_nums(1)[0]
            elif cmd == 'v': cy += next_nums(1)[0]
            elif cmd in ('C', 'c'):
                n = next_nums(6)
                if cmd == 'c': cx += n[4]; cy += n[5]
                else: cx, cy = n[4], n[5]
            elif cmd in ('S', 's', 'Q', 'q'):
                n = next_nums(4)
                if cmd in ('s', 'q'): cx += n[2]; cy += n[3]
                else: cx, cy = n[2], n[3]
            elif cmd in ('T', 't'):
                n = next_nums(2)
                if cmd == 't': cx += n[0]; cy += n[1]
                else: cx, cy = n[0], n[1]
            segments.append(('line', cx, cy))
        elif cmd in ('Z', 'z'):
            cx, cy = sx, sy
    return segments

tree = ET.parse(r'C:\Users\migue\robot-ross\donkey.svg')
root = tree.getroot()
print("width:", root.get('width'))
print("height:", root.get('height'))
print("viewBox:", root.get('viewBox'))

all_segs = []
for elem in root.iter():
    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
    if tag == 'path':
        d = elem.get('d', '')
        if d:
            all_segs.extend(parse_path_d(d))

if not all_segs:
    print("NO SEGMENTS FOUND")
    sys.exit(1)

xs = [x for _, x, _ in all_segs]
ys = [y for _, _, y in all_segs]
print(f"X range: {min(xs):.2f} to {max(xs):.2f}  (span {max(xs)-min(xs):.2f})")
print(f"Y range: {min(ys):.2f} to {max(ys):.2f}  (span {max(ys)-min(ys):.2f})")
w = max(xs) - min(xs)
h = max(ys) - min(ys)
size_mm = 120
scale = size_mm / max(w, h)
print(f"scale for 120mm: {scale:.4f}")
print(f"output size: {w*scale:.1f} x {h*scale:.1f} mm")
