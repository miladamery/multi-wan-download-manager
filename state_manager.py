"""
State Persistence Manager for Multi-WAN Download Manager

Handles saving and loading application state including:
- Download queue
- Active downloads with progress
- Completed downloads history
- User settings
"""
import json
import os
import shutil
from datetime import datetime
from typing import Dict, Any

import config


class StateManager:
    """Manages application state persistence."""

    def __init__(self):
        self.state_file = config.STATE_FILE
        self.backup_dir = config.BACKUP_DIR
        self._ensure_directories()

    def _ensure_directories(self):
        """Create state directory and backup directory if they don't exist."""
        os.makedirs(config.STATE_DIR, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)

    def save_state(self, state: Dict[str, Any]) -> bool:
        """
        Save current application state to JSON file.

        Args:
            state: Dictionary containing all state data

        Returns:
            True if save successful, False otherwise
        """
        try:
            # Add timestamp
            state['timestamp'] = datetime.now().isoformat()

            # Create backup before overwriting
            if os.path.exists(self.state_file):
                self._create_backup()

            # Write state to file
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            print(f"Error saving state: {e}")
            return False

    def load_state(self) -> Dict[str, Any]:
        """
        Load application state from JSON file.

        Returns:
            Dictionary containing saved state, or empty dict if file doesn't exist
        """
        try:
            if not os.path.exists(self.state_file):
                return {}

            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)

            return state
        except Exception as e:
            print(f"Error loading state: {e}")
            # Try to restore from backup
            return self._restore_from_backup()

    def _create_backup(self):
        """Create a timestamped backup of the current state file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(self.backup_dir, f"state_{timestamp}.json")
        shutil.copy2(self.state_file, backup_file)

        # Keep only last 10 backups
        self._cleanup_old_backups()

    def _restore_from_backup(self) -> Dict[str, Any]:
        """Try to restore from the most recent backup."""
        try:
            backups = sorted(
                [f for f in os.listdir(self.backup_dir) if f.startswith("state_")],
                reverse=True
            )

            if backups:
                latest_backup = os.path.join(self.backup_dir, backups[0])
                with open(latest_backup, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass

        return {}

    def _cleanup_old_backups(self):
        """Keep only the 10 most recent backups."""
        try:
            backups = sorted(
                [f for f in os.listdir(self.backup_dir) if f.startswith("state_")],
                reverse=True
            )

            # Remove old backups (keep last 10)
            for old_backup in backups[10:]:
                os.remove(os.path.join(self.backup_dir, old_backup))
        except Exception:
            pass

    def clear_state(self):
        """Clear all saved state (for testing or manual reset)."""
        try:
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
        except Exception:
            pass
