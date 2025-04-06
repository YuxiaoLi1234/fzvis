#!/usr/bin/env python
# This file can be used later for standalone unit tests.
 
import libpressio

compressor = libpressio.PressioCompressor.from_config({
    "compressor_id": "sz",
    "early_config": {
        "pressio:metric": "composite",
        "composite:plugins": ["time", "size", "error_stat"],
    },
    "compressor_config": {
        "pressio:abs": 0.001
    }
})

print(compressor.get_configuration())