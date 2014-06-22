from setuptools import setup

setup(
    name='{{ appname }}',
    version='0.0.1',
    description="'{{ appname }}' WAMP Component",
    platforms=['Any'],
    packages='{{ appname }}',
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'autobahn.twisted.wamplet': [
            'backend = {{ appname }}.{{ appname }}:AppSession'
        ],
    }
)