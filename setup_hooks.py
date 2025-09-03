"""
Git Hook Setup Script
Sets up post-push detection for automation
"""

import sys
import platform
import subprocess
from pathlib import Path


class HookSetup:
    def __init__(self):
        self.git_dir = self.find_git_directory()
        self.hooks_dir = self.git_dir / "hooks" if self.git_dir else None
        self.script_dir = Path(__file__).parent.absolute()

    def find_git_directory(self):
        """Find the .git directory and verify it's the CSF repo"""
        current = Path.cwd()
        while current != current.parent:
            git_dir = current / ".git"
            if git_dir.exists():
                # Verify this is the CSF repository
                if self.verify_csf_repository(current):
                    return git_dir
                else:
                    print(
                        "Error: This script only works with the CSF integration testscripts repository"
                    )
                    print(f"Current repository: {self.get_repo_url(current)}")
                    print(
                        "Expected: https://code.xtend.infor.com/Infor/csf-integration-testscripts"
                    )
                    return None
            current = current.parent
        return None

    def verify_csf_repository(self, repo_path):
        """Verify we're in the correct CSF repository"""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False

            remote_url = result.stdout.strip().lower()

            # Check if this is the CSF integration testscripts repo
            expected_identifiers = [
                "csf-integration-testscripts",
                "infor/csf-integration-testscripts",
            ]

            return any(identifier in remote_url for identifier in expected_identifiers)

        except Exception:
            return False

    def get_repo_url(self, repo_path):
        """Get the repository URL for display purposes"""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return "Unknown"
        except Exception:
            return "Unknown"

    def create_push_detector_script(self):
        """Create a lightweight push detector script"""
        detector_script = self.script_dir / "push_detector.py"

        script_content = f'''
#!/usr/bin/env python3
"""
Lightweight Push Detector
Runs after successful push to check if automation should trigger
ONLY WORKS WITH CSF INTEGRATION TESTSCRIPTS REPOSITORY
"""

import subprocess
import sys
import os
from pathlib import Path

def verify_csf_repository():
    """Verify we're in the correct CSF repository"""
    try:
        result = subprocess.run(['git', 'remote', 'get-url', 'origin'], 
                            capture_output=True, text=True)
        if result.returncode != 0:
            return False
            
        remote_url = result.stdout.strip().lower()
        
        # Check if this is the CSF integration testscripts repo
        expected_identifiers = [
            'csf-integration-testscripts',
            'infor/csf-integration-testscripts'
        ]
        
        return any(identifier in remote_url for identifier in expected_identifiers)
        
    except Exception:
        return False

def main():
    """Check if we should run automation after push"""
    
    # Verify we're in the correct repository
    if not verify_csf_repository():
        print("ERROR: This automation only works with the CSF integration testscripts repository")
        return
    
    # Only run if --auto-build is in the original push command
    # This is set by our custom push alias
    if "--auto-build" not in sys.argv:
        print("Push completed. Run 'python script.py --build' to trigger automation.")
        return
    
    print("Auto-build enabled! Starting Jenkins-TEM automation...")
    
    # Store the current directory (CSF repo) before changing directories
    original_dir = os.getcwd()
    
    # Path to the automation script
    ci_cd_dir = Path("C:/Code/ci-cd-pipeline")
    script_path = ci_cd_dir / "script.py"

    # Run automation with build flag, but keep the CSF repo as working directory
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--build"],
            cwd=original_dir,  # Keep CSF repo as working directory
            capture_output=False,
            text=True,
        )

        if result.returncode == 0:
            print("Automation completed successfully!")
        else:
            print("Automation failed. Check output above.")
    except Exception as e:
        print(f"Error running automation: {{e}}")

if __name__ == "__main__":
    main()
'''

        with open(detector_script, "w") as f:
            f.write(script_content)

        # Make executable on Unix systems
        if platform.system() != "Windows":
            detector_script.chmod(0o755)

        return detector_script

    def setup_git_aliases(self):
        """Set up convenient git aliases"""
        print("Setting up git aliases...")

        try:
            subprocess.run(
                ["git", "config", "alias.push-only", "push origin master"], check=True
            )

            # Push with automation trigger
            script_path = self.script_dir / "push_detector.py"
            if platform.system() == "Windows":
                push_command = (
                    f'!git push origin master && python "{script_path}" --auto-build'
                )
            else:
                push_command = (
                    f'!git push origin master && python3 "{script_path}" --auto-build'
                )

            subprocess.run(
                ["git", "config", "alias.push-build", push_command], check=True
            )

            print("Git aliases created successfully!")
            return True

        except subprocess.CalledProcessError as e:
            print(f"Error setting up git aliases: {e}")
            return False

    def setup_hooks(self):
        """Set up git hooks"""
        if not self.git_dir:
            print("Not in the CSF integration testscripts repository!")
            print("Please run this script from within the CSF repo directory.")
            return False

        if not self.hooks_dir:
            print("Git hooks directory not found!")
            return False

        # Create push detector script
        detector_script = self.create_push_detector_script()
        print(f"Created push detector: {detector_script}")

        # Set up git aliases
        alias_success = self.setup_git_aliases()

        if alias_success:
            print("")
            print("SETUP COMPLETE!")
            print("")
            print(
                "This automation is now configured for the CSF integration testscripts repository only."
            )
            print("")
            print("USAGE:")
            print("  git push-only       # Normal push (no automation)")
            print("  git push-build      # Push + trigger automation")
            print("")
            print("MANUAL TRIGGER:")
            print("  python script.py --check    # Check for new commits")
            print("  python script.py --build    # Run automation manually")
            print("")
            print(
                "SAFETY: Only works in CSF repo, only 'git push-build' triggers automation."
            )

        return alias_success

    def remove_hooks(self):
        """Remove the hooks and aliases"""
        try:
            # Remove git aliases
            subprocess.run(
                ["git", "config", "--unset", "alias.push-only"], capture_output=True
            )
            subprocess.run(
                ["git", "config", "--unset", "alias.push-build"], capture_output=True
            )

            # Remove detector script
            detector_script = self.script_dir / "push_detector.py"
            if detector_script.exists():
                detector_script.unlink()

            print("Hooks and aliases removed successfully!")
            return True

        except Exception as e:
            print(f"Error removing hooks: {e}")
            return False


def main():
    """Main setup function"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--remove":
            setup = HookSetup()
            setup.remove_hooks()
            return
        elif sys.argv[1] == "--help":
            print("Git Hook Setup for Jenkins-TEM Automation")
            print("")
            print("USAGE:")
            print("  python setup_hooks.py           # Set up hooks and aliases")
            print("  python setup_hooks.py --remove  # Remove hooks and aliases")
            print("  python setup_hooks.py --help    # Show this help")
            return

    print("Setting up Git hooks for Jenkins-TEM automation...")
    print("")

    setup = HookSetup()
    success = setup.setup_hooks()

    if not success:
        print("Setup failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
