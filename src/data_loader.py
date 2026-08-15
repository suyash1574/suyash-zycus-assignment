"""
Dataset Loader and Historical Ticket Filter
Loads tickets (500) and accounts (50) from JSON / Excel files and manages 90-day lookup indices.
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from src.schemas import TicketRecord, AccountRecord

logger = logging.getLogger("data_loader")


class DataLoader:
    def __init__(self, data_dir: str = "data/"):
        self.data_dir = data_dir
        self.tickets: List[Dict[str, Any]] = []
        self.accounts: List[Dict[str, Any]] = []
        self.account_map: Dict[str, Dict[str, Any]] = {}
        self.ticket_map: Dict[str, Dict[str, Any]] = {}
        self.account_tickets_map: Dict[str, List[Dict[str, Any]]] = {}
        self.load_data()

    def load_data(self) -> None:
        """
        Loads tickets and accounts from JSON files in data_dir (or fallback dataset/starter-repo/data).
        """
        tickets_path = os.path.join(self.data_dir, "tickets.json")
        accounts_path = os.path.join(self.data_dir, "accounts.json")

        # Fallback to dataset/starter-repo/data if not found in data_dir
        if not os.path.exists(tickets_path):
            tickets_path = os.path.join("dataset", "starter-repo", "data", "tickets.json")
        if not os.path.exists(accounts_path):
            accounts_path = os.path.join("dataset", "starter-repo", "data", "accounts.json")

        if not os.path.exists(tickets_path) or not os.path.exists(accounts_path):
            logger.error(f"Dataset files not found at {tickets_path} or {accounts_path}")
            return

        with open(tickets_path, "r", encoding="utf-8") as f:
            self.tickets = json.load(f)

        with open(accounts_path, "r", encoding="utf-8") as f:
            self.accounts = json.load(f)

        self._build_indices()
        logger.info(f"DataLoader successfully initialized with {len(self.tickets)} tickets and {len(self.accounts)} accounts.")

    def _build_indices(self) -> None:
        """
        Builds in-memory O(1) hash maps for accounts, tickets, and account-to-ticket linkages.
        """
        self.account_map = {acc["account_id"]: acc for acc in self.accounts}
        self.ticket_map = {tkt["ticket_id"]: tkt for tkt in self.tickets}
        self.account_tickets_map = {}

        for tkt in self.tickets:
            acc_id = tkt.get("account_id")
            if acc_id:
                if acc_id not in self.account_tickets_map:
                    self.account_tickets_map[acc_id] = []
                self.account_tickets_map[acc_id].append(tkt)

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves account summary record by ID.
        """
        return self.account_map.get(account_id)

    def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves single ticket record by ID.
        """
        return self.ticket_map.get(ticket_id)

    def get_all_accounts(self) -> List[Dict[str, Any]]:
        """
        Returns list of all account summaries.
        """
        return self.accounts

    def get_all_tickets(self) -> List[Dict[str, Any]]:
        """
        Returns list of all tickets.
        """
        return self.tickets

    def get_account_tickets_90d(self, account_id: str, reference_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Retrieves tickets for an account from the last 90 days.
        If reference_date is not specified, calculates relative to the latest ticket timestamp in the dataset
        to ensure consistency with synthetic datasets.
        """
        all_acc_tickets = self.account_tickets_map.get(account_id, [])
        if not all_acc_tickets:
            return []

        # Determine reference anchor date: use latest ticket timestamp in the entire dataset if not provided
        if reference_date is None:
            max_dt = None
            for tkt in self.tickets:
                try:
                    dt_str = tkt.get("created_at", "")
                    if dt_str:
                        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        if max_dt is None or dt > max_dt:
                            max_dt = dt
                except Exception:
                    continue
            reference_date = max_dt or datetime.now(timezone.utc)

        cutoff = reference_date - timedelta(days=90)
        recent_tickets = []

        for tkt in all_acc_tickets:
            try:
                dt_str = tkt.get("created_at", "")
                if dt_str:
                    tkt_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    if tkt_dt >= cutoff:
                        recent_tickets.append(tkt)
                else:
                    recent_tickets.append(tkt)
            except Exception:
                recent_tickets.append(tkt)

        # Sort tickets newest first
        return sorted(recent_tickets, key=lambda x: x.get("created_at", ""), reverse=True)


data_loader = DataLoader()
