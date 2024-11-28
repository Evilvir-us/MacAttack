import subprocess
import os

def modify_python_file(file_path):
    """Disable debugging"""
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
        with open(file_path, 'w') as file:
            for line in lines:
                if "logging.basicConfig(level=logging.DEBUG)" in line:
                    file.write("#" + line)
                else:
                    file.write(line)
        
        print(f"File {file_path} successfully modified.")
    except Exception as e:
        print(f"Error modifying file: {e}")
        raise

def unmodify_python_file(file_path):
    """Re-enable debugging"""
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
        with open(file_path, 'w') as file:
            for line in lines:
                if line.strip().startswith("#logging.basicConfig(level=logging.DEBUG)"):
                    file.write(line.lstrip('#').lstrip())
                else:
                    file.write(line)
        
        print(f"File {file_path} successfully restored.")
    except Exception as e:
        print(f"Error restoring file: {e}")
        raise

def unmodify_python_file(file_path):
    """Restores the original state of the Python file by uncommenting the logging configuration line if necessary."""
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
        with open(file_path, 'w') as file:
            for line in lines:
                if line.strip().startswith("#logging.basicConfig(level=logging.DEBUG)") and not line.strip().startswith("logging.basicConfig(level=logging.DEBUG)"):
                    file.write(line.lstrip('#').lstrip())
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
        subprocess.check_call(['copy', 'dist\\MacAttack.exe', '.\\'], shell=True)
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
