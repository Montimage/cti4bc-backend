from setuptools import setup

setup(
    name='cti4bc',
    version='0.0.2',
    description='DYNABIC CTI4BC core functions',
    url='https://gitlab.com/dynabic/cti4bc',
    author='The DYNABIC T5.4 team',
    author_email='cti4bc@dynabic.eu',
    # license='see_Dynabic_project',
    packages=['cti4bc'],
    install_requires=['aiohttp', 'pytest']
)
