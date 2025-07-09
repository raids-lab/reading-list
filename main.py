import argparse
import pathlib
import subprocess
import sys
from typing import Dict, List, Optional, TextIO

import bibtexparser
from pylatexenc.latex2text import LatexNodes2Text

# Define a mapping from shortened book titles to their full names.
# This is used to identify the series of a literature reference based on its booktitle.
BOOKTITLE_PATTERN = {
    "ASPLOS": "Architectural Support for Programming Languages and Operating Systems",
    "FAST": "File and Storage Technologies",
    "OSDI": "Operating Systems Design and Implementation",
    "SOSP": "Symposium on Operating Systems Principles",
    "USENIX ATC": [
        "Usenix Annual Technical Conference",
        "USENIX Annual Technical Conference",
    ],
    "EuroSys": [
        "European Conference on Computer Systems",
        "EuroSys Conference",
    ],
    "PLDI": "Programming Language Design and Implementation",
    "MICRO": "International Symposium on Microarchitecture",
    "ICCAD": "International Conference on Computer-Aided Design",
    "VEE": "International Conference on Virtual Execution Environments",
    "MobiSys": "International Conference on Mobile Systems, Applications, and Services",
    "CGO": "International Symposium on Code Generation and Optimization",
}


class LiteratureRef:
    """
    A class to represent a literature reference.

    Attributes:
    - date: publication year
    - series: conference / journal / book title
    - title: literature title
    - authors: list of authors
    - link: paper url
    - [optional] code repository url
    """

    def __init__(
        self,
        date: int,
        series: str,
        title: str,
        authors: list[str],
        link: str,
        code: Optional[str] = None,
    ):
        self.date = date
        self.series = series
        self.title = title
        self.authors = authors
        self.link = link
        self.code = code

    def __lt__(self, other: "LiteratureRef") -> bool:
        """
        Less than comparison based on date and series.
        """
        if self.date != other.date:
            return self.date > other.date
        if self.series != other.series:
            return self.series < other.series
        return self.title < other.title

    def __repr__(self):
        return (
            f"LiteratureRef(date={self.date}, series='{self.series}', "
            f"title='{self.title}', authors={self.authors}, link='{self.link}', "
            f"code='{self.code}')"
        )

    def __str__(self):
        return (
            f"[{self.series} {self.date}] {self.title} by {', '.join(self.authors)} " +
            (f"(Link: {self.link}, Code: {self.code})" if self.code else f"(Link: {self.link})")
        )

    def into_format(self, fmt: str) -> str:
        if fmt == "text":
            return str(self)
        elif fmt == "html":
            return f"<strong>[{self.series} {self.date}] <em>{self.title}</em></strong><br>" + \
                f"<ul><li>Authors: {', '.join(self.authors)}</li>" + \
                f"<li><a href='{self.link}'>Link</a>" + \
                (f", <a href='{self.code}'>Code</a>" if self.code else "") + \
                "</ul>"
        else:
            raise ValueError(f"Unsupported format: {fmt}.")

    @classmethod
    def parse(cls, bib: TextIO) -> List["LiteratureRef"]:
        """
        Parses a BibTeX entry and returns a LiteratureRef object.
        """
        bib_data = bibtexparser.load(bib)
        references = []
        for entry in bib_data.entries:
            try:
                ref = cls(
                    date=int(entry.get("year", 0)),
                    series=LiteratureRef.__series_of(entry),
                    title=LatexNodes2Text().latex_to_text(entry["title"]),
                    authors=LiteratureRef.__authors_of(entry),
                    link=entry["url"],
                    code=entry.get("code", None),
                )
                references.append(ref)
            except KeyError as e:
                raise ValueError(
                    f"Missing required field in entry: {e}. Entry: {entry}")
        return references

    @classmethod
    def __authors_of(cls, entry: Dict[str, str]) -> List[str]:
        """
        Extracts authors from a BibTeX entry.
        """

        def reorder_name(name: str) -> str:
            """
            Reorders the name from 'Last, First' to 'First Last'.
            """
            parts = name.split(", ")
            if len(parts) == 2:
                return f"{parts[1]} {parts[0]}"
            return name

        authors = entry.get("author", "").split(" and ")
        return [reorder_name(LatexNodes2Text().latex_to_text(author.strip())) for author in authors]

    @classmethod
    def __series_of(cls, entry: Dict[str, str]) -> str:
        """
        Extracts the series from a BibTeX entry.
        """
        if "booktitle" in entry:
            booktitle = entry["booktitle"]
            for key, value in BOOKTITLE_PATTERN.items():
                if isinstance(value, list):
                    for v in value:
                        if v in booktitle:
                            return key
                elif isinstance(value, str):
                    if value in booktitle:
                        return key
                else:
                    raise ValueError(f"Invalid booktitle pattern: {value}.")
            raise ValueError(
                f"Unknown booktitle: {booktitle}. Please add it to `BOOKTITLE_PATTERN`."
            )
        if "journal" in entry:
            raise NotImplementedError("Journal entries are not supported yet.")
        if "archiveprefix" in entry:
            archive_prefix = entry["archiveprefix"]
            if archive_prefix == "arXiv":
                return "arXiv"
            raise ValueError(f"Unknown archivePrefix: {archive_prefix}.")
        raise ValueError(f"Unknown entry type: {entry}")


