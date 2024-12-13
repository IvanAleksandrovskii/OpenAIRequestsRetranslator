import asyncio
import time
from typing import List
import httpx
from asyncio import Lock

from logger import log
from config import settings


class UberClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.is_busy = False
        self.last_used = time.time()

    async def request(self, *args, **kwargs) -> httpx.Response:
        """
        Make an HTTP request using the client.

        :param args: Positional arguments for the request
        :param kwargs: Keyword arguments for the request
        :return: HTTP response
        """
        try:
            response = await self.client.request(*args, **kwargs)
            return response
        except httpx.RequestError as e:
            log.error(f"Request error: %s", e)
            raise
        # TODO: for now keep it here, cause in fact it's a time will client be marked as used for httpx async client
        finally:
            self.last_used = time.time()


class ClientManager:
    def __init__(self, client_timeout=settings.http_client.timeout,
                    max_keepalive_connections=settings.http_client.max_keepalive_connections):
        self.clients: List[UberClient] = []
        self.max_clients = max_keepalive_connections
        self.client_timeout = client_timeout
        self.limits = httpx.Limits(max_keepalive_connections=max_keepalive_connections,
                                    keepalive_expiry=client_timeout)
        self.lock = Lock()  # For thread-safety
        self.cleanup_task = None
        self.is_shutting_down = False

    async def start(self):
        """Initialize the cleanup task."""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self.periodic_cleanup())

    async def periodic_cleanup(self) -> None:
        """Periodically clean up inactive clients."""
        while not self.is_shutting_down:
            await asyncio.sleep(60)
            await self.cleanup_inactive_clients()

    async def cleanup_inactive_clients(self) -> None:
        """Remove inactive clients from the pool."""
        async with self.lock:
            current_time = time.time()
            self.clients = [client for client in self.clients
                            if client.is_busy or (current_time - client.last_used < self.client_timeout)]
            log.info(f"Cleanup completed. %s clients remaining.", len(self.clients))

    async def get_client(self) -> UberClient:
        """
        Get an available client from the pool. If none available and we haven't reached the limit, create a new one.

        :return: An available client
        """
        async with self.lock:
            current_time = time.time()
            # Check for available non-busy clients
            available_clients = [client for client in self.clients if not client.is_busy]
            log.info(f"Available clients: %s", len(available_clients))

            if available_clients:
                client = available_clients[0]
                # Mark the client as busy
                client.is_busy = True
                client.last_used = current_time
                return client

            # If no available clients and we haven't reached the limit, create a new one
            if len(self.clients) < self.max_clients:
                new_client = UberClient(httpx.AsyncClient(
                    timeout=self.client_timeout,
                    limits=self.limits
                ))
                # Mark the new client as busy
                new_client.is_busy = True
                new_client.last_used = current_time
                self.clients.append(new_client)
                return new_client

            # If we've reached the limit, wait for an available client
            log.warning("All clients busy. Waiting for an available client.")
            for _ in range(10):  # Retry 10 times in 5 seconds
                await asyncio.sleep(0.5)
                available_clients = [client for client in self.clients if not client.is_busy]
                if available_clients:
                    client = available_clients[0]
                    client.is_busy = True
                    client.last_used = current_time
                    return client

        raise Exception("Can't get a free client after 10 attempts in 5 seconds")

    async def release_client(self, client: UberClient):
        """Release a client, make it not busy anymore."""
        async with self.lock:
            if client in self.clients:
                client.is_busy = False

    async def dispose_all_clients(self) -> None:
        """Dispose all clients."""
        self.is_shutting_down = True
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        async with self.lock:
            for uber_client in self.clients:
                await uber_client.client.aclose()
            self.clients.clear()
        log.info("All clients disposed.")


# Global ClientManager instance
client_manager = ClientManager()
