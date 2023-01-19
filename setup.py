import setuptools

with open('README.md', 'r') as f:
    readme_text = f.read()

setuptools.setup(
    name='farragone',
    version='0.2.4.dev',
    author='Joseph Lansdowne',
    author_email='ikn@ikn.org.uk',
    description='Batch file renamer for programmers',
    long_description=readme_text,
    long_description_content_type='text/markdown',
    url='http://ikn.org.uk/app/farragone',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3.1',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ],
)
