import os
import re
from dotenv import load_dotenv

load_dotenv()
pyins = r'python -m PyInstaller --noconfirm --clean --log-level=WARN --windowed --name "Video Scoring" --add-data="video_scoring/resources/;video_scoring/resources/" --add-data="video_scoring/resources/dark/;video_scoring/resources/dark/"  --hidden-import qtpy --icon="..\resources\icon_gray.ico" main.py'


def replace_env_var(match: re.Match):
    # strip quotes and ) from the match
    match = match.group(1)
    return f"'{os.getenv(match)}'"


def check_version_match():
    with open("installer.iss", "r") as f:
        installer = f.read()
        # get the version from the installer
        installer_version = re.search(
            r'#define MyAppVersion "([0-9.]+)"', installer
        ).group(1)
    with open("main.py", "r") as f:
        main = f.read()
        # get the version from main
        main_version = re.search(r'VERSION = "([0-9.]+)"', main).group(1)
    if installer_version != main_version:
        print(
            f"""Version mismatch!
Installer: {installer_version}
Main: {main_version}
"""
        )
        exit(1)
    else:
        print(f"Version match: {installer_version}")


def run_tests():
    print("I should really make some tests...")


def build_main():
    with open("main.py", "r+") as f:
        BUILD_MAIN = f.read()
        # replace any os.getenv calls with the actual value

        DEV_MAIN = BUILD_MAIN
        # replace any os.getenv calls with the actual value
        BUILD_MAIN = re.sub(r'os\.getenv\("([A-Z_]+)"\)', replace_env_var, BUILD_MAIN)
        BUILD_MAIN = re.sub(r'(environment=")[^"]*(")', r"\1production\2", BUILD_MAIN)
        # now rewrite the file
        # new file for debugging
        f.seek(0)
        f.write(BUILD_MAIN)
        f.truncate()

    # now run pyinstaller
    os.system(pyins)

    # now rewrite the file back to dev
    with open("main.py", "w") as f:
        # rewrite the file
        f.write(DEV_MAIN)


def run_installer():
    iscc_path = (
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"  # change this to your path
    )
    os.system(f'"{iscc_path}" installer.iss')


if __name__ == "__main__":
    check_version_match()
    run_tests()
    build_main()
    run_installer()
