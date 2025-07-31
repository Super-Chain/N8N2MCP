#!/usr/bin/env python3
"""
Main entry point for N8N Agent Marketplace
Starts both the Flask app (port 5000) and MCP Router (port 6545)
"""

import os
import sys
import subprocess
import time
import signal
import threading

# Add the parent directory to Python path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from environment
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
MCP_HOST = os.getenv('MCP_HOST', '0.0.0.0')
MCP_PORT = int(os.getenv('MCP_PORT', 6545))

# Process handles
flask_process = None
mcp_process = None

def signal_handler(sig, frame):
    """Handle shutdown gracefully"""
    print("\n🛑 Shutting down servers...")
    
    if flask_process:
        flask_process.terminate()
        print("✅ Flask server stopped")
    
    if mcp_process:
        mcp_process.terminate()
        print("✅ MCP Router stopped")
    
    sys.exit(0)

def start_flask_app():
    """Start the Flask application"""
    print(f"🚀 Starting Flask app on http://{FLASK_HOST}:{FLASK_PORT}")
    
    global flask_process
    env = os.environ.copy()
    env['HOST'] = FLASK_HOST
    env['PORT'] = str(FLASK_PORT)
    env['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))
    
    flask_process = subprocess.Popen(
        [sys.executable, 'agent_marketplace/app.py'],
        env=env,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )

def start_mcp_router():
    """Start the MCP Router"""
    print(f"🚀 Starting MCP Router on http://{MCP_HOST}:{MCP_PORT}")
    
    global mcp_process
    # Change to mcp_router directory to ensure imports work
    mcp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp_router')
    
    env = os.environ.copy()
    env['HOST'] = MCP_HOST
    env['PORT'] = str(MCP_PORT)
    
    mcp_process = subprocess.Popen(
        [sys.executable, 'mcp_router.py'],
        cwd=mcp_dir,
        env=env
    )

def get_credential_docs_link(credential_name):
    """Returns the documentation link for a given credential."""
    docs_links = {
        "SUPABASE_URL": "https://supabase.com/docs/guides/getting-started/quickstarts/flask",
        "SUPABASE_KEY": "https://supabase.com/docs/guides/getting-started/quickstarts/flask",
        "SUPABASE_SERVICE_KEY": "https://supabase.com/docs/guides/getting-started/quickstarts/flask",
        "X_N8N_API_KEY": "https://docs.n8n.io/hosting/scaling/worker-nodes/#api-key",
        "N8N_BASE_URL": "https://docs.n8n.io/hosting/scaling/worker-nodes/#api-key",
    }
    return docs_links.get(credential_name, "No documentation link available.")

def check_environment():
    """Check if environment is properly configured"""
    print("🔍 Checking environment configuration...")
    
    required_vars = [
        'SUPABASE_URL',
        'SUPABASE_KEY',
        'SUPABASE_SERVICE_KEY',
        'X_N8N_API_KEY',
        'N8N_BASE_URL'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease provide the missing credentials:")
        for var in missing_vars:
            value = input(f"   - {var}: ")
            os.environ[var] = value
        print("\nCredentials have been set for this session.")
        print("To avoid this prompt in the future, please create a .env file with the following content:")
        for var in required_vars:
            print(f"{var}={os.getenv(var)}")
        print("\nFor more information on how to get these credentials, please refer to the documentation:")
        for var in missing_vars:
            print(f"   - {var}: {get_credential_docs_link(var)}")

    print("✅ Environment configuration OK")
    return True

def run_database_setup():
    """Run database setup if needed"""
    print("\n🔧 Checking database setup...")
    
    try:
        result = subprocess.run(
            [sys.executable, 'agent_marketplace/setup_supabase.py'],
            capture_output=True,
            text=True
        )
        
        if "Setup completed successfully" in result.stdout:
            print("✅ Database setup completed")
        elif "MANUAL SETUP REQUIRED" in result.stdout:
            print("⚠️  Database tables need to be created manually")
            print("   Run: python agent_marketplace/setup_supabase.py")
            print("   Follow the instructions to create tables in Supabase")
        else:
            print("✅ Database already configured")
            
    except Exception as e:
        print(f"⚠️  Could not verify database setup: {e}")

def main():
    """Main entry point"""
    print("=" * 60)
    print("🏗️  N8N Agent Marketplace - Starting Services")
    print("=" * 60)
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Run database setup check
    run_database_setup()
    
    print("\n🚀 Starting servers...")
    print(f"   Flask App: http://{FLASK_HOST}:{FLASK_PORT}")
    print(f"   MCP Router: http://{MCP_HOST}:{MCP_PORT}")
    print("\nPress Ctrl+C to stop all servers\n")
    
    # Start both servers
    try:
        # Start Flask app in a thread
        flask_thread = threading.Thread(target=start_flask_app)
        flask_thread.start()
        
        # Give Flask a moment to start
        time.sleep(2)
        
        # Start MCP Router in a thread
        mcp_thread = threading.Thread(target=start_mcp_router)
        mcp_thread.start()
        
        # Wait for processes
        if flask_process:
            flask_process.wait()
        if mcp_process:
            mcp_process.wait()
            
    except Exception as e:
        print(f"❌ Error starting servers: {e}")
        signal_handler(None, None)

if __name__ == "__main__":
    main()