# usage: stitch.py out.png full_width offset tileA.png tileB.png
import sys
from PIL import Image
import numpy as np
out, W, off, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
A = Image.open(a).convert('RGB'); B = Image.open(b).convert('RGB')
h = A.size[1]; vw = A.size[0]
d = np.abs(np.asarray(A)[:, off:vw].astype(int) - np.asarray(B)[:, 0:vw-off].astype(int)).mean()
print('overlap diff', round(d, 3))
img = Image.new('RGB', (W, h)); img.paste(A, (0, 0)); img.paste(B.crop((vw-off, 0, vw, h)), (vw, 0))
img.save(out); print(out, img.size)
