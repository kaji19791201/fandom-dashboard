import subprocess


class ClaudeCLIProvider:
    def complete(self, prompt: str, image_url: str = "") -> str:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"claude CLI error: {result.stderr}")
        return result.stdout.strip()
