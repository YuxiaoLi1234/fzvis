#!/usr/bin/env python
# This file can be used later for standalone unit tests.
 
import libpressio
from pprint import pprint

# c = libpressio.PressioCompressor("pressio", name="pressio")
# pprint(c.get_configuration()["pressio"]["pressio:compressor"])
# pprint(c.get_documentation())
# pprint(c.get_configuration()["pressio"])

# c = libpressio.PressioCompressor("pressio", {"pressio:compressor": compressor_id}, name="pressio")
# top_level = c.get_configuration()["pressio"]
# options = top_level[compressor_id] # we determined that "sz3" is the right string here by stripping out "pressio/" from the entries in children
# children = options["pressio:children"] # you'll see pressio/noop and pressio/sz3
# print("top_level:", json.dumps(top_level, indent=4, sort_keys=True))
# print("children:", json.dumps(children, indent=4, sort_keys=True))

# compressor_id = "sz3"
compressor_id = "zfp"
compressor = libpressio.PressioCompressor(compressor_id)

# compressor = libpressio.PressioCompressor.from_config({
#     "compressor_id": "sz3",
#     # "early_config": {
#     #     "pressio:metric": "composite",
#     #     "composite:plugins": ["time", "size", "error_stat"],
#     # },
#     # "compressor_config": {
#     #     "sz3:error_bound_mode_str":"ABS",
#     #     "sz3:abs_error_bound":0.001,
#     #     "pressio:nthreads": "4",
#     #     "pressio:abs": 0.001,
#     # }
# })

print("Documentation:")
pprint(compressor.get_documentation())
print("\nConfigurations:")
pprint(compressor.get_configuration())
print("\nOptions:")
pprint(compressor.get_options())


# print("\nFiltered configurations:")
# options = compressor.get_configuration()
# module_slots = {k: options[k] for k in options if k.startswith(compressor_id)}
# pprint(module_slots)

# compressor = libpressio.PressioCompressor(compressor_id, {"sz3:error_bound_mode_str": "ABS_OR_REL", "sz3:abs_error_bound": 1e-6, "sz3:rel_error_bound": 1e-6, "pressio:nthreads": 4})
# print("\nConfigurations:")
# pprint(compressor.get_configuration())
# print("\nOptions:")
# pprint(compressor.get_options())
