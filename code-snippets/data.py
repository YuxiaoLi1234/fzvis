import numpy as np
data = np.fromfile("vortex.bin", dtype=np.float32).reshape(50,50,50)
print(data)
