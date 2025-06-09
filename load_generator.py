#!/usr/bin/env python3
"""
Simplified Selenium Grid Load Generator
This script creates and manages browser sessions with the Selenium Grid to generate load.
"""

import time
import os
import random
import threading
import logging
import traceback
import sys
import requests
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("load-generator")

# Configuration
HUB_URL = "http://selenium-grid.example.com:30080/wd/hub"
STATUS_URL = "http://selenium-grid.example.com:30080/status"
DIRECT_NODE = None  # Set to node URL if you want to target a specific node

# Test websites
SITES = [
    "https://www.google.com",
    "https://www.wikipedia.org",
    "https://www.github.com"
]

# Session settings
MAX_CONCURRENT_SESSIONS = 3
SESSION_LIFETIME_SECONDS = 180  # 3 minutes
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2
CONNECTION_TIMEOUT = 15
PAGE_LOAD_TIMEOUT = 10
SCRIPT_TIMEOUT = 5

# Runtime state
active_sessions = []
active_sessions_lock = threading.Lock()
should_continue = True

def get_grid_status():
    """Check Grid status and available nodes"""
    try:
        response = requests.get(STATUS_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            ready = data.get('value', {}).get('ready', False)
            nodes = data.get('value', {}).get('nodes', [])
            
            # Count available slots
            available_slots = 0
            for node in nodes:
                slots = node.get('slots', [])
                available_slots += sum(1 for slot in slots if slot.get('session') is None)
            
            return {
                'ready': ready,
                'node_count': len(nodes),
                'available_slots': available_slots,
                'raw_data': data
            }
        else:
            logger.error(f"Failed to get grid status: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error checking grid status: {e}")
        return None

def create_chrome_options():
    """Create Chrome options with appropriate capabilities"""
    options = Options()
    
    # Basic Chrome arguments
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Set browser name to "chrome" to match the node
    options.set_capability("browserName", "chrome")
    options.set_capability("platformName", "linux")
    
    # Set shorter timeouts to prevent hangs
    options.set_capability("timeouts", {
        "implicit": 0,
        "pageLoad": PAGE_LOAD_TIMEOUT * 1000,  # milliseconds
        "script": SCRIPT_TIMEOUT * 1000
    })
    
    return options

def create_session_with_retry():
    """Create a browser session with retries"""
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            logger.info(f"Attempt {attempt}/{RETRY_ATTEMPTS} to create a session")
            driver = create_session()
            if driver:
                return driver
        except Exception as e:
            logger.warning(f"Session creation attempt {attempt} failed: {e}")
            if attempt < RETRY_ATTEMPTS:
                delay = RETRY_DELAY * attempt
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
    
    logger.error("All session creation attempts failed")
    return None

def create_session():
    """Create a Selenium browser session"""
    try:
        # Check grid status
        grid_status = get_grid_status()
        if not grid_status or not grid_status['ready']:
            logger.warning(f"Grid not ready: {grid_status}")
            return None
        
        if grid_status['available_slots'] < 1:
            logger.warning("No available slots in the grid")
            return None
        
        logger.info(f"Creating session (available slots: {grid_status['available_slots']})")
        
        # Configure Chrome options
        chrome_options = create_chrome_options()
        
        # Set up timeouts in the WebDriver
        from selenium.webdriver.remote.remote_connection import RemoteConnection
        
        # Create the WebDriver
        start_time = time.time()
        # Set the timeout directly on the WebDriver instance
        driver.set_page_load_timeout(CONNECTION_TIMEOUT)
        driver.set_script_timeout(CONNECTION_TIMEOUT)
        endpoint = DIRECT_NODE if DIRECT_NODE else HUB_URL
        driver = webdriver.Remote(
            command_executor=endpoint,
            options=chrome_options
        )
        
        creation_time = time.time() - start_time
        logger.info(f"Session created successfully in {creation_time:.2f} seconds (ID: {driver.session_id})")
        
        # Set page load timeout
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        driver.set_script_timeout(SCRIPT_TIMEOUT)
        
        return driver
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        logger.debug(traceback.format_exc())
        return None

def browse_sites(driver, max_actions=3):
    """Perform browsing actions with the given driver"""
    actions_completed = 0
    start_time = time.time()
    
    try:
        while actions_completed < max_actions and (time.time() - start_time) < SESSION_LIFETIME_SECONDS:
            site = random.choice(SITES)
            try:
                logger.info(f"Navigating to {site}")
                driver.get(site)
                
                # Find elements to interact with
                elements = driver.find_elements(By.TAG_NAME, "a")
                if elements:
                    logger.info(f"Found {len(elements)} link elements")
                
                # Simple JavaScript execution to generate CPU load
                driver.execute_script("return document.title;")
                
                actions_completed += 1
                time.sleep(random.uniform(1, 3))
            except TimeoutException:
                logger.warning(f"Timeout loading {site}")
            except Exception as e:
                logger.error(f"Error during browsing: {e}")
                break
    except Exception as e:
        logger.error(f"Error in browse_sites: {e}")
    
    return actions_completed

def session_worker(session_id):
    """Worker function for each session thread"""
    try:
        driver = create_session_with_retry()
        if not driver:
            logger.error(f"Worker {session_id}: Failed to create session")
            return
        
        # Add to active sessions
        with active_sessions_lock:
            session_info = {
                "id": session_id,
                "driver": driver,
                "created_at": time.time()
            }
            active_sessions.append(session_info)
            logger.info(f"Worker {session_id}: Added session to active sessions (total: {len(active_sessions)})")
        
        # Perform browsing actions
        try:
            actions = browse_sites(driver)
            logger.info(f"Worker {session_id}: Completed {actions} browsing actions")
        except Exception as e:
            logger.error(f"Worker {session_id}: Error during browsing: {e}")
        
        # Clean up session
        try:
            logger.info(f"Worker {session_id}: Closing session")
            driver.quit()
        except Exception as e:
            logger.error(f"Worker {session_id}: Error closing session: {e}")
        
        # Remove from active sessions
        with active_sessions_lock:
            active_sessions[:] = [s for s in active_sessions if s["id"] != session_id]
            logger.info(f"Worker {session_id}: Removed session (remaining: {len(active_sessions)})")
    
    except Exception as e:
        logger.error(f"Worker {session_id}: Unexpected error: {e}")
        logger.debug(traceback.format_exc())

def session_manager():
    """Manage browser sessions, creating new ones up to the maximum"""
    session_counter = 0
    
    while should_continue:
        try:
            # Check current session count
            with active_sessions_lock:
                current_count = len(active_sessions)
            
            # Create new sessions if needed
            if current_count < MAX_CONCURRENT_SESSIONS:
                # Check grid status first
                grid_status = get_grid_status()
                if grid_status and grid_status['ready'] and grid_status['available_slots'] > 0:
                    session_counter += 1
                    session_id = f"session-{session_counter}"
                    
                    logger.info(f"Starting worker for {session_id} (current sessions: {current_count})")
                    worker_thread = threading.Thread(
                        target=session_worker,
                        args=(session_id,),
                        name=f"worker-{session_id}"
                    )
                    worker_thread.daemon = True
                    worker_thread.start()
                else:
                    logger.warning("No available slots or grid not ready")
                    time.sleep(5)
            else:
                logger.info(f"At maximum sessions ({current_count}), waiting...")
                time.sleep(5)
            
            # Check for expired sessions
            current_time = time.time()
            with active_sessions_lock:
                for session in list(active_sessions):
                    if current_time - session["created_at"] > SESSION_LIFETIME_SECONDS:
                        logger.info(f"Session {session['id']} expired, cleaning up")
                        try:
                            session["driver"].quit()
                        except Exception as e:
                            logger.error(f"Error closing expired session: {e}")
                        active_sessions.remove(session)
            
            # Brief pause between checks
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Error in session manager: {e}")
            logger.debug(traceback.format_exc())
            time.sleep(5)

def status_reporter():
    """Report status periodically"""
    while should_continue:
        try:
            with active_sessions_lock:
                session_count = len(active_sessions)
                session_ids = [s["id"] for s in active_sessions]
            
            grid_status = get_grid_status()
            if grid_status:
                logger.info(
                    f"Status: {session_count} active sessions, "
                    f"Grid has {grid_status['node_count']} nodes with "
                    f"{grid_status['available_slots']} available slots"
                )
                if session_count > 0:
                    logger.info(f"Active sessions: {', '.join(session_ids)}")
            else:
                logger.warning(f"Status: {session_count} active sessions, Grid status unknown")
            
            time.sleep(15)
        except Exception as e:
            logger.error(f"Error in status reporter: {e}")
            time.sleep(15)

def shutdown_handler():
    """Handle graceful shutdown"""
    global should_continue
    should_continue = False
    
    logger.info("Shutting down, closing all sessions...")
    with active_sessions_lock:
        for session in active_sessions:
            try:
                logger.info(f"Closing session {session['id']}")
                session["driver"].quit()
            except Exception as e:
                logger.error(f"Error closing session during shutdown: {e}")
    
    logger.info("All sessions closed")

def main():
    """Main entry point"""
    global should_continue
    
    try:
        logger.info("Starting Selenium Grid load generator")
        logger.info(f"Hub URL: {HUB_URL}")
        logger.info(f"Max concurrent sessions: {MAX_CONCURRENT_SESSIONS}")
        logger.info(f"Session lifetime: {SESSION_LIFETIME_SECONDS} seconds")
        
        # Check initial grid status
        initial_status = get_grid_status()
        if initial_status:
            logger.info(
                f"Grid status: Ready={initial_status['ready']}, "
                f"Nodes={initial_status['node_count']}, "
                f"Available slots={initial_status['available_slots']}"
            )
        else:
            logger.warning("Could not get initial grid status")
        
        # Start session manager thread
        manager_thread = threading.Thread(
            target=session_manager,
            name="session-manager"
        )
        manager_thread.daemon = True
        manager_thread.start()
        
        # Start status reporter thread
        reporter_thread = threading.Thread(
            target=status_reporter,
            name="status-reporter"
        )
        reporter_thread.daemon = True
        reporter_thread.start()
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            shutdown_handler()
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        logger.debug(traceback.format_exc())
        shutdown_handler()
        sys.exit(1)

if __name__ == "__main__":
    main()

