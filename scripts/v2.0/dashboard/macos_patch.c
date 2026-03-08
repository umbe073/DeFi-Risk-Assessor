#include <Python.h>
#include <objc/runtime.h>
#include <Foundation/Foundation.h>
#include <AppKit/AppKit.h>

// Forward declaration for the forwarding method
static void forwardInvocation(id self, SEL _cmd, NSInvocation *invocation);

static PyObject* patch_nsapplication(PyObject* self, PyObject* args) {
    // Get the NSApplication class
    Class nsApplicationClass = objc_getClass("NSApplication");
    if (!nsApplicationClass) {
        PyErr_SetString(PyExc_RuntimeError, "NSApplication class not found");
        return NULL;
    }
    
    // Create a method implementation that returns macOS 15.0
    IMP macosVersionIMP = imp_implementationWithBlock(^(id self) {
        return 15.0;
    });
    
    // Add the macOSVersion method to the class
    class_addMethod(nsApplicationClass, 
                   @selector(macOSVersion), 
                   macosVersionIMP, 
                   "d@:");
    
    // Add methodSignatureForSelector to handle any selector
    IMP methodSignatureIMP = imp_implementationWithBlock(^NSMethodSignature*(id self, SEL selector) {
        // Return a default signature for any selector
        return [NSMethodSignature signatureWithObjCTypes:"v@:"];
    });
    
    class_addMethod(nsApplicationClass, 
                   @selector(methodSignatureForSelector:), 
                   methodSignatureIMP, 
                   "@@::");
    
    // Add forwardInvocation to handle any missing method
    IMP forwardInvocationIMP = (IMP)forwardInvocation;
    class_addMethod(nsApplicationClass, 
                   @selector(forwardInvocation:), 
                   forwardInvocationIMP, 
                   "v@:@");
    
    Py_RETURN_NONE;
}

// Implementation of the forwarding method
static void forwardInvocation(id self, SEL _cmd, NSInvocation *invocation) {
    // Just do nothing for any unrecognized method
    // This prevents the crash by handling any missing method gracefully
}

static PyMethodDef MacOSPatchMethods[] = {
    {"patch_nsapplication", patch_nsapplication, METH_NOARGS, "Patch NSApplication with missing methods"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef macos_patch_module = {
    PyModuleDef_HEAD_INIT,
    "macos_patch",
    "macOS NSApplication patch",
    -1,
    MacOSPatchMethods
};

PyMODINIT_FUNC PyInit_macos_patch(void) {
    return PyModule_Create(&macos_patch_module);
}
