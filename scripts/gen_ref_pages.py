#!/usr/bin/env python3
"""Generate the code reference pages and navigation."""

import logging
from pathlib import Path

import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()

src = Path(Path(__file__).parent.parent)

LOG: logging.Logger = logging.getLogger("gen_ref_pages")
LOG.addHandler(logging.NullHandler())

logging.basicConfig(format="%(name)s - %(levelname)s - %(message)s", level=logging.INFO)


for path in sorted(Path(src / "glitchygames").rglob("*.py")):
    LOG.info(f"Processing {path}")
    module_path: Path = path.relative_to(src).with_suffix("")
    LOG.info(f"Module path: {module_path}")

    doc_path: Path = Path(src) / ".." / "docs" / path.with_suffix(".md")
    doc_path = doc_path.relative_to(src).with_suffix("")
    LOG.info(f"Doc path: {doc_path}")

    # TODO: This is a hack to fix the path for the docs.  It should be fixed in the future.
    full_doc_path: Path = Path("") / doc_path  # noqa: PTH201
    LOG.info(f"Full doc path: {full_doc_path}")

    parts = tuple(module_path.parts)

    if parts[-1] == "__init__":
        parts: tuple[str, ...] = parts[:-1]
        doc_path = doc_path.with_name("index.md")
        full_doc_path = full_doc_path.with_name("index.md")

    elif parts[-1] == "__main__":
        continue

    nav[parts] = doc_path.as_posix()

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        ident = ".".join(parts)
        fd.write(f"::: {ident}")

    mkdocs_gen_files.set_edit_path(full_doc_path, path)

with mkdocs_gen_files.open("SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
