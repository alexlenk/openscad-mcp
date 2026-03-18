"""Container runtime abstraction for Docker and Finch."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from openscad_mcp_server.models import ContainerResult


class ContainerError(Exception):
    """Raised when a container operation fails."""

    def __init__(self, message: str, *, image: str | None = None) -> None:
        self.image = image
        super().__init__(message)


class ContainerManager:
    """Manages container operations across Docker and Finch runtimes."""

    SUPPORTED_RUNTIMES = ("docker", "finch")

    def __init__(self, runtime: str, executable: str) -> None:
        if runtime not in self.SUPPORTED_RUNTIMES:
            raise ValueError(f"Unsupported runtime: {runtime!r}. Must be one of {self.SUPPORTED_RUNTIMES}")
        self.runtime = runtime
        self.executable = executable

    # -- public helpers exposed for testability --

    def build_run_command(
        self,
        image: str,
        command: list[str],
        mounts: dict[str, str] | None = None,
    ) -> list[str]:
        """Build the CLI arg list for a container run invocation.

        ``mounts`` maps host paths to container paths.
        """
        cmd: list[str] = [self.executable, "run", "--rm"]
        for host_path, container_path in (mounts or {}).items():
            resolved = str(Path(host_path).resolve())
            cmd += ["-v", f"{resolved}:{container_path}"]
        cmd.append(image)
        cmd.extend(command)
        return cmd

    # -- core operations --

    async def run(
        self,
        image: str,
        command: list[str],
        mounts: dict[str, str] | None = None,
        timeout: int = 300,
    ) -> ContainerResult:
        """Run a container and return its result."""
        cmd = self.build_run_command(image, command, mounts)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise ContainerError(
                f"Container runtime unavailable: {self.runtime!r} executable not found at {self.executable!r}",
                image=image,
            )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise ContainerError(
                f"Container timed out after {timeout}s running: {' '.join(cmd)}",
                image=image,
            )

        return ContainerResult(
            exit_code=proc.returncode or 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
        )

    async def image_exists(self, image: str) -> bool:
        """Check whether a container image is available locally."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.executable, "image", "inspect", image,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    async def build_image(self, dockerfile: str, tag: str) -> None:
        """Build a container image from a Dockerfile path."""
        context = str(Path(dockerfile).parent)
        proc = await asyncio.create_subprocess_exec(
            self.executable, "build", "-f", dockerfile, "-t", tag, context,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        if proc.returncode != 0:
            raise ContainerError(
                f"Failed to build image {tag!r} from {dockerfile!r}: {stderr_bytes.decode('utf-8', errors='replace')}",
                image=tag,
            )

    # -- static detection --

    @staticmethod
    async def detect() -> tuple[str, str] | None:
        """Probe for Docker then Finch. Return ``(runtime, executable)`` or ``None``."""
        for runtime in ContainerManager.SUPPORTED_RUNTIMES:
            executable = shutil.which(runtime)
            if executable is None:
                continue
            # Verify the runtime actually works
            try:
                proc = await asyncio.create_subprocess_exec(
                    executable, "info",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()
                if proc.returncode == 0:
                    return runtime, executable
            except (FileNotFoundError, OSError):
                continue
        return None
