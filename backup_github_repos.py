# Written by K. M. Knausgård 2023-04-26
import os
import sys
import subprocess
import logging
import time
from github import Github
from requests.exceptions import RequestException

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class GithubBackup:
    def __init__(self, token, rate_limit_seconds=0):
        self.github = Github(token)
        self.rate_limit_seconds = rate_limit_seconds

    def get_repositories(self):
        try:
            repos = self.github.get_user().get_repos()
            return sorted(repos, key=lambda r: r.updated_at, reverse=True)
        except RequestException as e:
            logging.error(f"Network error: {e}")
            sys.exit(1)
        except Github.GithubException as e:
            logging.error(f"GitHub API error: {e}")
            sys.exit(1)

    def display_repositories(self, repos):
        print("Repositories:")
        for repo in repos:
            repo_type = "Private" if repo.private else "Public"
            print(f"{repo_type}: {repo.name} (Last updated: {repo.updated_at})")

    def verify_repository(self, target_dir):
        try:
            result = subprocess.run(
                ["git", "-C", target_dir, "fsck"],
                check=True,
                capture_output=True,
                text=True,
            )
            logging.info(f"Backup verification for {target_dir} successful")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Backup verification for {target_dir} failed: {e.output}")
            return False

    def clone_or_update_repository(self, repo, backup_dir):
        repo_url = repo.ssh_url if "ssh://" in repo.ssh_url else repo.clone_url
        repo_name = repo.name
        target_dir = os.path.join(backup_dir, repo_name)

        if os.path.exists(target_dir):
            logging.info(f"Updating {repo_name} in {backup_dir}")
            try:
                subprocess.run(
                    ["git", "-C", target_dir, "fetch", "--all", "--prune"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    ["git", "-C", target_dir, "merge"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                logging.info(f"Successfully updated {repo_name} in {backup_dir}")
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to update {repo_name} in {backup_dir}: {e.output}")
            return

        try:
            logging.info(f"Cloning {repo_name} to {backup_dir}")
            subprocess.run(
                [
                    "git",
                    "lfs",
                    "clone",
                    "--recursive",
                    "-c",
                    "submodule.recurse=true",
                    repo_url,
                    target_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            logging.info(f"Successfully cloned {repo_name} to {backup_dir}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to clone {repo_name} to {backup_dir}: {e.output}")

        self.verify_repository(target_dir)

    def backup_repositories(self):
        repos = self.get_repositories()
        self.display_repositories(repos)

        confirm = input("Do you want to backup these repositories? (yes/no) ")
        if confirm.lower() != "yes":
            print("Backup canceled.")
            return

        for repo in repos:
            backup_dir = "public_repos" if repo.private is False else "private_repos"
            os.makedirs(backup_dir, exist_ok=True)
            self.clone_or_update_repository(repo, backup_dir)
            if self.rate_limit_seconds > 0:
                time.sleep(self.rate_limit_seconds)   

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backup_github_repos.py <GitHub Personal Access Token> [rate_limit_seconds]")
        sys.exit(1)

    token = sys.argv[1]
    rate_limit_seconds = int(sys.argv[2]) if len(sys.argv) >= 3 else 1.0
    backup = GithubBackup(token, rate_limit_seconds)
    
    backup.backup_repositories()
