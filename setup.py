from distutils.core import setup
from setuptools import find_packages


setup(
    name='artemis-cli',
    version='0.0.1',
    description='Artemis CLI',
    author='Joe Lombrozo',
    author_email='joe@djeebus.net',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    setup_requires=['setuptools-git'],
    zip_safe=True,
    install_requires=[
        'click',
        'libdiana',
    ],
    entry_points={
        'console_scripts': [
            'artemis-cli = artemis_cli:cli',
        ],
    },
)
