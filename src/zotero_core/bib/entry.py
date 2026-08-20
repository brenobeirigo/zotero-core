"""One parsed BibTeX entry -> one :class:`Work`.

The field table is the union of what the two importers mapped: the Web API
side contributed `language`, `repository` and `archiveID`; the desktop side
contributed `place`, `series`, `university`, `thesisType`, `institution`,
`reportNumber`, `websiteTitle`, `accessDate` and the en-dash page fix.
"""

from __future__ import annotations

from ..identity import format_citation_key
from .creators import clean, first_creator_match, parse_creators
from .models import Work
from .types import check_required, resolve_item_type


def entry_to_work(entry: dict, stream: str = "", *, strict_types: bool = False) -> Work:
    item_type, reason = resolve_item_type(entry, strict=strict_types)
    citation_key = clean(entry.get("ID"))
    title = clean(entry.get("title"))
    year = clean(entry.get("year")) or clean(entry.get("date"))
    check_required(item_type, citation_key, title, year)

    fields: dict[str, str] = {
        "title": title,
        "date": year,
        "DOI": clean(entry.get("doi")),
        "url": clean(entry.get("url")),
        "volume": clean(entry.get("volume")),
        "pages": clean(entry.get("pages")).replace("--", "-"),
        "publisher": clean(entry.get("publisher")),
        "place": clean(entry.get("address")),
        "series": clean(entry.get("series")),
        "language": clean(entry.get("langid")) or clean(entry.get("language")),
        "extra": format_citation_key(citation_key),
    }

    if item_type == "journalArticle":
        fields["publicationTitle"] = clean(entry.get("journal")) or clean(
            entry.get("journaltitle")
        )
        # `number` is the issue here and the report number below, so it is
        # resolved per item type rather than in the shared block.
        fields["issue"] = clean(entry.get("number"))
    elif item_type == "bookSection":
        fields["bookTitle"] = clean(entry.get("booktitle"))
    elif item_type == "conferencePaper":
        fields["proceedingsTitle"] = clean(entry.get("booktitle")) or clean(
            entry.get("journal")
        )
    elif item_type == "thesis":
        fields["university"] = clean(entry.get("school"))
        fields["thesisType"] = _thesis_type(entry)
    elif item_type == "report":
        fields["institution"] = clean(entry.get("institution"))
        fields["reportNumber"] = clean(entry.get("number"))
    elif item_type == "webpage":
        fields["websiteTitle"] = (
            clean(entry.get("organization"))
            or clean(entry.get("publisher"))
            or clean(entry.get("howpublished"))
        )
        fields["accessDate"] = clean(entry.get("urldate"))
    elif item_type == "preprint":
        fields["repository"] = clean(entry.get("archiveprefix"))
        fields["archiveID"] = clean(entry.get("eprint"))

    return Work(
        citation_key=citation_key,
        stream=stream,
        item_type=item_type,
        item_type_reason=reason,
        title=title,
        year=year,
        doi=clean(entry.get("doi")),
        match_creator=first_creator_match(entry.get("author")),
        fields={key: value for key, value in fields.items() if value},
        creators=parse_creators(entry.get("author")),
    )


def _thesis_type(entry: dict) -> str:
    entry_type = (entry.get("ENTRYTYPE") or "").casefold()
    if entry_type == "phdthesis":
        return "PhD thesis"
    if entry_type == "mastersthesis":
        return "Master's thesis"
    if entry_type == "bachelorthesis":
        return "Bachelor's thesis"
    return clean(entry.get("type")) or "Thesis"
