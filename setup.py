from distutils.core import setup
setup(
    name = 'lastfmcache',
    packages = ['lastfmcache'],
    version = '1.0.0',
    description = 'Python interface to the Last.FM API/website with caching support',   # Give a short description about your library
    url = 'https://github.com/spiritualized/lastfmcache',   # Provide either the link to your github or to your website
    download_url = 'https://github.com/spiritualized/lastfmcache/archive/v1.0.0.tar.gz',    # I explain this later on
    keywords = ['lastfm', 'python', 'cache', 'api'],   # Keywords that define your package best
    install_requires = [
                    'bs4'
                    'pylast'
                    'requests'
                    'sqlalchemy'
                    'sqlite3'
                ],

    classifiers = [
        'Development Status :: 5 - Production/Stable',      # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package
        'Intended Audience :: Developers',      # Define that your audience are developers
        'Topic :: Software Development :: Build Tools',
        'Programming Language :: Python :: 3',      #Specify which python versions that you want to support
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
)
