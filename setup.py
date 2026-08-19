from setuptools import setup

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="commitron",
    version="0.2.0",
    description="AI-powered Git commit message generator using Google Gemini",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Error404-uv",
    url="https://github.com/Error404-uv/commitron",
    py_modules=["smart_commit"],
    python_requires=">=3.9",
    install_requires=[
        "google-generativeai",
        "rich",
    ],
    entry_points={
        "console_scripts": [
            "smart-commit=smart_commit:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Topic :: Software Development :: Version Control :: Git",
    ],
)
