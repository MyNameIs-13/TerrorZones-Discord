from setuptools import setup, find_packages

setup(
    name='TerrorZones-Discord',
    version='0.0.1',
    author='MyNameIs-13',
    description="discord webhook which informs about D2:R Terrorzones",
    scripts=['src/main.py'],
    install_requires=['requests', 'schedule', 'python-dotenv', 'discord_webhook'],
    packages=find_packages()
)
