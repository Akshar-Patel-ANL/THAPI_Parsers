typedef enum hipMemoryType {
    hipMemoryTypeHost,    
    hipMemoryTypeDevice,                  
    hipMemoryTypeArray,   
    hipMemoryTypeUnified,
    hipMemoryTypeManaged
} hipMemoryType;

int main(){
    (void) hipMemoryTypeUnified;
}