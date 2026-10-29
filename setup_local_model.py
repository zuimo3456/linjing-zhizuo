"""Compatibility entry point: the active local model is pinned ONNX int8."""
import runpy

if __name__=='__main__':
    runpy.run_module('setup_onnx_model',run_name='__main__')
