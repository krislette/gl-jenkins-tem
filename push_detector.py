
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
        print("[ERROR] This automation only works with the CSF integration testscripts repository")
        return
    
    # Only run if --auto-build is in the original push command
    # This is set by our custom push alias
    if "--auto-build" not in sys.argv:
        print("")
        print("[INFO] Push completed. Run 'python script.py --build' to trigger automation.")
        return
    
    print("")
    print("[SUCCESS] Your code has been shipped to csf-integration-testscripts")
    print("[SUCCESS] Auto-build enabled! Starting Jenkins-TEM automation...")
    
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
            print("[SUCCESS] Automation completed successfully!]")
        else:
            print("[FAILED] Automation failed. Check output above.")
    except Exception as e:
        print(f"[ERROR] Error running automation: {e}")

if __name__ == "__main__":
    main()
