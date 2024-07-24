typedef union hipResourceDesc {
    enum {MODE1 = 1, MODE2 = 2, MODE3 = 3} mode;
    enum {TYPE1 = 1, TYPE2 = 2} type;
    union {
        struct foo {
            int array;
        } array;
        struct bar {
            int mipmap;
        } mipmap;
        struct {
            void* devPtr;
            int sizeInBytes;
        } linear;
        struct {
            void* devPtr;
            int width;
            int height;
            int pitchInBytes;
        } pitch2D;
    } res;
}hipResourceDesc;
