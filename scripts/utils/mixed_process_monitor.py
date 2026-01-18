"""
Mixed process monitor for tracking Mixed processes and managing timers.
"""
import time
from typing import Optional


class MixedProcessMonitor:
    """
    Monitors Mixed processes and tracks when they've been active for the timeout period.
    """
    
    def __init__(self, timeout_seconds: int = 30):
        """
        Initialize the Mixed process monitor.
        
        Args:
            timeout_seconds: Number of seconds before triggering VLM check (default: 30)
        """
        self.timeout_seconds = timeout_seconds
        self.current_mixed_process: Optional[str] = None
        self.timer_start_time: Optional[float] = None
        self.last_checked_process: Optional[str] = None
    
    def update_process(self, process_name: str, classification: str) -> None:
        """
        Update the monitor with the current process and its classification.
        
        Args:
            process_name: Name of the current process
            classification: Classification of the process ('work', 'entertainment', 'mixed', 'unknown')
        """
        # If process changed, reset timer
        if process_name != self.last_checked_process:
            self.last_checked_process = process_name
            
            # If it's a Mixed or Unknown process, start/reset timer
            if classification in ['mixed', 'unknown']:
                if self.current_mixed_process != process_name:
                    # Different Mixed/Unknown process, reset timer
                    self.current_mixed_process = process_name
                    self.timer_start_time = time.time()
                    print(f"[MixedProcessMonitor] Started timer for {classification.capitalize()} process: {process_name}")
                # Same Mixed/Unknown process, timer continues running
            else:
                # Not a Mixed/Unknown process, clear tracking
                if self.current_mixed_process is not None:
                    print(f"[MixedProcessMonitor] Process changed from {classification.capitalize()} ({self.current_mixed_process}) to {classification} ({process_name})")
                self.current_mixed_process = None
                self.timer_start_time = None
    
    def should_check(self) -> bool:
        """
        Check if we should trigger VLM analysis (timer exceeded for current Mixed process).
        
        Returns:
            True if timer has exceeded timeout for current Mixed process, False otherwise
        """
        if self.current_mixed_process is None or self.timer_start_time is None:
            return False
        
        elapsed_time = time.time() - self.timer_start_time
        if elapsed_time >= self.timeout_seconds:
            print(f"[MixedProcessMonitor] Timer exceeded ({elapsed_time:.1f}s) for {self.current_mixed_process}")
            return True
        
        return False
    
    def reset(self) -> None:
        """Reset the monitor (clear current process and timer)."""
        self.current_mixed_process = None
        self.timer_start_time = None
        self.last_checked_process = None
    
    def get_elapsed_time(self) -> Optional[float]:
        """
        Get elapsed time for current Mixed process.
        
        Returns:
            Elapsed time in seconds, or None if no Mixed process is being tracked
        """
        if self.current_mixed_process is None or self.timer_start_time is None:
            return None
        return time.time() - self.timer_start_time

