from distutils.core import setup

setup(
    name='pyexchange',
    version='1.0.0',
    packages=[
        'pyexchange',
    ],
    url='https://github.com/monolithos/pyexchange.git',
    license='',
    author='',
    author_email='',
    description='',
    install_requires=[
        "pymaker==1.2.*",
        "python-dateutil==2.8.1",
        "websockets==8.1.0",
        "python-kucoin==2.1.2",
        "pyjwt==1.7.1",
        "leverj_ordersigner==0.8",
        "dydx-python==0.9.4",
    ]
)
