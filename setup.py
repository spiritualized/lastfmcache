from distutils.core import setup
setup(
    name = 'lastfmcache',
    packages = ['lastfmcache'],
    version = '1.0.3',
    description = 'Python interface to the Last.FM API/website with caching support',
    url = 'https://github.com/spiritualized/lastfmcache',
    download_url = 'https://github.com/spiritualized/lastfmcache/archive/v1.0.3.tar.gz',
    keywords = ['lastfm', 'python', 'cache', 'api'],
    install_requires = [
                    'bs4',
                    'pylast',
                    'requests',
                    'sqlalchemy',
                ],

    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
)
