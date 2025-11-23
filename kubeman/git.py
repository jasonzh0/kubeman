import tempfile
import shutil
from pathlib import Path
from kubeman.config import Config
from kubeman.executor import CommandExecutor, get_executor


class GitManager:
    """
    Manager for Git operations related to manifest repository management.

    Provides methods to push rendered manifests to a Git repository.
    """

    def __init__(self, executor: CommandExecutor = None):
        """
        Initialize the GitManager.

        Args:
            executor: CommandExecutor instance (defaults to global executor)
        """
        self.executor = executor or get_executor()

    def fetch_commit_hash(self) -> str:
        """
        Fetch the current git commit hash from environment variable.

        Returns:
            str: The current commit hash.

        Raises:
            ValueError: If STABLE_GIT_COMMIT is not set
        """
        return Config.git_commit()

    def fetch_branch_name(self) -> str:
        """
        Fetch the current branch name from environment variable.

        Returns:
            str: The current branch name.

        Raises:
            ValueError: If STABLE_GIT_BRANCH is not set
        """
        return Config.git_branch()

    def fetch_manifest_dir(self) -> Path:
        """
        Fetch the rendered manifest directory from environment variable.

        Returns:
            Path: The path to the rendered manifest directory.

        Raises:
            ValueError: If RENDERED_MANIFEST_DIR is not set
        """
        return Path(Config.rendered_manifest_dir())

    def push_manifests(self, repo_url: str = None) -> None:
        """
        Check out the manifests repository, switch to the current branch,
        copy manifests, create a commit, and push the changes.

        Args:
            repo_url: The Git repository URL to push manifests to.
                     If not provided, reads from MANIFEST_REPO_URL environment variable.

        Raises:
            ValueError: If repo_url is not provided and MANIFEST_REPO_URL is not set
        """
        if not repo_url:
            repo_url = Config.manifest_repo_url()
            if not repo_url:
                raise ValueError(
                    "repo_url must be provided or MANIFEST_REPO_URL environment variable must be set"
                )

        # Get the manifests directory path
        manifests_dir = self.fetch_manifest_dir()
        # Use a context manager to ensure the temporary directory is cleaned up
        with tempfile.TemporaryDirectory(prefix="repo_clone_") as repo_temp_dir:
            repo_temp_path = Path(repo_temp_dir)

            # Clone the manifests repository
            self.executor.run(["git", "clone", repo_url, str(repo_temp_path)], check=True)

            # Get the current branch name
            branch_name = self.fetch_branch_name()

            # Check if branch exists on the remote repository
            check_result = self.executor.run_silent(
                ["git", "ls-remote", "--heads", "origin", branch_name],
                cwd=repo_temp_path,
            )
            branch_exists = bool(check_result.stdout.strip())
            print(f"Checking if branch '{branch_name}' exists on remote: {branch_exists}")

            # Fetch only the branch we need
            if branch_exists:
                # Fetch only the existing branch
                self.executor.run(
                    ["git", "fetch", "origin", branch_name], cwd=repo_temp_path, check=True
                )
                # Checkout and track the remote branch
                self.executor.run(
                    ["git", "checkout", "-B", branch_name, f"origin/{branch_name}"],
                    cwd=repo_temp_path,
                    check=True,
                )
            else:
                # Fetch only main branch for new branch creation
                self.executor.run(
                    ["git", "fetch", "origin", "main"], cwd=repo_temp_path, check=True
                )
                # Branch from latest main
                self.executor.run(
                    ["git", "checkout", "origin/main", "-b", branch_name],
                    cwd=repo_temp_path,
                    check=True,
                )

            # Delete everything in repo_temp_dir except .git folder
            for item in repo_temp_path.iterdir():
                if item.name != ".git" and item.exists():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()

            # Copy manifests to repo directory
            shutil.copytree(manifests_dir, repo_temp_path, dirs_exist_ok=True)

            # Commit manifests back
            commit_sha = self.fetch_commit_hash()
            self.executor.run(["git", "add", "."], cwd=repo_temp_path, check=True)
            self.executor.run(
                [
                    "git",
                    "commit",
                    "--allow-empty",
                    "-m",
                    f"Update manifests for branch {branch_name} (commit {commit_sha})",
                ],
                cwd=repo_temp_path,
                check=True,
            )
            self.executor.run(
                ["git", "push", "origin", branch_name], cwd=repo_temp_path, check=True
            )


if __name__ == "__main__":
    from pathlib import Path

    print(f"Starting push_manifests. Working directory: {Path.cwd()}")

    try:
        git_instance = GitManager()
        git_instance.push_manifests()
    except Exception as e:
        print(f"Error in push_manifests: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
