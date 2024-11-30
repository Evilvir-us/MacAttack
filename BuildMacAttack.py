import subprocess
import os

def run_pyinstaller():
    """Runs PyInstaller to create the executable with custom options."""
    try:
        print("Running PyInstaller with custom options...")
        subprocess.check_call([
            'pyinstaller',
            '--onefile',
            '--add-data=include;include',  # Add include directory to the build
            '--icon=icon.ico',
            'MacAttack.pyw'
        ])
        print("PyInstaller finished successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error running PyInstaller: {e}")
        raise

def modify_python_file(file_path):
    """Disable debugging by replacing logging.basicConfig with the commented version."""
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
        with open(file_path, 'w') as file:
            for line in lines:
                if "logging.basicConfig" in line:
                    file.write("#logging.basicConfig(level=logging.DEBUG)\n")  # Replace with commented version
                else:
                    file.write(line)
        print(f"File {file_path} successfully modified.")
    except Exception as e:
        print(f"Error modifying file: {e}")
        raise

def unmodify_python_file(file_path):
    """Re-enable debugging by replacing the commented logging.basicConfig with the active version."""
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
        with open(file_path, 'w') as file:
            for line in lines:
                if "#logging.basicConfig" in line:
                    file.write("logging.basicConfig(level=logging.DEBUG)\n")  # Replace with active version
                else:
                    file.write(line)
        print(f"File {file_path} successfully restored.")
    except Exception as e:
        print(f"Error restoring file: {e}")
        raise

def copy_executable():
    """Copies the generated executable to the current directory."""
    try:
        print("Copying MacAttack.exe to the current directory...")
        source_path = os.path.join('dist', 'MacAttack.exe')
        destination_path = '.'
        subprocess.check_call(['copy', source_path, destination_path], shell=True)
        print("Executable copied successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error copying executable: {e}")
        raise

def main():
    """Main function to execute all steps."""
    modify_python_file('MacAttack.pyw')
    run_pyinstaller()
    copy_executable()
    unmodify_python_file('MacAttack.pyw')
    input("Process complete. Press Enter to exit...")

if __name__ == "__main__":
    main()