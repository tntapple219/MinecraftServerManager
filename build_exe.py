import os
import sys 
import shutil
from nuitka.__main__ import main as nuitka_main

# --- 1. Define the Nuitka compilation arguments ---
nuitka_options = [
    # Core settings: Target module and compilation type
    "main.py",
    "--standalone",
    "--onefile",
    "--include-data-files=app.ico=app.ico", 
    
    "--enable-plugin=tk-inter", 
    "--windows-console-mode=disable",
    
    "--windows-icon-from-ico=app.ico",
    "--company-name=TNTAPPLE",
    "--product-name=TNTAPPLE",
    "--product-version=1.0.0.0",
    # Output directory setting
    "--output-dir=build",
]

# --- 2. Execute Nuitka compilation ---
print("🚀 Starting Nuitka compilation...")

# **關鍵修正**：模擬命令列環境
# 1. 儲存原始 sys.argv
original_argv = sys.argv
# 2. 設置新的 sys.argv，讓 nuitka_main 讀取它
#    第一個元素必須是腳本名稱本身，然後才是參數
sys.argv = ["nuitka"] + nuitka_options 

try:
    nuitka_main() # <-- 修正：現在不帶任何位置參數呼叫 main()
finally:
    # 3. 恢復原始的 sys.argv，這是個好習慣！
    sys.argv = original_argv 

# --- 3. Organize the output (Mimicking the 'Release' folder from README) ---
release_folder = "Release"

# Ensure the final output directory exists
if not os.path.exists(release_folder):
    os.makedirs(release_folder)

# Find the compiled .exe file (usually located in the build folder)
source_exe_path = os.path.join("build", "main.onefile", "main.exe")
# Rename the executable as suggested in the README
target_exe_path = os.path.join(release_folder, "MinecraftServerManager.exe") 

if os.path.exists(source_exe_path):
    print(f"✨ Executable found, moving to {target_exe_path}")
    shutil.copy(source_exe_path, target_exe_path)
    
    # Copy the documentation files
    shutil.copy("README.md", os.path.join(release_folder, "README.md"))
    shutil.copy("README_zh.md", os.path.join(release_folder, "README_zh.md"))
    
    print(f"🎉 Build complete! Final result is in the '{release_folder}' folder.")
    
    # Clean up the temporary build directory
    shutil.rmtree("build", ignore_errors=True)
else:
    print("❌ Error: The final executable main.exe was not found. Compilation might have failed.")