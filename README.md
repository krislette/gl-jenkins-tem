# GitLab-Jenkins-TEM CI/CD Pipeline

This mini project started as an idea, after *repeatedly* configuring and executing on different platforms. Now, it automates the complete CI/CD workflow from code push to test execution. That means, it removes manual steps mainly between Jenkins builds and TEM execution.

## What This Does

This automation pipeline makes your development workflow *efficient*:

1. **Detects New Commits** - Monitors the CSF integration testscripts repository for new changes
2. **Triggers Jenkins Builds** - Starts builds via Jenkins API when new commits are found
3. **Waits for Build Completion** - Monitors build progress with smart polls (30min-2hr build time)
4. **Executes TEM Test Plans** - Submits test execution jobs in TEM after successful builds
5. **Email Notifications** - TEM sends completion notifications when test execution finishes

**Time Savings**: Removes 10-15 minutes of manual work and constant queue checks between each step.

## Process Timeline

| Step | Manual Time | Automated | Wait Time |
|------|-------------|-----------|-----------|
| Push code | 1 min | 1 min | - |
| Navigate to Jenkins | 2 min | Automated | - |
| Trigger build | 1 min | Automated | - |
| Wait in queue | - | Automated | 30min - 1hr |
| Monitor build | 5 min | Automated | 30min - 2hr |
| Navigate to TEM | 2 min | Automated | - |
| Fill TEM form | 3 min | Automated | - |
| Wait for execution | - | Automated | 30min - 1hr |
| **Total Manual Work** | **14 minutes** | **1 minute** | **1-5 hours** |

## Prerequisites

### Software Requirements
- **Python 3.7+** installed and accessible from command line
- **Google Chrome** browser (for Selenium automation)
- **Git** configured with access to your company repositories
- **Git Bash** for running setup commands
- **Code Editor** preferably Visual Studio Code for editing the config file
- **Network Access (VPN)** to Jenkins and TEM platforms

### Access Requirements
- Jenkins API token (see setup instructions below)
- TEM account with execution permissions
- Access to Xtend repository

## Installation and Setup

### Step 1: Clone the Pipeline Repository

```bash
# Open bash and navigate to your code directory
cd C:\Code

# Clone the repo into a folder named ci-cd-pipeline
git clone https://github.com/krislette/gl-jenkins-tem.git ci-cd-pipeline
cd ci-cd-pipeline

# Remove any pre-existing push_detector.py (it will be generated later)
rm push_detector.py
```

### Step 2: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Generate Jenkins API Token

For this step, leave the bash terminal (and open your preferred browser) but don't close it yet, you will be coming back to the terminal later.

1. Log into Jenkins web interface
2. Click your profile name (top right) then **Security** and see the **API Token** section
3. Click **"Add new token"**
4. Give it a name (example: "Automation Script")
5. Copy the token to your `config.json` (see step 4), this only appears once

### Step 4: Create Configuration File

After creating token, open bash terminal again, then copy the example config by typing:

```bash
copy config.example.json config.json
```

