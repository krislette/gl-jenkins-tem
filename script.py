"""
Jenkins-TEM Automation Script
Automates the build process from Jenkins trigger to TEM execution
"""

import requests
import time
import json
import subprocess
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
)


class BuildAutomator:
    def __init__(self, config_file="C:/Code/ci-cd-pipeline/config.json"):
        """Initialize the automator with configuration"""
        with open(config_file, "r") as f:
            self.config = json.load(f)

        # Verify we're in the correct repository
        if not self.verify_repository():
            raise Exception(
                "This script only works with the CSF integration testscripts repository"
            )

        self.jenkins_url = self.config["jenkins"]["base_url"]
        self.jenkins_auth = (
            self.config["jenkins"]["username"],
            self.config["jenkins"]["api_token"],
        )
        self.tem_url = self.config["tem"]["base_url"]

    def verify_repository(self):
        """Verify we're in the correct CSF repository"""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"], capture_output=True, text=True
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

        except Exception as e:
            self.log(f"Error checking repository: {e}")
            return False

    def log(self, message):
        """Log with timestamp"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def test_jenkins_trigger(self):
        """Test Jenkins API trigger"""
        self.log("Testing Jenkins API trigger...")

        queue_url = self.trigger_jenkins_build()
        if queue_url:
            self.log(f"SUCCESS: Jenkins build triggered! Queue URL: {queue_url}")
            self.log("Check Jenkins manually to see if build started")
            return True
        else:
            self.log("FAILED: Could not trigger Jenkins build")
            return False

    def test_tem_selenium(self):
        """Test TEM Selenium automation without Jenkins build"""
        self.log("Testing TEM Selenium automation...")
        self.log("This will open browser and attempt TEM form filling...")

        return self.execute_tem_automation()

    def check_for_new_commits(self):
        """Check if there are new commits to process"""
        try:
            # Get the latest commit hash
            result = subprocess.run(
                ["git", "rev-parse", "origin/master"], capture_output=True, text=True
            )
            latest_commit = result.stdout.strip()

            # Check if we've processed this commit already
            try:
                with open(".last_processed_commit", "r") as f:
                    last_processed = f.read().strip()
            except FileNotFoundError:
                last_processed = ""

            if latest_commit != last_processed:
                self.log(f"New commit detected: {latest_commit[:8]}")
                return latest_commit
            return None

        except Exception as e:
            self.log(f"Error checking commits: {e}")
            return None

    def trigger_jenkins_build(self):
        """Trigger Jenkins build via API"""
        try:
            self.log("Triggering Jenkins build...")

            build_url = f"{self.jenkins_url}buildWithParameters"
            params = {"CSF_SOHO_VERSION": self.config["jenkins"]["soho_version"]}

            response = requests.post(build_url, auth=self.jenkins_auth, params=params)

            if 200 <= response.status_code < 300:
                self.log("Jenkins build triggered successfully")
                # Get queue item location from response headers
                queue_url = response.headers.get("Location")
                return queue_url
            else:
                self.log(f"Failed to trigger build. Status: {response.status_code}")
                self.log(f"Response: {response.text}")
                return None

        except Exception as e:
            self.log(f"Error triggering Jenkins build: {e}")
            return None

    def get_build_number_from_queue(self, queue_url, timeout=300):
        """Get build number from queue URL"""
        if not queue_url:
            return None

        try:
            queue_api_url = f"{queue_url}api/json"
            start_time = time.time()

            while time.time() - start_time < timeout:
                response = requests.get(queue_api_url, auth=self.jenkins_auth)
                if 200 <= response.status_code < 300:
                    data = response.json()
                    if "executable" in data and data["executable"]:
                        build_number = data["executable"]["number"]
                        self.log(f"Build started: #{build_number}")
                        return build_number

                time.sleep(10)  # Check queue every 10 seconds

            self.log("Timeout waiting for build to start")
            return None

        except Exception as e:
            self.log(f"Error getting build number: {e}")
            return None

    def wait_for_build_completion(self, build_number, max_wait_hours=3):
        """Wait for Jenkins build to complete with progressive polling"""
        if not build_number:
            return False

        try:
            build_api_url = f"{self.jenkins_url}{build_number}/api/json"
            start_time = time.time()
            max_wait_seconds = max_wait_hours * 3600

            # Progressive polling intervals (in seconds)
            # Since builds take minimum 30 minutes, no need for aggressive early polling
            polling_intervals = [
                (
                    30 * 60,
                    900,
                ),  # First 30 min: every 15 minutes (builds rarely finish before this)
                (
                    max_wait_seconds,
                    900,
                ),  # After 30 min: every 15 minutes (more likely to finish)
            ]

            last_poll_time = start_time

            while time.time() - start_time < max_wait_seconds:
                response = requests.get(build_api_url, auth=self.jenkins_auth)

                if 200 <= response.status_code < 300:
                    data = response.json()

                    if not data.get("building", True):  # Build finished
                        result = data.get("result", "UNKNOWN")
                        if result == "SUCCESS":
                            self.log("Jenkins build completed successfully")
                            return True
                        else:
                            self.log(f"Jenkins build failed with result: {result}")
                            # Print build console output for debugging
                            self.log("Fetching build console output...")
                            console_url = (
                                f"{self.jenkins_url}{build_number}/consoleText"
                            )
                            console_response = requests.get(
                                console_url, auth=self.jenkins_auth
                            )
                            if 200 <= console_response.status_code < 300:
                                lines = console_response.text.split("\n")
                                # Show last 20 lines of console output
                                self.log("Last 20 lines of build output:")
                                for line in lines[-20:]:
                                    if line.strip():
                                        self.log(f"  {line}")
                            return False
                    else:
                        # Determine current polling interval
                        elapsed = time.time() - start_time
                        for i, (time_threshold, interval) in enumerate(
                            polling_intervals
                        ):
                            if elapsed < time_threshold:
                                current_interval = interval
                                current_interval_idx = i
                                break

                        # Only log status every few polls to avoid spam
                        if time.time() - last_poll_time >= current_interval:
                            duration = int(elapsed)
                            self.log(
                                f"Build #{build_number} still running... ({duration//60}m {duration%60}s elapsed)"
                            )
                            last_poll_time = time.time()

                        time.sleep(current_interval)
                else:
                    self.log(f"Error checking build status: {response.status_code}")
                    return False

            self.log("Build timeout exceeded")
            return False

        except Exception as e:
            self.log(f"Error waiting for build completion: {e}")
            return False

    def setup_selenium_driver(self):
        """Setup Chrome driver with appropriate options"""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-web-security")
            options.add_argument("--allow-running-insecure-content")
            options.add_argument("--disable-features=VizDisplayCompositor")

            driver = webdriver.Chrome(options=options)
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            return driver
        except Exception as e:
            self.log(f"Error setting up Chrome driver: {e}")
            return None

    def safe_click(self, driver, xpath, description, timeout=15):
        try:
            # Wait for busy indicator to disappear (if present)
            try:
                WebDriverWait(driver, timeout).until_not(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".busy-indicator.active")
                    )
                )
                print("[INFO] Busy indicator cleared")
            except TimeoutException:
                print("[WARNING] Busy indicator still present, proceeding anyway")

            # Wait for the element to be clickable
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )

            # Try normal click
            element.click()
            print(f"[SUCCESS] Clicked {description}")
            return True
        except (ElementClickInterceptedException, ElementNotInteractableException):
            print(f"[WARNING] Normal click failed on {description}, trying JS click...")
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                driver.execute_script("arguments[0].click();", element)
                print(f"[SUCCESS] JS clicked {description}")
                return True
            except Exception as js_e:
                print(f"[FAILED] JS click also failed on {description}: {js_e}")
                return False

        except TimeoutException:
            print(f"[FAILED] Timeout waiting for {description}")
            return False

    def execute_tem_automation(self):
        """Automate TEM execution using Selenium"""
        driver = None
        try:
            self.log("Starting TEM automation...")
            driver = self.setup_selenium_driver()
            if not driver:
                return False

            wait = WebDriverWait(driver, 20)

            # Navigate to TEM
            self.log("Navigating to TEM...")
            driver.get(self.tem_url)

            # Login
            self.log("Logging in...")
            self.safe_click(driver, "//*[@id='loginTaas']", "Login button")

            # Wait for login to complete
            self.log("Waiting for login to complete...")
            wait = WebDriverWait(driver, 30)
            wait.until(EC.element_to_be_clickable((By.ID, "navManageExecution")))

            # Navigate to Executions tab
            self.log("Navigating to Executions tab...")
            self.safe_click(driver, "//*[@id='navManageExecution']", "Executions tab")

            # Create Execution Job
            self.log("Creating execution job...")
            self.safe_click(
                driver, "//*[@id='executeTestPlan']", "Create Execution Job"
            )

            # Script Branch dropdown
            self.log("Selecting script branch...")
            self.safe_click(
                driver,
                "//label[normalize-space()='Script Branch']/following::div[contains(@class,'dropdown') and @role='combobox'][1]",
                "Script Branch dropdown",
            )
            self.safe_click(
                driver,
                "//li[normalize-space()='release_1.0.0']",
                "Script Branch option",
            )

            # Script Version dropdown
            self.log("Selecting script version...")
            self.safe_click(
                driver,
                "//label[normalize-space()='Script Version']/following::div[contains(@class,'dropdown') and @role='combobox'][1]",
                "Script Version dropdown",
            )
            self.safe_click(
                driver,
                "//li[normalize-space()='11.0-SNAPSHOT']",
                "Script Version option",
            )

            # Test execution plan search
            self.log("Searching for test plan...")
            test_plan_name = self.config["tem"]["test_plan_name"]
            self.safe_click(
                driver,
                "//label[normalize-space()='Test Execution Plan']/following::span[@class='trigger'][1]",
                "Test Plan search icon",
            )

            # Search in popup
            search_input = wait.until(
                EC.presence_of_element_located(
                    (By.ID, "taas-lookup-datagrid-1-header-filter-1")
                )
            )
            search_input.clear()
            search_input.send_keys(test_plan_name)

            # Select the test plan from results
            self.safe_click(
                driver,
                f"//td//div[normalize-space()='{test_plan_name}']",
                "Test Plan search result",
            )

            # Handle Base URL popup
            self.log("Handling Base URL popup...")
            self.safe_click(driver, "//*[@id='modal-button-1']", "Base URL OK button")

            # Fill Environment Owner Email
            self.log("Filling environment details...")
            email_input = wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//label[normalize-space()='Environment Owner Email']/following::input[@formcontrolname='ownerEmailCtrl'][1]",
                    )
                )
            )
            email_input.clear()
            email_input.send_keys(self.config["tem"]["environment_email"])

            # Usage type dropdown
            self.log("Selecting usage type...")
            self.safe_click(
                driver,
                "//label[normalize-space()='Usage Type']/following::div[contains(@class,'dropdown') and @role='combobox'][1]",
                "Usage Type dropdown",
            )
            self.safe_click(driver, "//li[normalize-space()='QA']", "Usage Type option")

            # Submit
            self.log("Submitting execution job...")
            self.safe_click(
                driver,
                "//button[span[normalize-space()='Submit']]",
                "Submit button",
            )

            self.log("TEM execution job submitted successfully!")
            self.log("You will receive an email when execution completes")

            return True
        except Exception as e:
            self.log(f"Error in TEM automation: {e}")
            return False
        finally:
            if driver:
                # Brief pause to see result
                time.sleep(3)
                driver.quit()

    def update_processed_commit(self, commit_hash):
        """Update the last processed commit"""
        try:
            with open(".last_processed_commit", "w") as f:
                f.write(commit_hash)
        except Exception as e:
            self.log(f"Warning: Could not update processed commit: {e}")

    def run_automation(self):
        """Run the complete automation process"""
        self.log("Starting automation process...")

        # Check for new commits
        new_commit = self.check_for_new_commits()
        if not new_commit:
            self.log("No new commits found. Exiting.")
            return

        try:
            # Step 1: Trigger Jenkins build
            queue_url = self.trigger_jenkins_build()
            if not queue_url:
                self.log("Failed to trigger Jenkins build. Stopping.")
                return

            # Step 2: Get build number
            build_number = self.get_build_number_from_queue(queue_url)
            if not build_number:
                self.log("Failed to get build number. Stopping.")
                return

            # Step 3: Wait for build completion
            build_success = self.wait_for_build_completion(build_number)
            if not build_success:
                self.log("Jenkins build failed. Stopping automation.")
                self.log(
                    "Please check Jenkins console output and fix issues before retrying."
                )
                return

            # Step 4: Execute TEM automation
            tem_success = self.execute_tem_automation()
            if not tem_success:
                self.log("TEM automation failed.")
                return

            # Step 5: Mark commit as processed
            self.update_processed_commit(new_commit)

            self.log("Automation completed successfully!")
            self.log(
                "The process will continue in TEM. Check your email for completion notification."
            )

        except KeyboardInterrupt:
            self.log("Automation interrupted by user")
        except Exception as e:
            self.log(f"Unexpected error: {e}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Jenkins-TEM Automation Script")
    parser.add_argument(
        "--build",
        "-b",
        action="store_true",
        help="Enable Jenkins build and TEM execution (REQUIRED for automation)",
    )
    parser.add_argument(
        "--check",
        "-c",
        action="store_true",
        help="Only check for new commits, no automation",
    )
    parser.add_argument(
        "--help-setup", action="store_true", help="Show setup instructions"
    )
    parser.add_argument(
        "--test-jenkins",
        action="store_true",
        help="Test Jenkins API trigger only (no waiting, no TEM)",
    )
    parser.add_argument(
        "--test-tem",
        action="store_true",
        help="Test TEM Selenium automation only (no Jenkins)",
    )

    args = parser.parse_args()

    if args.help_setup:
        print(
            """
    SETUP INSTRUCTIONS:

    1. Install dependencies:
    pip install requests selenium

    2. Download ChromeDriver:
    - Go to https://chromedriver.chromium.org/
    - Download version matching your Chrome browser
    - Add to PATH or place in script directory

    3. Create config.json with your Jenkins/TEM details

    4. Generate Jenkins API token:
    - Jenkins → Your Profile → Security → API Token
    - Click "Add new token" and copy to config.json

    USAGE:
    python automation_script.py --check     # Just check for new commits
    python automation_script.py --build     # Full automation (Jenkins + TEM)

    SAFETY: The --build flag is REQUIRED for automation to prevent accidental builds.
        """
        )
        return

    if args.check:
        # Only check for commits, don't run automation
        try:
            automator = BuildAutomator()
            new_commit = automator.check_for_new_commits()
            if new_commit:
                automator.log(f"New commit found: {new_commit[:8]}")
                automator.log("Run with --build flag to trigger automation")
            else:
                automator.log("No new commits found")
        except Exception as e:
            print(f"Error checking commits: {e}")
        return

    if args.test_jenkins:
        try:
            automator = BuildAutomator()
            success = automator.test_jenkins_trigger()
            if success:
                print("Jenkins API test completed successfully!")
            else:
                print("Jenkins API test failed!")
        except Exception as e:
            print(f"Error testing Jenkins: {e}")
        return

    if args.test_tem:
        try:
            automator = BuildAutomator()
            success = automator.test_tem_selenium()
            if success:
                print("TEM Selenium test completed successfully!")
            else:
                print("TEM Selenium test failed!")
        except Exception as e:
            print(f"Error testing TEM: {e}")
        return

    if not args.build:
        print("SAFETY CHECK: --build flag required for automation")
        print("")
        print("This prevents accidental Jenkins builds when others use the script.")
        print("")
        print("OPTIONS:")
        print("  python automation_script.py --check         # Check for new commits")
        print("  python automation_script.py --build         # Run full automation")
        print("  python automation_script.py --test-jenkins  # Test Jenkins API")
        print("  python automation_script.py --test-tem      # Test TEM Selenium")
        print("  python automation_script.py --help-setup    # Setup instructions")
        return

    try:
        automator = BuildAutomator()
        automator.run_automation()
    except FileNotFoundError:
        print("config.json not found. Please create configuration file.")
        print("Run: python automation_script.py --help-setup")
    except Exception as e:
        print(f"Error initializing automator: {e}")


if __name__ == "__main__":
    main()
