from typing import List, Optional, Union
from pydantic import BaseModel, Field


class OPDS2Metadata(BaseModel):
    title: str
    identifier: Optional[str] = None
    author: Optional[Union[str, List[str]]] = None


class OPDS2Link(BaseModel):
    href: str
    type: Optional[str] = None
    rel: Optional[str] = None


class OPDS2Publication(BaseModel):
    metadata: OPDS2Metadata
    links: List[OPDS2Link]


class PublicationFeedNoValidation(BaseModel):
    metadata: Optional[dict] = None
    publications: List[dict]
    links: Optional[List[dict]] = Field(default_factory=list)
