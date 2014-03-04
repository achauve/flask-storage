from setuptools import setup, Command
import subprocess


class PyTest(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        errno = subprocess.call(['py.test'])
        raise SystemExit(errno)


setup(
    name='Flask-Storage-Helpers',
    version='0.1.5',
    url='http://github.com/achauve/flask-storage-helpers',
    license='MIT',
    author='Konsta Vesterinen',
    author_email='konsta.vesterinen@gmail.com',
    description='Various file storage backends for Flask apps.',
    long_description= open('README.rst').read(),
    packages=['flask_storage_helpers'],
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'Flask>=0.7',
        'boto>=2.5.2',
        'python-cloudfiles>=1.7.10'
    ],
    cmdclass={'test': PyTest},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
