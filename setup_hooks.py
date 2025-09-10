"""
Git Hook Setup Script
Sets up post-push detection for automation
"""

# Regular imports
import sys
import platform
import subprocess
from pathlib import Path

# Rich imports
from rich.console import Console
from rich.text import Text
from rich.panel import Panel


class HookSetup:
    def __init__(self):
        self.console = Console()
        self.git_dir = self.find_git_directory()
        self.hooks_dir = self.git_dir / "hooks" if self.git_dir else None
        self.script_dir = Path(__file__).parent.absolute()

    def log(self, level, message):
        """Log with status level"""
        if level.lower() == "success":
            message_text = Text(f"[SUCCESS] {message}", style="bold green")
        elif level.lower() == "error":
            message_text = Text(f"[ERROR] {message}", style="bold red")
        elif level.lower() == "failed":
            message_text = Text(f"[FAILED] {message}", style="bold red")
        elif level.lower() == "warning":
            message_text = Text(f"[WARNING] {message}", style="bold yellow")
        else:
            # Regular info messages - make keywords bold
            full_text = f"[INFO] {message}"
            message_text = Text()
            words = full_text.split()

            # Keywords to emphasize
            keywords = [
                "Git",
                "Jenkins",
                "TEM",
                "automation",
                "CSF",
                "repository",
                "SUCCESS",
                "FAILED",
                "SETUP",
                "COMPLETE",
                "hooks",
                "aliases",
            ]

            for i, word in enumerate(words):
                if any(keyword.lower() in word.lower() for keyword in keywords):
                    message_text.append(word, style="bold")
                else:
                    message_text.append(word)

                if i < len(words) - 1:
                    message_text.append(" ")

        self.console.print(message_text)

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
                    self.log(
                        "error",
                        "This script only works with the CSF integration testscripts repository",
                    )
                    self.log(
                        "info", f"Current repository: {self.get_repo_url(current)}"
                    )
                    self.log(
                        "info",
                        "Expected: https://code.xtend.infor.com/Infor/csf-integration-testscripts",
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

        script_content = f'''#!/usr/bin/env python3
"""
Lightweight Push Detector
Runs after successful push to check if automation should trigger
ONLY WORKS WITH CSF INTEGRATION TESTSCRIPTS REPOSITORY
"""

# Regular imports
import subprocess
import sys
import os
from pathlib import Path

# Rich imports
from rich.console import Console
from rich.text import Text


def log(message, level="INFO"):
    """Enhanced log with colors using Rich (no timestamps for push detector)"""
    console = Console()
    
    if level.upper() == "SUCCESS":
        message_text = Text(f"[SUCCESS] {{message}}", style="bold green")
    elif level.upper() == "ERROR":
        message_text = Text(f"[ERROR] {{message}}", style="bold red")
    elif level.upper() == "FAILED":
        message_text = Text(f"[FAILED] {{message}}", style="bold red")
    elif level.upper() == "WARNING":
        message_text = Text(f"[WARNING] {{message}}", style="bold yellow")
    else:
        # Regular info messages - make keywords bold
        full_text = f"[INFO] {{message}}"
        message_text = Text()
        words = full_text.split()
        
        # Keywords to emphasize
        keywords = [
            "Push", "automation", "Jenkins", "TEM", "CSF", "build", 
            "completed", "shipped", "Auto-build", "enabled"
        ]
        
        for i, word in enumerate(words):
            if any(keyword.lower() in word.lower() for keyword in keywords):
                message_text.append(word, style="bold")
            else:
                message_text.append(word)
            
            if i < len(words) - 1:
                message_text.append(" ")
    
    console.print(message_text)

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
        log("This automation only works with the CSF integration testscripts repository", "ERROR")
        return
    
    # Only run if --auto-build is in the original push command
    # This is set by our custom push alias
    if "--auto-build" not in sys.argv:
        print("")
        log("Push completed. Run 'python script.py --build' to trigger automation.")
        return
    
    print("")
    log("Your code has been shipped to csf-integration-testscripts", "SUCCESS")
    log("Auto-build enabled! Starting Jenkins-TEM automation...", "SUCCESS")
    
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
            log("Automation completed successfully!", "SUCCESS")
        else:
            log("Automation failed. Check output above.", "FAILED")
    except Exception as e:
        log(f"Error running automation: {{e}}", "ERROR")

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
        self.log("info", "Setting up git aliases...")

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

            self.log("success", "Git aliases created successfully!")
            return True

        except subprocess.CalledProcessError as e:
            self.log("error", f"Error setting up git aliases: {e}")
            return False

    def setup_hooks(self):
        """Set up git hooks"""
        if not self.git_dir:
            self.log("error", "Not in the CSF integration testscripts repository!")
            self.log(
                "info", "Please run this script from within the CSF repo directory."
            )
            return False

        if not self.hooks_dir:
            self.log("error", "Git hooks directory not found!")
            return False

        # Create push detector script
        detector_script = self.create_push_detector_script()
        self.log("success", f"Created push detector: {detector_script}")

        # Set up git aliases
        alias_success = self.setup_git_aliases()

        if alias_success:
            self.log("success", "SETUP COMPLETE!")
            self.log("info", "Preparing information panel...")

            setup_info = Panel(
                """
        [bold white]This automation is now configured for the CSF integration testscripts repository only.[/bold white]

        [bold green]USAGE (Recommended):[/bold green]
        git push-only       # Normal push (no automation)
        git push-build      # Push + trigger automation

        [bold yellow]MANUAL TRIGGER (Not Recommended):[/bold yellow]
        python script.py --check    # Check for new commits
        python script.py --build    # Run automation manually

        [bold blue]SAFETY:[/bold blue]
        Only works in CSF repo, only 'git push-build' triggers automation.

        [bold white]For complete information, setup details, usage, warnings, and common issues:[/bold white]
        See the README on the repository.
                """,
                title="Setup Complete",
                border_style="green",
            )
            self.console.print(setup_info)

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

            self.log("success", "Hooks and aliases removed successfully!")
            return True

        except Exception as e:
            self.log("error", f"Error removing hooks: {e}")
            return False


def main():
    """Main setup function"""
    setup = HookSetup()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--remove":
            setup.remove_hooks()
            return
        elif sys.argv[1] == "--help":
            help_panel = Panel(
                """
        [bold green]Git Hook Setup for Jenkins-TEM Automation[/bold green]

        [bold blue]USAGE (Recommended):[/bold blue]
        python setup_hooks.py           # Set up hooks and aliases
        python setup_hooks.py --remove  # Remove hooks and aliases
        python setup_hooks.py --help    # Show this help
                """,
                title="Help",
                border_style="blue",
            )
            setup.console.print(help_panel)
            return

    setup.console.print(
        Text("Setting up Git hooks for Jenkins-TEM automation...", style="bold blue")
    )

    success = setup.setup_hooks()

    if not success:
        setup.log("failed", "Setup failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
