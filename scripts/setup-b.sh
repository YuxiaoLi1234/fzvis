export PATH=/home/hdevaiah/spack/bin:$PATH
spack --version
. /home/hdevaiah/spack/share/spack/setup-env.sh
spack load libpressio
spack load node-js
node -v
npm -v
pip install -r requirements.txt
source /home/hdevaiah/fzvis/env/bin/activate
python3 src/components/main.py
