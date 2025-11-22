import subprocess
import os
import tempfile
import shutil
import tarfile
from pathlib import Path
import sys


class GitManager:
    """
    A singleton class to interact with Git and fetch the current commit hash and branch name.
    """

    _instance = None
    _commit_hash = None
    _branch_name = None

    def __new__(cls):
        """
        Create a new instance of the GitManager class if one does not already exist.
        Ensures that only one instance of GitManager is created (singleton pattern).
        """
        if cls._instance is None:
            cls._instance = super(GitManager, cls).__new__(cls)
        return cls._instance

    def read_from_env(self, var_name: str) -> str:
        """
        Helper to read an environment variable or exit with error if unset.
        """
        if var_name in os.environ:
            value = os.environ[var_name]
            print(f"Got {var_name} from environment: {value}")
            return value
        else:
            print(f"Failed to find {var_name} in environment variables")
            sys.exit(1)

    def fetch_commit_hash(self) -> str:
        """
        Fetch the current git commit hash from environment variable.

        Returns:
            str: The current commit hash.
        """
        if self._commit_hash is None:
            self._commit_hash = self.read_from_env("STABLE_GIT_COMMIT")
        return self._commit_hash

    def fetch_branch_name(self) -> str:
        """
        Fetch the current branch name from environment variable.

        Returns:
            str: The current branch name.
        """
        if self._branch_name is None:
            self._branch_name = self.read_from_env("STABLE_GIT_BRANCH")
        return self._branch_name

    def fetch_manifest_dir(self) -> str:
        """
        Fetch the rendered manifest directory from environment variable.

        Returns:
            str: The path to the rendered manifest directory.
        """
        return self.read_from_env("RENDERED_MANIFEST_DIR")

    def push_manifests(self, repo_url: str = None) -> None:
        """
        Check out the manifests repository, switch to the current branch,
        copy manifests, create a commit, and push the changes.

        Args:
            repo_url: The Git repository URL to push manifests to.
                     If not provided, reads from MANIFEST_REPO_URL environment variable.
        """
        if not repo_url:
            repo_url = os.getenv("MANIFEST_REPO_URL")
            if not repo_url:
                raise ValueError(
                    "repo_url must be provided or MANIFEST_REPO_URL environment variable must be set"
                )

        # Get the manifests directory path
        manifests_dir = self.fetch_manifest_dir()
        # Use a context manager to ensure the temporary directory is cleaned up
        with tempfile.TemporaryDirectory(prefix="repo_clone_") as repo_temp_dir:
            # Clone the manifests repository
            subprocess.run(["git", "clone", repo_url, repo_temp_dir], check=True)

            # Get the current branch name
            branch_name = self.fetch_branch_name()

            # Check if branch exists on the remote repository
            check_remote_branch = subprocess.run(
                ["git", "ls-remote", "--heads", "origin", branch_name],
                cwd=repo_temp_dir,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            branch_exists = bool(check_remote_branch.stdout.strip())
            print(f"Checking if branch '{branch_name}' exists on remote: {branch_exists}")

            # Fetch only the branch we need
            if branch_exists:
                # Fetch only the existing branch
                subprocess.run(
                    ["git", "fetch", "origin", branch_name], cwd=repo_temp_dir, check=True
                )
                # Checkout and track the remote branch
                subprocess.run(
                    ["git", "checkout", "-B", branch_name, f"origin/{branch_name}"],
                    cwd=repo_temp_dir,
                    check=True,
                )
            else:
                # Fetch only main branch for new branch creation
                subprocess.run(["git", "fetch", "origin", "main"], cwd=repo_temp_dir, check=True)
                # Branch from latest main
                subprocess.run(
                    ["git", "checkout", "origin/main", "-b", branch_name],
                    cwd=repo_temp_dir,
                    check=True,
                )

            # Delete everything in repo_temp_dir except .git folder
            for item in os.listdir(repo_temp_dir):
                item_path = os.path.join(repo_temp_dir, item)
                if item != ".git" and os.path.exists(item_path):
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)

            # Copy manifests to repo directory
            shutil.copytree(manifests_dir, repo_temp_dir, dirs_exist_ok=True)

            # Commit manifests back
            commit_sha = self.fetch_commit_hash()
            subprocess.run(["git", "add", "."], cwd=repo_temp_dir, check=True)
            subprocess.run(
                [
                    "git",
                    "commit",
                    "--allow-empty",
                    "-m",
                    f"Update manifests for branch {branch_name} (commit {commit_sha})",
                ],
                cwd=repo_temp_dir,
                check=True,
            )
            subprocess.run(["git", "push", "origin", branch_name], cwd=repo_temp_dir, check=True)


if __name__ == "__main__":
    print(f"Starting push_manifests. Working directory: {os.getcwd()}")

    try:
        git_instance = GitManager()
        git_instance.push_manifests()
    except Exception as e:
        print(f"Error in push_manifests: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
