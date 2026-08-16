import subprocess
from pathlib import Path

def publish(build_dir: str = "webapp/build", branch: str = "gh-pages") -> None:
    build_path = Path(build_dir)
    if not build_path.exists():
        raise FileNotFoundError(f"build dir non trovata: {build_dir}")

    subprocess.run(["git", "add", "-f", build_dir], check=True)
    diff_result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if diff_result.returncode == 0:
        print("nessuna modifica al sito, skip pubblicazione")
        return

    subprocess.run(["git", "commit", "-m", "chore: aggiorna sito"], check=True)
    subprocess.run(["git", "subtree", "push", "--prefix", build_dir, "origin", branch], check=True)
