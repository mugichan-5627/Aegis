import re
import os

svg_dir = r"c:\Users\Moosa\Downloads\Aegis_Codex\ppt-master\projects\aegis_pitch_ppt169_20260601\svg_final"
out = []
for f_name in sorted(os.listdir(svg_dir)):
    if f_name.endswith('.svg'):
        out.append(f"\n================ {f_name} ================")
        with open(os.path.join(svg_dir, f_name), 'r', encoding='utf-8') as f:
            content = f.read()
        texts = re.findall(r'<text[^>]*>(.*?)</text>', content)
        for t in texts:
            t_clean = t.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            out.append(f"  {t_clean}")

with open('svg_scanned.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print("Scanned SVG details dumped to svg_scanned.txt")