def output_references(
    references: List[LiteratureRef],
    output_stream: TextIO,
    title: str = "Reading List",
    fmt: str = "text",
) -> None:
    """
    Outputs the list of references in the specified format.
    """
    if fmt == "text":
        for ref in references:
            output_stream.write(ref.into_format("text") + "\n")
    elif fmt == "html":
        output_stream.write("<!DOCTYPE html>\n")
        output_stream.write(f"<html><head><title>{title}</title></head>\n")
        output_stream.write("<body>\n")
        output_stream.write(f"<h2>{title}</h2>\n")
        output_stream.write("<ul>\n")
        # Write each reference as a list item in HTML format
        # Using the into_format method to convert each reference to HTML
        for ref in references:
            output_stream.write(f"<li>{ref.into_format('html')}</li>\n")
        output_stream.write("</ul>\n</body>\n</html>\n")
    else:
        raise ValueError(f"Unsupported format: {fmt}.")


def main():
    parser = argparse.ArgumentParser(
        description="Reading List Generator via BibTeX parser")
    parser.add_argument(
        "-f",
        "--bib-file",
        type=str,
        required=True,
        metavar="<FILE>",
        help="Path to the BibTeX file containing literature references",
    )
    parser.add_argument(
        "-F",
        "--format",
        type=str,
        choices=["text", "html"],
        default="text",
        help="Output format for the literature references (default: text)",
    )
    parser.add_argument(
        "-O",
        "--output-file",
        type=str,
        metavar="<FILE>",
        default="-",
        help="Output file to save the formatted references (default: stdout)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the output file after writing (only works if output file is not stdout)",
    )
    args = parser.parse_args()

    if args.open and args.output_file == "-":
        parser.error("Cannot open stdout. Please specify an output file.")

    with open(args.bib_file, "r", encoding="utf-8") as bib_file:
        references = LiteratureRef.parse(bib_file)

    # sort and deduplicate references
    references.sort()
    references = list(dict.fromkeys(references))

    # Convert kebab case to title case for the output title
    title = pathlib.Path(args.bib_file).stem.replace("-", " ").title()

    if args.output_file == "-":
        output_references(references, sys.stdout, title=title, fmt=args.format)
    else:
        with open(args.output_file, "w", encoding="utf-8") as output_stream:
            output_references(references, output_stream,
                              title=title, fmt=args.format)
            if args.open:
                subprocess.run(["xdg-open", args.output_file])


if __name__ == "__main__":
    main()
