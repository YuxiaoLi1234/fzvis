#!/bin/bash

export PATH=/home/hdevaiah/spack/bin:$PATH
echo "Spack version:"
spack --version
. /home/hdevaiah/spack/share/spack/setup-env.sh
spack load libpressio
spack load node-js
node -v
npm -v
npm run serve