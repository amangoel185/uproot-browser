"""
Display tools for TTrees.
"""

from __future__ import annotations

import dataclasses
import functools
from pathlib import Path
from typing import Any, Dict

import uproot
from rich.console import Console
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

console = Console()

__all__ = ("make_tree", "process_item", "print_tree", "UprootItem", "console")


def __dir__() -> tuple[str, ...]:
    return __all__


@dataclasses.dataclass
class UprootItem:
    path: str
    item: Any

    @property
    def is_dir(self) -> bool:
        return isinstance(self.item, (uproot.reading.ReadOnlyDirectory, uproot.TTree))

    def meta(self) -> dict[str, Any]:
        return process_item(self.item)

    def label(self) -> Text:
        return process_item(self.item)["label"]  # type: ignore[no-any-return]

    @property
    def children(self) -> list[UprootItem]:
        if not self.is_dir:
            return []
        items = {key.split(";")[0] for key in self.item.keys()}
        return [
            UprootItem(f"{self.path}/{key}", self.item[key]) for key in sorted(items)
        ]


def make_tree(node: UprootItem, *, tree: Tree | None = None) -> Tree:
    """
    Given an object, build a rich.tree.Tree output.
    """

    if tree is None:
        tree = Tree(**node.meta())
    else:
        tree = tree.add(**node.meta())

    for child in node.children:
        make_tree(child, tree=tree)

    return tree


@functools.singledispatch
def process_item(uproot_object: Any) -> Dict[str, Any]:
    """
    Given an unknown object, return a rich.tree.Tree output. Specialize for known objects.
    """
    name = getattr(uproot_object, "name", "<unnamed>")
    classname = getattr(uproot_object, "classname", uproot_object.__class__.__name__)
    label = Text.assemble(
        "❓ ",
        (f"{name} ", "bold"),
        (classname, "italic"),
    )
    return {"label": label}


@process_item.register
def _process_item_tfile(
    uproot_object: uproot.reading.ReadOnlyDirectory,
) -> Dict[str, Any]:
    """
    Given an TFile, return a rich.tree.Tree output.
    """
    path = Path(uproot_object.file_path)

    if uproot_object.path:
        # path is to a TDirectory on tree
        path_name = escape(uproot_object.path[0])
        link_text = f"file://{path}:/{path_name}"
    else:
        # path is the top of the tree: the file
        path_name = escape(path.name)
        link_text = f"file://{path}"

    label = Text.from_markup(f":file_folder: [link {link_text}]{path_name}")

    result = {
        "label": label,
        "guide_style": "bold bright_blue",
    }
    return result


@process_item.register
def _process_item_ttree(uproot_object: uproot.TTree) -> Dict[str, Any]:
    """
    Given an tree, return a rich.tree.Tree output.
    """
    label = Text.assemble(
        "🌴 ",
        (f"{uproot_object.name} ", "bold"),
        f"({uproot_object.num_entries:g})",
    )

    result = {
        "label": label,
        "guide_style": "bold bright_green",
    }
    return result


@process_item.register
def _process_item_tbranch(uproot_object: uproot.TBranch) -> Dict[str, Any]:
    """
    Given an branch, return a rich.tree.Tree output.
    """

    jagged = isinstance(
        uproot_object.interpretation, uproot.interpretation.jagged.AsJagged
    )
    icon = "🍃 " if jagged else "🍁 "

    label = Text.assemble(
        icon,
        (f"{uproot_object.name} ", "bold"),
        (f"{uproot_object.typename}", "italic"),
    )
    result = {"label": label}
    return result


@process_item.register
def _process_item_th(uproot_object: uproot.behaviors.TH1.Histogram) -> Dict[str, Any]:
    """
    Given an histogram, return a rich.tree.Tree output.
    """
    icon = "📊 " if uproot_object.kind == "COUNT" else "📈 "
    sizes = " × ".join(f"{len(ax)}" for ax in uproot_object.axes)

    label = Text.assemble(
        icon,
        (f"{uproot_object.name} ", "bold"),
        (f"{uproot_object.classname} ", "italic"),
        f"({sizes})",
    )
    result = {"label": label}
    return result


# pylint: disable-next=redefined-outer-name
def print_tree(entry: str, *, console: Console = console) -> None:
    """
    Prints a tree given a specification string. Currently, that must be a
    single filename. Colons are not allowed currently in the filename.
    """

    upfile = uproot.open(entry)
    tree = make_tree(UprootItem("/", upfile))
    console.print(tree)
