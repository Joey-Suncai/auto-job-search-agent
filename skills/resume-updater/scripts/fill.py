# prints fraction of usable page height filled for each pdf (1.0 = text reaches bottom margin)
import sys, subprocess, re
from PIL import Image
import numpy as np
for pdf in sys.argv[1:]:
    pages = int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', pdf], capture_output=True, text=True).stdout).group(1))
    subprocess.run(['pdftoppm', '-r', '72', '-gray', '-f', '1', '-l', '1', '-png', pdf, '/tmp/_f'], check=True)
    import glob; im = np.asarray(Image.open(sorted(glob.glob('/tmp/_f*.png'))[0]))
    rows = np.where((im < 160).sum(1) > 0)[0]
    top, bot, H = rows.min(), rows.max(), im.shape[0]
    print(f"{pdf.split('/')[-1]:55s} pages={pages} top={top} bottom={bot} of {H}  fill={(bot)/(H-top):.3f}")
