#ifndef HIP_RUNTIME_LOAD_API_
#define HIP_RUNTIME_LOAD_API_

#ifdef __cplusplus
extern "C" {
#endif /* __cplusplus */

extern void **__hipRegisterFatBinary(
    const void *data);


extern void __hipRegisterFunction(
    void         **modules,
    const void    *hostFunction,
    char          *deviceFunction,
    const char    *deviceName,
    unsigned int   threadLimit,
    uint3         *tid,
    uint3         *bid,
    dim3          *blockDim,
    dim3          *gridDim,
    int           *wSize);

extern void __hipRegisterManagedVar(
    void      **modules,    // Pointer to hip module returned from __hipRegisterFatbinary
    void      **pointer,    // Pointer to a chunk of managed memory with size \p size and alignment \p
                            // align HIP runtime allocates such managed memory and assign it to \p pointer
    void       *init_value, // Initial value to be copied into \p pointer
    const char *name,       // Name of the variable in code object
    size_t      size,
    unsigned    align);

extern void __hipRegisterSurface(
    void **modules,   // The device modules containing code object
    void  *var,       // The shadow variable in host code
    char  *hostVar,   // Variable name in host code
    char  *deviceVar, // Variable name in device code
    int    type,
    int    ext);


extern void __hipRegisterTexture(
    void **modules,   // The device modules containing code object
    void  *var,       // The shadow variable in host code
    char  *hostVar,   // Variable name in host code
    char  *deviceVar, // Variable name in device code
    int    type,
    int    norm,
    int    ext);

extern void __hipRegisterVar(
    void   **modules,   // The device modules containing code object
    void    *var,       // The shadow variable in host code
    char    *hostVar,   // Variable name in host code
    char    *deviceVar, // Variable name in device code
    int      ext,       // Whether this variable is external
    size_t   size,      // Size of the variable
    int      constant,  // Whether this variable is constant
    int      global);   // Unknown, always 0

extern void __hipUnregisterFatBinary(
    void** modules);

extern const char* hipGetCmdName(
    uint32_t id);

typedef enum activity_domain_t {
  ACTIVITY_DOMAIN_HSA_API = 0, /* HSA API domain */
  ACTIVITY_DOMAIN_HSA_OPS = 1, /* HSA async activity domain */
  ACTIVITY_DOMAIN_HIP_OPS = 2, /* HIP async activity domain */
  ACTIVITY_DOMAIN_HCC_OPS =
      ACTIVITY_DOMAIN_HIP_OPS, /* HCC async activity domain */
  ACTIVITY_DOMAIN_HIP_VDI =
      ACTIVITY_DOMAIN_HIP_OPS, /* HIP VDI async activity domain */
  ACTIVITY_DOMAIN_HIP_API = 3, /* HIP API domain */
  ACTIVITY_DOMAIN_KFD_API = 4, /* KFD API domain */
  ACTIVITY_DOMAIN_EXT_API = 5, /* External ID domain */
  ACTIVITY_DOMAIN_ROCTX = 6,   /* ROCTX domain */
  ACTIVITY_DOMAIN_HSA_EVT = 7, /* HSA events */
  ACTIVITY_DOMAIN_NUMBER
} activity_domain_t;

typedef int hipRegisterTracerCallback_callback_t(
    activity_domain_t domain,
    uint32_t operation_id,
    void* data);

extern void hipRegisterTracerCallback(
    hipRegisterTracerCallback_callback_t *function);

#ifdef __cplusplus
}
#endif /* __cplusplus */

#endif
