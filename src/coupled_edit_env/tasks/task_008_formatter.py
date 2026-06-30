"""
Task 008: Document Formatter - Structural change with cascading effects

Scenario: A document formatting system where `parse_sections` was changed from
returning a flat list of sections to a tree structure (sections can contain
sub-sections). The renderer, table-of-contents generator, and search functionality
all assume flat list access and break in different ways.

Difficulty: Hard
Coupling type: Flat-to-hierarchical data structure change with multiple consumers
"""

from coupled_edit_env.types import TaskInstance


def create_task() -> TaskInstance:
    project_files = {
        "docs/parser.py": '''
from dataclasses import dataclass, field


@dataclass
class Section:
    title: str
    content: str
    level: int
    children: list = field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def flatten(self) -> list:
        """Recursively flatten this section and all descendants."""
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result


def parse_sections(raw_text: str) -> list[Section]:
    """
    MODIFIED: Now returns a tree of sections based on heading level.
    Previously returned a flat list like [Section("Intro", ..., 1), Section("Sub", ..., 2), ...].
    Now returns only top-level sections, with sub-sections nested in .children.

    Example: If input has H1, H2, H2, H1, H2 structure, returns:
    [Section(H1, children=[Section(H2), Section(H2)]), Section(H1, children=[Section(H2)])]
    """
    lines = raw_text.strip().split("\\n")
    all_sections = []
    current_section = None
    current_content_lines = []

    for line in lines:
        heading_level = 0
        if line.startswith("### "):
            heading_level = 3
            title = line[4:].strip()
        elif line.startswith("## "):
            heading_level = 2
            title = line[3:].strip()
        elif line.startswith("# "):
            heading_level = 1
            title = line[2:].strip()
        else:
            current_content_lines.append(line)
            continue

        if current_section is not None:
            current_section.content = "\\n".join(current_content_lines).strip()
            current_content_lines = []

        current_section = Section(title=title, content="", level=heading_level)
        all_sections.append(current_section)

    if current_section is not None:
        current_section.content = "\\n".join(current_content_lines).strip()

    if not all_sections:
        return []

    roots = []
    stack = []

    for section in all_sections:
        while stack and stack[-1].level >= section.level:
            stack.pop()

        if stack:
            stack[-1].children.append(section)
        else:
            roots.append(section)

        stack.append(section)

    return roots
''',
        "docs/renderer.py": '''
from docs.parser import parse_sections, Section


class HtmlRenderer:
    def render(self, raw_text: str) -> str:
        """Render document to HTML."""
        sections = parse_sections(raw_text)
        html_parts = ["<html><body>"]
        for section in sections:
            level = section.level
            html_parts.append(f"<h{level}>{section.title}</h{level}>")
            if section.content:
                html_parts.append(f"<p>{section.content}</p>")
        html_parts.append("</body></html>")
        return "\\n".join(html_parts)

    def render_titles_only(self, raw_text: str) -> list[str]:
        """Extract just the titles in document order."""
        sections = parse_sections(raw_text)
        return [s.title for s in sections]

    def word_count(self, raw_text: str) -> int:
        """Count total words across all sections."""
        sections = parse_sections(raw_text)
        total = 0
        for section in sections:
            total += len(section.content.split())
        return total


class TableOfContents:
    def generate(self, raw_text: str) -> list[dict]:
        """Generate a TOC with title, level, and content preview."""
        sections = parse_sections(raw_text)
        toc = []
        for section in sections:
            preview = section.content[:50] + "..." if len(section.content) > 50 else section.content
            toc.append({
                "title": section.title,
                "level": section.level,
                "preview": preview,
            })
        return toc

    def generate_indented(self, raw_text: str) -> str:
        """Generate an indented text TOC."""
        sections = parse_sections(raw_text)
        lines = []
        for section in sections:
            indent = "  " * (section.level - 1)
            lines.append(f"{indent}- {section.title}")
        return "\\n".join(lines)
''',
        "docs/search.py": '''
from docs.parser import parse_sections, Section


class DocumentSearch:
    def search_content(self, raw_text: str, query: str) -> list[dict]:
        """Find sections containing the query string."""
        sections = parse_sections(raw_text)
        results = []
        for i, section in enumerate(sections):
            if query.lower() in section.content.lower() or query.lower() in section.title.lower():
                results.append({
                    "index": i,
                    "title": section.title,
                    "level": section.level,
                    "snippet": section.content[:100],
                })
        return results

    def get_section_by_index(self, raw_text: str, index: int):
        """Get a section by its flat index."""
        sections = parse_sections(raw_text)
        if 0 <= index < len(sections):
            return sections[index]
        return None

    def count_sections(self, raw_text: str) -> dict[str, int]:
        """Count sections at each level."""
        sections = parse_sections(raw_text)
        counts = {}
        for section in sections:
            key = f"h{section.level}"
            counts[key] = counts.get(key, 0) + 1
        return counts
''',
    }

    modified_function = "parse_sections"

    test_suite = '''
import sys
sys.path.insert(0, ".")
from docs.parser import parse_sections, Section


SAMPLE_DOC = """# Introduction
Welcome to the guide.

## Getting Started
First steps here.

## Installation
How to install.

# Advanced Topics
For power users.

## Configuration
Config details.

### Environment Variables
Env var specifics.
"""


def test_parse_returns_tree():
    result = parse_sections(SAMPLE_DOC)
    assert len(result) == 2  # Two H1 sections
    assert result[0].title == "Introduction"
    assert result[0].level == 1
    assert len(result[0].children) == 2  # Getting Started, Installation


def test_nested_children():
    result = parse_sections(SAMPLE_DOC)
    advanced = result[1]
    assert advanced.title == "Advanced Topics"
    assert len(advanced.children) == 1
    config = advanced.children[0]
    assert config.title == "Configuration"
    assert len(config.children) == 1
    assert config.children[0].title == "Environment Variables"
'''

    hidden_tests = '''
import sys
sys.path.insert(0, ".")
from docs.parser import parse_sections, Section
from docs.renderer import HtmlRenderer, TableOfContents
from docs.search import DocumentSearch


SAMPLE_DOC = """# Introduction
Welcome to the guide.

## Getting Started
First steps here.

## Installation
How to install things properly.

# Advanced Topics
For power users only.

## Configuration
Config details go here.

### Environment Variables
Set your env vars carefully.
"""


def test_render_html_all_sections():
    renderer = HtmlRenderer()
    html = renderer.render(SAMPLE_DOC)
    assert "<h1>Introduction</h1>" in html
    assert "<h2>Getting Started</h2>" in html
    assert "<h2>Installation</h2>" in html
    assert "<h1>Advanced Topics</h1>" in html
    assert "<h2>Configuration</h2>" in html
    assert "<h3>Environment Variables</h3>" in html


def test_render_titles_all():
    renderer = HtmlRenderer()
    titles = renderer.render_titles_only(SAMPLE_DOC)
    assert "Introduction" in titles
    assert "Getting Started" in titles
    assert "Installation" in titles
    assert "Advanced Topics" in titles
    assert "Configuration" in titles
    assert "Environment Variables" in titles
    assert len(titles) == 6


def test_word_count_total():
    renderer = HtmlRenderer()
    count = renderer.word_count(SAMPLE_DOC)
    assert count > 20


def test_toc_all_sections():
    toc_gen = TableOfContents()
    toc = toc_gen.generate(SAMPLE_DOC)
    assert len(toc) == 6
    titles = [entry["title"] for entry in toc]
    assert "Introduction" in titles
    assert "Environment Variables" in titles


def test_toc_indented():
    toc_gen = TableOfContents()
    result = toc_gen.generate_indented(SAMPLE_DOC)
    lines = result.split("\\n")
    assert any("- Introduction" in l and not l.startswith(" ") for l in lines)
    assert any("  - Getting Started" in l for l in lines)
    assert any("    - Environment Variables" in l for l in lines)


def test_search_finds_nested():
    search = DocumentSearch()
    results = search.search_content(SAMPLE_DOC, "env var")
    assert len(results) >= 1
    assert any("Environment" in r["title"] for r in results)


def test_search_finds_top_level():
    search = DocumentSearch()
    results = search.search_content(SAMPLE_DOC, "power users")
    assert len(results) >= 1
    assert any("Advanced" in r["title"] for r in results)


def test_count_sections_all_levels():
    search = DocumentSearch()
    counts = search.count_sections(SAMPLE_DOC)
    assert counts.get("h1", 0) == 2
    assert counts.get("h2", 0) == 3
    assert counts.get("h3", 0) == 1


def test_get_section_by_index():
    search = DocumentSearch()
    section = search.get_section_by_index(SAMPLE_DOC, 0)
    assert section is not None
    assert section.title == "Introduction"
    section3 = search.get_section_by_index(SAMPLE_DOC, 3)
    assert section3 is not None
    assert section3.title == "Advanced Topics"
'''

    ground_truth_repairs = {
        "docs/renderer.py": "Must recursively traverse children. render/render_titles_only/word_count must flatten the tree or recurse into children.",
        "docs/search.py": "Must flatten the tree structure to search/count/index all sections including nested ones.",
    }

    return TaskInstance(
        task_id="task_008_formatter",
        instruction=(
            "The function `parse_sections` in docs/parser.py was intentionally changed. "
            "It now returns a TREE structure: only top-level (H1) sections in the list, with "
            "sub-sections nested in each section's .children attribute. Previously it returned "
            "a flat list of ALL sections regardless of level. "
            "This change is correct and must NOT be reverted. "
            "Fix all code in docs/renderer.py and docs/search.py that iterates over sections "
            "assuming a flat list. They must now recursively traverse the tree to access all sections."
        ),
        project_files=project_files,
        modified_function=modified_function,
        test_suite=test_suite,
        hidden_tests=hidden_tests,
        ground_truth_repairs=ground_truth_repairs,
        difficulty="hard",
        revert_indicators=[
            "return all_sections",
            "sections.append(current_section)",
        ],
        modified_is_async=False,
    )
