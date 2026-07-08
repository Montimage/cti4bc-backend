from setuptools import setup

setup(
    name='cti4bc',
    version='0.0.2',
    description='CTI4BC core functions',
    url='https://github.com/Montimage/cti4bc-backend',
    author='Montimage',
    author_email='contact@montimage.com',
    license='Apache-2.0',
    packages=['cti4bc'],
    install_requires=['aiohttp', 'pytest']
)
