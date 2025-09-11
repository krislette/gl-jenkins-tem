"""
Jenkins-TEM Automation Script
Automates the build process from Jenkins trigger to TEM execution
"""

# Regular imports
import os
import requests
import time
import json
import subprocess
import threading
from datetime import datetime
from misc.trivias import get_trivia

# Rich imports
from rich.console import Console
from rich.spinner import Spinner
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

# Selenium imports
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
        # Initialize Rich console
        self.console = Console()

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
            # Check the current working directory, not the script location
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),  # Explicitly use current working directory
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

    def log(self, message, level="INFO"):
        """Enhanced log with timestamp and colors using Rich"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Create colored timestamp
        timestamp_text = Text(f"[{timestamp}]", style="bold white")

        if level == "SUCCESS":
            message_text = Text(message, style="bold green")
        elif level == "ERROR":
            message_text = Text(message, style="bold red")
        elif level == "WARNING":
            message_text = Text(message, style="bold yellow")
        else:
            # Regular info messages - make keywords bold
            message_text = Text()
            words = message.split()

            # Keywords to emphasize
            keywords = [
                "Jenkins",
                "TEM",
                "New",
                "don't",
                "close",
                "connected",
                "SUCCESS",
                "FAILED",
                "DYK?",
                "completed",
                "triggered",
            ]

            for i, word in enumerate(words):
                if any(keyword.lower() in word.lower() for keyword in keywords):
                    message_text.append(word, style="bold")
                else:
                    message_text.append(word)

                if i < len(words) - 1:
                    message_text.append(" ")

        # Combine timestamp and message
        full_message = Text()
        full_message.append(timestamp_text)
        full_message.append(" ")
        full_message.append(message_text)

        self.console.print(full_message)

    def log_reminder(self):
        """Log few reminders from time to time"""
        self.log("Please don't close this terminal while waiting.")
        self.log("Stay connected to the VPN to avoid failures.")

    def log_with_spinner(
        self, message, duration, check_function=None, check_interval=10
    ):
        """Display message with spinner for long operations"""
        spinner_active = True
        spinner_result = None

        def spinner_thread():
            nonlocal spinner_result
            with Live(console=self.console, refresh_per_second=10) as live:
                spinner = Spinner("simpleDots", text=message)
                while spinner_active:
                    live.update(spinner)
                    time.sleep(0.1)
                # Clear the spinner by updating with empty content
                live.update("")

        # Start spinner in background
        spinner_t = threading.Thread(target=spinner_thread, daemon=True)
        spinner_t.start()

        start_time = time.time()

        try:
            while time.time() - start_time < duration:
                if check_function:
                    result = check_function()
                    if result:
                        spinner_result = result
                        break
                time.sleep(check_interval)
        finally:
            spinner_active = False
            # Wait for spinner to clean up
            spinner_t.join(timeout=0.5)
            # Force a newline for a clean separation from spinner
            print()

        return spinner_result

    def test_jenkins_trigger(self):
        """Test Jenkins API trigger"""
        self.log("Testing Jenkins API trigger")
        queue_url = self.trigger_jenkins_build()
        if queue_url:
            self.log(f"Jenkins build triggered! Queue URL: {queue_url}", "SUCCESS")
            self.log("Check Jenkins manually to see if build started")
            return True
        else:
            self.log("Could not trigger Jenkins build", "ERROR")
            return False

    def test_tem_selenium(self):
        """Test TEM Selenium automation without Jenkins build"""
        self.log("Testing TEM Selenium automation")
        self.log("This will open browser and attempt TEM form filling")
        return self.execute_tem_automation()

    def check_for_new_commits(self):
        """Check if there are new commits to process"""
        try:
            # Get the latest commit hash from current working directory (CSF repo)
            result = subprocess.run(
                ["git", "rev-parse", "origin/master"],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
            )
            latest_commit = result.stdout.strip()

            # Check if we've processed this commit already
            # Read from the automation directory, not the CSF repo
            script_dir = os.path.dirname(os.path.abspath(__file__))
            commit_file = os.path.join(script_dir, ".last_processed_commit")

            try:
                with open(commit_file, "r") as f:
                    last_processed = f.read().strip()
            except FileNotFoundError:
                last_processed = ""

            if latest_commit != last_processed:
                self.log(
                    f"New commit detected: {latest_commit[:8]}csf-integration-testscripts"
                )
                return latest_commit
            return None
        except Exception as e:
            self.log(f"Error checking commits: {e}", "ERROR")
            return None

    def trigger_jenkins_build(self):
        """Trigger Jenkins build via API"""
        try:
            self.log("Triggering Jenkins build")
            build_url = f"{self.jenkins_url}buildWithParameters"
            params = {"CSF_SOHO_VERSION": self.config["jenkins"]["soho_version"]}

            response = requests.post(build_url, auth=self.jenkins_auth, params=params)

            if 200 <= response.status_code < 300:
                self.log("Jenkins build triggered successfully", "SUCCESS")

                # Jenkins *may or may not* return a queue URL
                queue_url = response.headers.get("Location")
                if queue_url:
                    return queue_url

                # Fallback: Look for user's job on queue
                self.log(
                    "Warning: Jenkins did not return a queue URL. "
                    "Checking the queue API for your build...",
                    "WARNING",
                )
                try:
                    queue_api_url = f"{self.jenkins_url}queue/api/json"
                    queue_resp = requests.get(queue_api_url, auth=self.jenkins_auth)
                    if queue_resp.ok:
                        queue_data = queue_resp.json()
                        for item in queue_data.get("items", []):
                            task_url = item.get("task", {}).get("url", "")
                            if self.config["jenkins"]["job_name"] in task_url:
                                queue_url = item.get("url")
                                self.log(f"Found queued item: {queue_url}", "SUCCESS")
                                return queue_url
                except Exception as e:
                    self.log(f"Queue lookup failed: {e}", "ERROR")

                # Fallback #2: Last known build
                try:
                    job_api_url = f"{self.jenkins_url}api/json"
                    job_resp = requests.get(job_api_url, auth=self.jenkins_auth)
                    if job_resp.ok:
                        data = job_resp.json()
                        last_build = data.get("lastBuild", {}).get("number")
                        if last_build:
                            self.log(
                                f"Fallback: using last known build #{last_build} "
                                "(may not be your run).",
                                "WARNING",
                            )
                            return f"{self.jenkins_url}{last_build}/"
                except Exception as e:
                    self.log(f"Fallback failed to fetch last build: {e}", "ERROR")

            else:
                self.log(
                    f"Failed to trigger build. Status: {response.status_code}", "ERROR"
                )
                self.log(f"Response: {response.text}", "ERROR")
                return None
        except Exception as e:
            self.log(f"Error triggering Jenkins build: {e}", "ERROR")
            return None

    def get_build_number_from_queue(self, queue_url, timeout=7200):
        """Get build number from queue URL"""
        if not queue_url:
            return None

        try:
            queue_api_url = f"{queue_url}api/json"
            start_time = time.time()
            last_reported_minute = -1

            self.log(
                "Build is in queue usually takes 30-60 minutes if another build is already running."
            )
            self.log_reminder()

            # Use spinner for queue waiting
            def check_queue():
                nonlocal last_reported_minute
                response = requests.get(queue_api_url, auth=self.jenkins_auth)
                if 200 <= response.status_code < 300:
                    data = response.json()
                    # If still queued
                    if "executable" not in data or not data["executable"]:
                        in_queue_since = data.get("inQueueSince")
                        if in_queue_since:
                            queued_for = int(
                                (time.time() * 1000 - in_queue_since) / 1000
                            )
                            mins = queued_for // 60
                            # Update every 15 mins
                            if (
                                mins > 0
                                and mins % 15 == 0
                                and mins != last_reported_minute
                            ):
                                why = data.get("why", "")
                                self.log(
                                    f"Still in queue (~{mins} min) {why if why else 'Waiting for available executor'}"
                                )
                                self.log_reminder()
                                self.log(f"DYK? {get_trivia()}")
                                last_reported_minute = mins
                        return False
                    else:
                        # Build started
                        build_number = data["executable"]["number"]
                        queued_for = int(
                            (time.time() * 1000 - data["inQueueSince"]) / 1000
                        )
                        self.log(
                            f"Build started: #{build_number} (waited {queued_for//60}m {queued_for%60}s in queue)",
                            "SUCCESS",
                        )
                        self.log(
                            "Please wait ~30 minutes to 2 hours for Jenkins build completion."
                        )
                        self.log_reminder()
                        return build_number
                return False

            # Show spinner while waiting
            result = self.log_with_spinner(
                "Waiting in build queue", timeout, check_queue, 10
            )

            # Check if we got a result from the spinner
            if result:
                return result

            # Final check
            response = requests.get(queue_api_url, auth=self.jenkins_auth)
            if 200 <= response.status_code < 300:
                data = response.json()
                if "executable" in data and data["executable"]:
                    return data["executable"]["number"]

            self.log("Timeout waiting for build to start", "ERROR")
            return None

        except Exception as e:
            self.log(f"Error getting build number: {e}", "ERROR")
            return None

    def wait_for_build_completion(self, build_number, max_wait_hours=3):
        """Wait for Jenkins build to complete with progressive polling"""
        if not build_number:
            return False

        try:
            build_api_url = f"{self.jenkins_url}{build_number}/api/json"
            start_time = time.time()
            max_wait_seconds = max_wait_hours * 3600

            last_poll_time = start_time

            def check_build():
                nonlocal last_poll_time
                response = requests.get(build_api_url, auth=self.jenkins_auth)
                if 200 <= response.status_code < 300:
                    data = response.json()
                    if not data.get("building", True):  # Build finished
                        result = data.get("result", "UNKNOWN")
                        if result == "SUCCESS":
                            self.log("Jenkins build completed successfully", "SUCCESS")
                            return True
                        else:
                            self.log(
                                f"Jenkins build failed with result: {result}", "ERROR"
                            )
                            # Print build console output for debugging
                            self.log("Fetching build console output")
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
                            return "FAILED"
                    else:
                        # Log status every 15 minutes
                        elapsed = time.time() - start_time
                        if time.time() - last_poll_time >= 900:  # 15 minutes
                            duration = int(elapsed)
                            self.log(
                                f"Build #{build_number} still running, ({duration//60}m {duration%60}s elapsed)"
                            )
                            self.log_reminder()
                            self.log(f"DYK? {get_trivia()}")
                            last_poll_time = time.time()
                        return False
                else:
                    self.log(
                        f"Error checking build status: {response.status_code}", "ERROR"
                    )
                    return "ERROR"

            # Show spinner while build is running
            result = self.log_with_spinner(
                f"Build #{build_number} is running",
                max_wait_seconds,
                check_build,
                900,
            )

            # Check the result
            if result is True:
                return True
            elif result == "FAILED" or result == "ERROR":
                return False

            # Final check
            final_result = check_build()
            return final_result is True

        except Exception as e:
            self.log(f"Error waiting for build completion: {e}", "ERROR")
            return False

    def setup_selenium_driver(self):
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            driver = webdriver.Chrome(options=options)
            return driver
        except Exception as e:
            self.log(f"Error setting up Chrome driver: {str(e)}", "ERROR")
            import traceback

            self.log(f"Driver setup traceback: {traceback.format_exc()}", "ERROR")
            return None

    def safe_click(self, driver, xpath, description, timeout=30):
        try:
            # Wait for busy indicator to disappear (if present)
            try:
                WebDriverWait(driver, timeout).until_not(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".busy-indicator.active")
                    )
                )
                self.log("Busy indicator cleared")
            except TimeoutException:
                self.log("Busy indicator still present, proceeding anyway", "WARNING")

            # Wait for the element to be clickable
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )

            # Try normal click
            element.click()
            self.log(f"Clicked {description}", "SUCCESS")
            return True

        except (ElementClickInterceptedException, ElementNotInteractableException):
            self.log(
                f"Normal click failed on {description}, trying JS click", "WARNING"
            )
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                driver.execute_script("arguments[0].click();", element)
                self.log(f"JS clicked {description}", "SUCCESS")
                return True
            except Exception as js_e:
                self.log(f"JS click also failed on {description}: {js_e}", "ERROR")
                return False
        except TimeoutException:
            self.log(f"Timeout waiting for {description}", "ERROR")
            return False

    def execute_tem_automation(self):
        """Automate TEM execution using Selenium"""
        driver = None
        try:
            self.log("Starting TEM automation")
            driver = self.setup_selenium_driver()
            if not driver:
                return False

            wait = WebDriverWait(driver, 20)

            # Navigate to TEM
            self.log("Navigating to TEM")
            driver.get(self.tem_url)

            # Login
            self.log("Logging in")
            self.safe_click(driver, "//*[@id='loginTaas']", "Login button")

            # Wait for login to complete
            self.log("Waiting for login to complete")
            wait = WebDriverWait(driver, 30)
            wait.until(EC.element_to_be_clickable((By.ID, "navManageExecution")))

            # Navigate to Executions tab
            self.log("Navigating to Executions tab")
            self.safe_click(driver, "//*[@id='navManageExecution']", "Executions tab")

            # Create Execution Job
            self.log("Creating execution job")
            self.safe_click(
                driver, "//*[@id='executeTestPlan']", "Create Execution Job"
            )

            # Script Branch dropdown
            self.log("Selecting script branch")
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
            self.log("Selecting script version")
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
            self.log("Searching for test plan")
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
            self.log("Handling Base URL popup")
            self.safe_click(driver, "//*[@id='modal-button-1']", "Base URL OK button")

            # Fill Environment Owner Email
            self.log("Filling environment details")
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
            self.log("Selecting usage type")
            self.safe_click(
                driver,
                "//label[normalize-space()='Usage Type']/following::div[contains(@class,'dropdown') and @role='combobox'][1]",
                "Usage Type dropdown",
            )
            self.safe_click(driver, "//li[normalize-space()='QA']", "Usage Type option")

            # Submit
            self.log("Submitting execution job")
            self.safe_click(
                driver,
                "//button[span[normalize-space()='Submit']]",
                "Submit button",
            )

            # Wait for and verify the success status
            self.log("Waiting for submission confirmation")
            try:
                # Wait for the success status message to appear
                success_status = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located(
                        (
                            By.XPATH,
                            "//span[contains(text(), 'The job has been successfully queued')]",
                        )
                    )
                )
                self.log("Job successfully queued confirmation received", "SUCCESS")

                # Click the OK button on the modal
                self.safe_click(driver, "//*[@id='modal-button-3']", "OK button")

            except TimeoutException:
                self.log("Could not find success confirmation message", "WARNING")
                # Try to click OK button anyway
                self.safe_click(driver, "//*[@id='modal-button-3']", "OK button")

            self.log("TEM execution job submitted successfully!", "SUCCESS")
            self.log("You will receive an email when execution completes")
            return True

        except Exception as e:
            self.log(f"Error in TEM automation: {e}", "ERROR")
            return False
        finally:
            if driver:
                # Brief pause to see result
                time.sleep(3)
                driver.quit()

    def update_processed_commit(self, commit_hash):
        """Update the last processed commit"""
        try:
            # Save in the same directory as the script, not in the CSF repo
            script_dir = os.path.dirname(os.path.abspath(__file__))
            commit_file = os.path.join(script_dir, ".last_processed_commit")
            with open(commit_file, "w") as f:
                f.write(commit_hash)
        except Exception as e:
            self.log(f"Warning: Could not update processed commit: {e}", "WARNING")

    def run_automation(self):
        """Run the complete automation process"""
        self.log("Starting automation process")

        # Check for new commits
        new_commit = self.check_for_new_commits()
        if not new_commit:
            self.log("No new commits found. Exiting.")
            return

        try:
            # Step 1: Trigger Jenkins build
            queue_url = self.trigger_jenkins_build()
            if not queue_url:
                self.log("Failed to trigger Jenkins build. Stopping.", "ERROR")
                return

            # Step 2: Get build number
            build_number = self.get_build_number_from_queue(queue_url)
            if not build_number:
                self.log("Failed to get build number. Stopping.", "ERROR")
                return

            # Step 3: Wait for build completion
            build_success = self.wait_for_build_completion(build_number)
            if not build_success:
                self.log("Jenkins build failed. Stopping automation.", "ERROR")
                self.log(
                    "Please check Jenkins console output and fix issues before retrying."
                )
                return

            # Step 4: Execute TEM automation
            tem_success = self.execute_tem_automation()
            if not tem_success:
                self.log("TEM automation failed.", "ERROR")
                return

            # Step 5: Mark commit as processed
            self.update_processed_commit(new_commit)

            self.log("Automation completed successfully!", "SUCCESS")
            self.log(
                "The process will continue in TEM. Check your email for completion notification."
            )

        except KeyboardInterrupt:
            self.log("Automation interrupted by user", "WARNING")
        except Exception as e:
            self.log(f"Unexpected error: {e}", "ERROR")


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

    # Create console for main function
    console = Console()

    if args.help_setup:
        setup_panel = Panel(
            """
