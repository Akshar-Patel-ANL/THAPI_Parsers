typedef struct hipResourceDesc {
    union {
        struct {
            int array;
        } array;
    } res;
}hipResourceDesc;