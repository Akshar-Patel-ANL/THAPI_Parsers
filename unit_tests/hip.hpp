#define __HIP_PLATFORM_AMD__
#include <stdlib.h>
#include <pthread.h>
#include <string.h>
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <hip/hip_runtime_api.h>
#include <hip/hiprtc.h>
#include "modified_include/hip/hip_runtime_load_api.h"