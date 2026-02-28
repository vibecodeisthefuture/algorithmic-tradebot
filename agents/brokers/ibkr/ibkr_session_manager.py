"""
IBKR Session Manager - Background Session Keepalive

IBKR Client Portal Gateway sessions timeout after 10-15 minutes of inactivity.
This module provides background session management via periodic /tickle requests.

Usage:
    manager = IBKRSessionManager()
    manager.start()  # Start background keepalive
    # ... do trading operations ...
    manager.stop()   # Graceful shutdown

Documentation: https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/
"""

import threading
import time
import logging
from datetime import datetime
from typing import Optional

from ibkr_connection import IBKRConnection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IBKRSessionManager:
    """
    Maintains IBKR Client Portal Gateway session via periodic /tickle requests.

    Sessions timeout after 10-15 minutes of inactivity. This manager sends
    tickle requests every 3 minutes (configurable) to keep the session alive.

    Attributes:
        connection: IBKRConnection instance
        interval: Seconds between tickle requests (default: 180)
        running: Whether the manager is currently active
    """

    DEFAULT_INTERVAL = 180  # 3 minutes

    def __init__(
        self,
        connection: Optional[IBKRConnection] = None,
        interval: int = DEFAULT_INTERVAL
    ):
        """
        Initialize session manager

        Args:
            connection: IBKRConnection instance (creates new if None)
            interval: Seconds between tickle requests (default: 180)
        """
        self.connection = connection or IBKRConnection()
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_tickle: Optional[datetime] = None
        self._tickle_count = 0
        self._failure_count = 0

    @property
    def running(self) -> bool:
        """Check if session manager is running"""
        return self._running

    @property
    def last_tickle(self) -> Optional[datetime]:
        """Get timestamp of last successful tickle"""
        return self._last_tickle

    def start(self) -> bool:
        """
        Start background session keepalive thread

        Returns:
            True if started successfully, False otherwise
        """
        if self._running:
            logger.warning("Session manager already running")
            return True

        # Verify connection is authenticated
        if not self.connection.is_authenticated():
            logger.error("Cannot start - session not authenticated")
            print("\n  Cannot start session manager - not authenticated")
            print("  Please login via browser at https://localhost:5000")
            return False

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._tickle_loop, daemon=True)
        self._thread.start()

        logger.info(f"Session manager started (interval: {self.interval}s)")
        print(f"\n  Session manager started")
        print(f"  Tickle interval: {self.interval} seconds")
        print(f"  Press Ctrl+C to stop")

        return True

    def stop(self):
        """Stop background session keepalive thread"""
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        logger.info(f"Session manager stopped (total tickles: {self._tickle_count})")
        print(f"\n  Session manager stopped")
        print(f"  Total tickles: {self._tickle_count}")
        print(f"  Failures: {self._failure_count}")

    def _tickle_loop(self):
        """Background loop that sends tickle requests at regular intervals"""
        while not self._stop_event.is_set():
            try:
                success = self.connection.tickle_session()

                if success:
                    self._last_tickle = datetime.now()
                    self._tickle_count += 1
                    logger.debug(f"Session tickled ({self._tickle_count})")
                else:
                    self._failure_count += 1
                    logger.warning(f"Tickle failed (count: {self._failure_count})")

                    # Check if session is still authenticated
                    if not self.connection.is_authenticated():
                        logger.error("Session no longer authenticated!")
                        print("\n  WARNING: Session expired - please re-authenticate")

            except Exception as e:
                self._failure_count += 1
                logger.error(f"Tickle error: {e}")

            # Wait for next interval (with early exit on stop)
            self._stop_event.wait(self.interval)

    def get_status(self) -> dict:
        """
        Get current session manager status

        Returns:
            Dictionary with status information
        """
        return {
            'running': self._running,
            'interval_seconds': self.interval,
            'tickle_count': self._tickle_count,
            'failure_count': self._failure_count,
            'last_tickle': self._last_tickle.isoformat() if self._last_tickle else None,
            'authenticated': self.connection.is_authenticated() if self._running else None
        }

    def print_status(self):
        """Print current session manager status"""
        status = self.get_status()

        print(f"\n{'-'*60}")
        print(" IBKR SESSION MANAGER STATUS")
        print(f"{'-'*60}")
        print(f"  Running: {status['running']}")
        print(f"  Interval: {status['interval_seconds']} seconds")
        print(f"  Tickle Count: {status['tickle_count']}")
        print(f"  Failures: {status['failure_count']}")
        if status['last_tickle']:
            print(f"  Last Tickle: {status['last_tickle']}")
        if status['authenticated'] is not None:
            print(f"  Authenticated: {status['authenticated']}")
        print(f"{'-'*60}\n")


def main():
    """
    Run session manager as standalone script
    """
    print("\n" + "="*60)
    print(" IBKR SESSION MANAGER")
    print("="*60)
    print("\nThis script keeps your IBKR session alive by sending")
    print("periodic /tickle requests to the gateway.")
    print("\nPress Ctrl+C to stop.\n")

    # Initialize connection
    conn = IBKRConnection()

    # Check authentication
    if not conn.is_authenticated():
        print("  Not authenticated. Please:")
        print("  1. Start gateway: bin\\run.bat root\\conf.yaml")
        print("  2. Login at: https://localhost:5000")
        print("  3. Complete two-factor authentication")
        print("\nThen run this script again.\n")
        return

    # Start session manager
    manager = IBKRSessionManager(connection=conn, interval=180)

    try:
        manager.start()

        # Keep running until Ctrl+C
        while manager.running:
            time.sleep(60)  # Check every minute
            manager.print_status()

    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        manager.stop()

    print("\nSession manager stopped.\n")


if __name__ == "__main__":
    main()