[bold green]SETUP INSTRUCTIONS:[/bold green]

[bold]1. Install dependencies:[/bold]
pip install requests selenium rich

[bold]2. Download ChromeDriver:[/bold]
- Go to https://chromedriver.chromium.org/
- Download version matching your Chrome browser
- Add to PATH or place in script directory

[bold]3. Create config.json with your Jenkins/TEM details[/bold]

[bold]4. Generate Jenkins API token:[/bold]
- Jenkins → Your Profile → Security → API Token
- Click "Add new token" and copy to config.json

[bold green]USAGE:[/bold green]
python script.py --check     # Just check for new commits
python script.py --build     # Full automation (Jenkins + TEM)

[bold red]SAFETY:[/bold red] The --build flag is REQUIRED for automation to prevent accidental builds.
            """,
            title="Setup Instructions",
            border_style="green",
        )
        console.print(setup_panel)
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
            console.print(f"[bold red]Error checking commits: {e}[/bold red]")
        return

    if args.test_jenkins:
        try:
            automator = BuildAutomator()
            success = automator.test_jenkins_trigger()
            if success:
                console.print(
                    "[bold green]Jenkins API test completed successfully![/bold green]"
                )
            else:
                console.print("[bold red]Jenkins API test failed![/bold red]")
        except Exception as e:
            console.print(f"[bold red]Error testing Jenkins: {e}[/bold red]")
        return

    if args.test_tem:
        try:
            automator = BuildAutomator()
            success = automator.test_tem_selenium()
            if success:
                console.print(
                    "[bold green]TEM Selenium test completed successfully![/bold green]"
                )
            else:
                console.print("[bold red]TEM Selenium test failed![/bold red]")
        except Exception as e:
            console.print(f"[bold red]Error testing TEM: {e}[/bold red]")
        return

    if not args.build:
        safety_panel = Panel(
            """
[bold red]SAFETY CHECK: --build flag required for automation[/bold red]

This prevents accidental Jenkins builds when others use the script.

[bold green]OPTIONS:[/bold green]
  python script.py --check         # Check for new commits
  python script.py --build         # Run full automation
  python script.py --test-jenkins  # Test Jenkins API
  python script.py --test-tem      # Test TEM Selenium
  python script.py --help-setup    # Setup instructions
            """,
            title="Safety Check",
            border_style="red",
        )
        console.print(safety_panel)
        return

    try:
        automator = BuildAutomator()
        automator.run_automation()
    except FileNotFoundError:
        console.print(
            "[bold red]config.json not found. Please create configuration file.[/bold red]"
        )
        console.print("Run: python script.py --help-setup")
    except Exception as e:
        console.print(f"[bold red]Error initializing automator: {e}[/bold red]")


if __name__ == "__main__":
    main()
