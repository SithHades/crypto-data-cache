class DataDownloaderError(Exception):
    """Base exception for data downloading errors."""

    pass


class DownloadFailedError(DataDownloaderError):
    """Exception raised when a download attempt fails (e.g., 404 Not Found)."""

    def __init__(
        self, url: str, status_code: int | None = None, message: str = "Download failed"
    ):
        self.url = url
        self.status_code = status_code
        self.message = f"{message}. URL: {url}" + (
            f", Status Code: {status_code}" if status_code else ""
        )
        super().__init__(self.message)


class DatabaseError(Exception):
    """Base exception for database related errors."""

    pass
