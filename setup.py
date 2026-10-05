"""
Setup file for GraphAide.
Use setup.cfg to configure your project.

This file was generated with PyScaffold 4.5.
PyScaffold helps you to put up the scaffold of your new Python project.
Learn more under: https://pyscaffold.org/
"""

from setuptools import find_packages, setup

if __name__ == "__main__":
    try:
        setup(
            name="graphaide",
            packages=find_packages(where="src", exclude=["tests"]),
            package_dir={"": "src"},
            package_data={
                "": [
                    "resources/templates/*.*",
                    "web_demo/**/*.md",
                    "web_demo/**/*.sh",
                    "web_demo/frontend/src/**/*",
                    "web_demo/frontend/public/**/*",
                    "web_demo/frontend/*.html",
                    "web_demo/frontend/*.json",
                    "web_demo/frontend/*.ts",
                ],
            },
            exclude_package_data={
                "": ["web_demo/frontend/node_modules/**"],
            },
            include_package_data=True,
        )
    except Exception:  # noqa
        print(
            "\n\nAn error occurred while building the project, "
            "please ensure you have the most updated version of setuptools, "
            "setuptools_scm and wheel with:\n"
            "   pip install -U setuptools setuptools_scm wheel\n\n"
        )
        raise