(Skip this if you don't have VS Code installed) Open the repository project code by typing the command below:

```
code .
```

A `config.json` file will be generated. Update it with your details (either via VS Code or any code editor of your choice):

```json
{
    "jenkins": {
        "base_url": "https://jenkins-server.com/job/job-name/",
        "username": "your-jenkins-username",
        "api_token": "your-jenkins-api-token-here (see step 4)",
        "soho_version": "your-soho-version"
    },
    "tem": {
        "base_url": "https://the-tem-server.com/",
        "test_plan_name": "Your Test Plan Name",
        "environment_email": "your-email@company.com"
    }
}
```

### Step 5: Set Up Git Hooks

Navigate to the Xtend repository (not the automation pipeline repository):

```bash
cd path\to\your\csf-integration-testscripts
```

Then run the setup script by entering this command on the terminal:

```bash
python C:\Code\ci-cd-pipeline\setup_hooks.py
```

This creates two new git commands:
- `git push-only` - Normal push without automation
- `git push-build` - Push and trigger automation

## Usage Guide

### Automated Workflow (Recommended)

From your CSF integration testscripts repository:

1. **Make your code changes**
2. **Commit your changes**: 
   ```bash
   git add .
   git commit -m "Your commit message"
   ```
3. **Push with automation**: 
   ```bash
   git push-build
   ```

**WARNING:** Do not close the terminal after running git push-build.
The automation runs inside this session until completion. Closing it will stop the process.

The script will automatically:
- Push your code to the repository
- Detect the new commit
- Trigger Jenkins build
- Wait for build completion (30min-2hr)
- Execute TEM test plan
- You will receive email when tests complete

### Manual Commands (Not Recommended)

**Don't try all** of the commands **except the `--help-setup` argument** below unless you plan to debug/change the code/contribute to the ci-cd-pipeline.

#### Check for New Commits Only
```bash
python C:\Code\ci-cd-pipeline\script.py --check
```

#### Run Full Automation
```bash
python C:\Code\ci-cd-pipeline\script.py --build
```

#### Test Individual Components
```bash
# Test Jenkins API connection only
python C:\Code\ci-cd-pipeline\script.py --test-jenkins

# Test TEM automation only (no Jenkins build)
python C:\Code\ci-cd-pipeline\script.py --test-tem
```

#### View Setup Help
```bash
python C:\Code\ci-cd-pipeline\script.py --help-setup
```

### Safety Features

- **Repository Verification**: Only works in CSF integration testscripts repository
- **Build Flag Required**: `--build` flag required for automation (prevents accidental builds)
- **Commit Tracker**: Prevents duplicate builds for the same commit
- **Smart Polls**: Uses intervals that do not overwhelm Jenkins

## Technical Details

### Build Times and Queue Management
- **Minimum Build Time**: 30 minutes
- **Maximum Build Time**: 3 hours
- **Queue Wait Time**: 30 minutes - 3 hours (depends on usage)
- **TEM Execution Time**: 30 minutes - 2 hours (depends on the script/s on test plan)

### Smart Poll Strategy
- **First 30 minutes**: Check every 15 minutes (builds rarely finish before this)
- **After 30 minutes**: Check every 15 minutes until completion
- **Progressive intervals**: Reduces server load while maintains responsiveness

### Selenium Automation Features
- **Headless Chrome**: Runs browser automation in background
- **Smart Wait**: Waits for elements to be clickable before interaction
- **Error Recovery**: Uses JavaScript clicks when normal clicks fail
- **Busy Indicator Handler**: Waits for TEM busy indicators to clear

## File Structure for the Automation Pipeline

```
C:\Code\ci-cd-pipeline\
├── script.py                   # Main automation script
├── setup_hooks.py              # Git hooks setup utility  
├── config.json                 # Your configuration file
├── push_detector.py            # Auto-generated by setup_hooks.py
├── .last_processed_commit      # Auto-generated commit tracker
└── README.md                   # This documentation
```

## Troubleshoot

### Common Issues and Solutions

**"config.json not found"**
- Make sure `config.json` is in `C:\Code\ci-cd-pipeline\` directory
- Check file permissions and JSON syntax

**"ChromeDriver not found"**
- Install webdriver-manager: `pip install webdriver-manager`
- Or manually add ChromeDriver to PATH
- Verify Chrome browser is installed

**"Repository verification failed"**
- This script only works in CSF integration testscripts repository
- Make sure you run from the correct repository directory
- Check that `git remote get-url origin` contains "csf-integration-testscripts"

**"Jenkins build failed"**
- Check Jenkins console output (automatically shown by script)
- Verify Jenkins API token is correct and not expired
- Make sure Jenkins job URL is correct in `config.json`
- Check if Jenkins server is accessible

**"TEM automation failed"**
- Verify TEM server is accessible in browser
- Check test plan name in `config.json` matches exactly (case-sensitive)
- Make sure environment email is correct
- Try run `--test-tem` to isolate TEM issues

**"Permission denied" errors**
- Run command prompt as administrator
- Check file/directory permissions
- Make sure you have git write permissions in the repository

### Debug Commands

**Test each component separately:**
```bash
# Test Jenkins API only (quick test)
python C:\Code\ci-cd-pipeline\script.py --test-jenkins

# Test TEM automation only (opens browser)
python C:\Code\ci-cd-pipeline\script.py --test-tem

# Check for new commits without run automation
python C:\Code\ci-cd-pipeline\script.py --check
```

**Verbose logs:**
```bash
python -v C:\Code\ci-cd-pipeline\script.py --build
```

### Configuration Validation

Verify your `config.json` settings:

1. **Jenkins URL**: Should end with job name and trailing slash
   - Good: `https://jenkins.company.com/job/my-job/`
   - Bad: `https://jenkins.company.com/job/my-job`

2. **API Token**: Generate new token if authentication fails
3. **Test Plan Name**: Must match exactly as shown in TEM
4. **Email**: Use a valid email (e.g. ends with @email.com/@gmail.com/@infor.com)

## Important Safety Notes

1. **Repository-Specific**: Only works with CSF integration testscripts repository
2. **Build Triggers**: Use `git push-build` to trigger the automation. You're still free to use `plain git push` for manual workflows without automation.
3. **Terminal Requirement**: Keep the terminal open after running git push-build; closing it will interrupt the automation
4. **Queue Awareness**: Builds go into queue - check Jenkins if builds seem delayed
5. **Network Dependencies**: Requires stable VPN connection to Jenkins and TEM
6. **Browser Requirements**: Headless Chrome must work in your environment

## Remove the Automation

To completely remove git hooks and aliases:

From your CSF repository:
```bash
python C:\Code\ci-cd-pipeline\setup_hooks.py --remove
```

This removes:
- Git aliases (`push-only`, `push-build`)
- Push detector script
- Commit tracker files

## Success Indicators

When everything works correctly, you should see a series of logs confirming:

- New commit detected
- Jenkins build triggered and completed
- TEM automation started and finished
- Email notification from TEM received after execution

> A full sample run is available at [/docs](https://github.com/krislette/gl-jenkins-tem/docs/) directory

## Get Help

If you encounter issues:

1. **Check this troubleshoot section** for common solutions
2. **Run individual tests** to isolate the problem
3. **Verify configuration** matches the examples above
4. **Test manual access** to Jenkins and TEM platforms
5. **Check network connectivity** and firewall settings

The automation saves significant time and reduces human error in your CI/CD pipeline. Once set up properly, it handles the entire flow from code push to test execution automatically.
