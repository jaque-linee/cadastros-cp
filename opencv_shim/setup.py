from setuptools import setup

setup(
    name="opencv-python",
    version="4.11.0.86",
    description="Shim para usar OpenCV headless no Streamlit",
    install_requires=[
        "opencv-python-headless==4.11.0.86"
    ],
)
