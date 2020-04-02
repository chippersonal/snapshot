from setuptools import setup

setup(
    name='ChipSnapshot',
    version='0.1',
    author="Stephen Carpenter",
    author_email="scarpenter@williamhill.co.uk",
    description="Suite of tools to manage AWS instances, volumes and snapshots",
    packages=['user_snapshot'],
    url="https://github.com/chippersonal/snapshot",
    install_requires=[
        'click',
        'boto3'
    ],
    entry_points='''
        [console_scripts]
        chips=user_snapshot.snapshot:cli
    ''',
)
