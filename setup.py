#!/usr/bin/env python3
"""Setup script for glitchygames."""

from setuptools import setup, find_packages

setup(
    name="glitchygames",
    version="0.1.0",
    description="A Pygame wrapper for low-powered systems",
    author="Terry Simons",
    author_email="terry.simons@gmail.com",
    packages=find_packages(),
    install_requires=[
        "pygame>=2.0.0",
    ],
    include_package_data=True,
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Games/Entertainment",
        "Topic :: Software Development :: Libraries :: pygame",
    ],
)