try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name="rediscluster",
    version="0.1.0",
    description="",
    author="Johan Grokzen Andersson",
    author_email="Grokzen@gmail.com",
    packages=["rediscluster"],
    install_requires=[
        'redis>=2.9.1'
    ],
    classifiers=(
        # As from https://pypi.python.org/pypi?%3Aaction=list_classifiers
        # 'Development Status :: 1 - Planning',
        # 'Development Status :: 2 - Pre-Alpha',
        'Development Status :: 3 - Alpha',
        # 'Development Status :: 4 - Beta',
        # 'Development Status :: 5 - Production/Stable',
        # 'Development Status :: 6 - Mature',
        # 'Development Status :: 7 - Inactive',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        # 'Programming Language :: Python :: 3.0',
        # 'Programming Language :: Python :: 3.1',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        # 'Environment :: Console',
        'Environment :: Redis',
        'Environment :: Redis Cluster',
        'Environment :: Web Environment',
        'Operating System :: POSIX',
        'Topic :: Redis',
        'Topic :: Redis Cluster'
    )
)
