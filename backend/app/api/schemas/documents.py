from pydantic import BaseModel


class DocumentItem(BaseModel):
    source: str
    indexed: bool = True

