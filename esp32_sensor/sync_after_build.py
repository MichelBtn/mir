import shutil
from pathlib import Path

Import("env")

def after_build(source, target, env):
    build_dir = Path(env.subst("$BUILD_DIR"))
    project_dir = Path(env.subst("$PROJECT_DIR"))
    dest_dir = project_dir.parent / "mir_esp_deploy" / "bin"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for filename in ("bootloader.bin", "partitions.bin", "firmware.bin"):
        shutil.copy2(build_dir / filename, dest_dir / filename)

    framework_file = "boot_app0.bin"
    dest_framework_path = dest_dir / framework_file
    platform = env.PioPlatform()
    framework_dir = Path(platform.get_package_dir("framework-arduinoespressif32"))
    framework_path = framework_dir / "tools" / "partitions" / framework_file
    shutil.copy2(framework_path, dest_framework_path)

    print(f"Fichiers synchronisés vers {dest_dir}")

env.AddPostAction("buildprog", after_build)
