from app.knowledge.model import KnowledgeSourceType
from app.knowledge.parsers.base import BaseDocumentParser
from app.knowledge.parsers.docx_parser import DOCXParser
from app.knowledge.parsers.pdf_parser import PDFParser
from app.knowledge.parsers.txt_parser import TXTParser
from app.knowledge.parsers.url_parser import URLParser


def get_parser_for_type(
    source_type: KnowledgeSourceType | str,
) -> BaseDocumentParser:
    """Return appropriate document parser for the given knowledge source type."""
    type_str = (
        source_type.value
        if isinstance(source_type, KnowledgeSourceType)
        else str(source_type)
    ).lower()

    if type_str in ("txt", "md"):
        return TXTParser()
    elif type_str in ("website", "html", "url"):
        return URLParser()
    elif type_str == "pdf":
        return PDFParser()
    elif type_str == "docx":
        return DOCXParser()
    else:
        raise ValueError(
            f"Unsupported document source type: {source_type}"
        )
