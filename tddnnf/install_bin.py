"""Install the d4v2 binary compiler for tddnnf."""

import argparse
import os
import stat
import subprocess
from pathlib import Path

D4_REPO = "https://github.com/ecivini/d4v2"
D4_BRANCH = "circuits_with_projected_vars"
LIBPATOH_URL = "https://faculty.cc.gatech.edu/~umit/PaToH/patoh-Linux-x86_64.tar.gz"


def get_bin_dir() -> Path:
    return Path(__file__).resolve().parent / "bin"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{proc.stderr}")


def install_d4(install_dir: Path) -> Path:
    install_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = install_dir / "repo"

    print(f"Cloning {D4_REPO}...")
    _run(["git", "clone", "--depth", "1", "-b", D4_BRANCH, D4_REPO, str(repo_dir)])

    old = Path.cwd()
    os.chdir(str(repo_dir))
    try:
        patoh_dir = repo_dir / "3rdParty" / "patoh"
        patoh_dir.mkdir(parents=True, exist_ok=True)

        print("Downloading libpatoh...")
        _run(["curl", "-L", LIBPATOH_URL, "--output", "libpatoh.tar.gz"])
        tmp = repo_dir / "tmp_patoh"
        tmp.mkdir(exist_ok=True)
        _run(["tar", "-xzf", "libpatoh.tar.gz", "-C", str(tmp)])
        Path("libpatoh.tar.gz").unlink()
        import platform

        arch = platform.machine()
        mach_map = {"x86_64": "Linux-x86_64", "aarch64": "Linux-aarch64", "arm64": "Linux-aarch64"}
        plat = mach_map.get(arch, f"Linux-{arch}")
        lib = tmp / "build" / plat / "libpatoh.a"
        (patoh_dir / "libpatoh.a").write_bytes(lib.read_bytes())
        _run(["rm", "-rf", str(tmp)])

        os.chdir(str(repo_dir / "demo" / "compiler"))
        print("Compiling d4...")
        _run(["bash", "./build.sh"])

        binary = repo_dir / "demo" / "compiler" / "build" / "compiler"
        target = install_dir / "d4.bin"
        target.write_bytes(binary.read_bytes())
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print("Cleaning up...")
        return target
    finally:
        os.chdir(str(old))
        _run(["rm", "-rf", str(repo_dir)])


def main() -> None:
    parser = argparse.ArgumentParser(description="Install d4v2 binary compiler")
    parser.add_argument("--d4", action="store_true", help="Install the d4 dDNNF compiler")
    args = parser.parse_args()

    if args.d4:
        bin_dir = get_bin_dir()
        bin_dir.mkdir(parents=True, exist_ok=True)
        target = install_d4(bin_dir)
        print(f"d4 installed at {target}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
