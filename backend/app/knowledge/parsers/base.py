from abc import ABC, abstractmethod


class BaseDocumentParser(ABC):
    """Abstract base class for document content parsers."""

    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str | None = None) -> str:
        """Parse raw file bytes into normalized string content.

        Raises:
            ValueError: If file is empty, unsupported, or malformed.
        """
        pass
