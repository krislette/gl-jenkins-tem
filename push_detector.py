#!/usr/bin/env python3
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
        message_text = Text(f"[SUCCESS] {message}", style="bold green")
    elif level.upper() == "ERROR":
        message_text = Text(f"[ERROR] {message}", style="bold red")
    elif level.upper() == "FAILED":
        message_text = Text(f"[FAILED] {message}", style="bold red")
    elif level.upper() == "WARNING":
        message_text = Text(f"[WARNING] {message}", style="bold yellow")
    else:
        # Regular info messages - make keywords bold
        full_text = f"[INFO] {message}"
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
        log(f"Error running automation: {e}", "ERROR")

if __name__ == "__main__":
    main()
