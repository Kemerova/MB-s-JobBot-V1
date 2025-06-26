#!/usr/bin/env python3
"""
JobBot Setup Script
Automated installation and configuration for the JobBot system
"""

import os
import sys
import subprocess
import webbrowser
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"   Current version: {sys.version}")
        print("   Please upgrade Python and try again")
        return False
    
    print(f"✅ Python {sys.version.split()[0]} - Compatible")
    return True


def install_dependencies():
    """Install required dependencies"""
    print("\n📦 Installing dependencies...")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        print("   Try running: pip install -r requirements.txt")
        return False


def check_api_keys():
    """Check if API keys are configured"""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("\n⚠️  No .env file found")
        return False
    
    with open(env_file, 'r') as f:
        content = f.read()
    
    has_openai = "OPENAI_API_KEY=" in content and "your-key-here" not in content
    
    if has_openai:
        print("✅ OpenAI API key configured")
        return True
    else:
        print("⚠️  OpenAI API key not configured")
        return False


def create_sample_env():
    """Create sample .env file"""
    env_content = """# JobBot Environment Variables
# Get your OpenAI API key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=your-openai-key-here

# Optional: USAJobs API key for government positions
# Get from: https://developer.usajobs.gov/
USAJOBS_API_KEY=your-usajobs-key-here

# Optional: Adzuna API credentials
# Get from: https://developer.adzuna.com/
ADZUNA_APP_ID=your-adzuna-app-id
ADZUNA_APP_KEY=your-adzuna-app-key

# Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
"""
    
    with open(".env", "w") as f:
        f.write(env_content)
    
    print("✅ Created sample .env file")
    print("   Please edit .env file and add your API keys")


def start_setup_wizard():
    """Start the setup wizard"""
    print("\n🚀 Starting setup wizard...")
    
    try:
        # Start the dashboard server in the background
        import subprocess
        import time
        
        # Start server
        process = subprocess.Popen([
            sys.executable, "-m", "V1.dashboard"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait a moment for server to start
        time.sleep(3)
        
        # Open browser to setup wizard
        setup_url = "http://localhost:8000/setup"
        print(f"🌐 Opening setup wizard at: {setup_url}")
        webbrowser.open(setup_url)
        
        print("\n✨ Setup wizard opened in your browser!")
        print("   Follow the steps to configure JobBot")
        print("   Press Ctrl+C to stop the server when done")
        
        # Wait for user to finish
        try:
            process.wait()
        except KeyboardInterrupt:
            print("\n👋 Setup wizard stopped")
            process.terminate()
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to start setup wizard: {e}")
        print("   You can start it manually with: python -m V1.dashboard")
        return False


def run_quick_test():
    """Run a quick test to verify installation"""
    print("\n🧪 Running quick test...")
    
    try:
        # Test imports
        from V1 import JobFinder, AsyncJobFinder, ApplicationTracker
        print("✅ Core modules imported successfully")
        
        # Test configuration
        from V1.config import ConfigManager
        config_manager = ConfigManager()
        print("✅ Configuration system working")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def show_next_steps():
    """Show next steps after setup"""
    print("\n🎯 JobBot Setup Complete!")
    print("=" * 50)
    
    print("\n📋 Next Steps:")
    print("1. Configure your API keys in the .env file")
    print("2. Run the setup wizard:")
    print("   python -m V1.dashboard")
    print("   Visit: http://localhost:8000/setup")
    print("\n3. Start your first job search:")
    print("   python main.py --concurrent")
    print("\n4. View the dashboard:")
    print("   Open: output/job_dashboard.html")
    
    print("\n📚 Useful Commands:")
    print("   python main.py --help                 # Show all options")
    print("   python main.py --concurrent           # Fast concurrent search")
    print("   python main.py --setup-config         # Create config file")
    print("   python main.py list-starred           # View starred jobs")
    
    print("\n🌐 Web Interface:")
    print("   python -m V1.dashboard               # Start web server")
    print("   http://localhost:8000/               # Main dashboard")
    print("   http://localhost:8000/setup          # Setup wizard")
    
    print("\n💡 Tips:")
    print("   - Use --concurrent for 3x faster searches")
    print("   - The setup wizard makes configuration easy")
    print("   - Mobile-responsive dashboard works on phones")
    print("   - Track applications from interest to offer")


def main():
    """Main setup function"""
    print("🎯 JobBot Setup & Installation")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        return 1
    
    # Install dependencies
    if not install_dependencies():
        return 1
    
    # Check/create .env file
    if not check_api_keys():
        create_sample_env()
    
    # Run quick test
    if not run_quick_test():
        print("\n⚠️  Some components may not work correctly")
        print("   Try installing dependencies manually")
    
    # Ask if user wants to run setup wizard
    print("\n❓ Would you like to run the setup wizard now? (y/n): ", end="")
    try:
        response = input().strip().lower()
        if response in ['y', 'yes']:
            start_setup_wizard()
    except KeyboardInterrupt:
        print("\n")
    
    # Show next steps
    show_next_steps()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())