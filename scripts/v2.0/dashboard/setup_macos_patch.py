#!/usr/bin/env python3
"""
Setup script for macOS patch C extension
"""

from setuptools import setup, Extension
import os
import sys

# Define the extension
macos_patch_extension = Extension(
    'macos_patch',
    sources=['macos_patch.c'],
    extra_compile_args=[
        '-framework', 'Foundation',
        '-framework', 'AppKit',
        '-framework', 'Cocoa',
        '-ObjC'
    ],
    extra_link_args=[
        '-framework', 'Foundation',
        '-framework', 'AppKit',
        '-framework', 'Cocoa'
    ]
)

# Setup
setup(
    name='macos_patch',
    version='1.0',
    description='macOS NSApplication patch for tkinter compatibility',
    ext_modules=[macos_patch_extension],
    py_modules=[],
)
