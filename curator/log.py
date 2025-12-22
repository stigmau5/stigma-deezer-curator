from pathlib import Path


class CuratedLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries = self._load()

    def _load(self) -> set[str]:
        if not self.path.exists():
            return set()

        with self.path.open("r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}

    def has(self, link: str) -> bool:
        return link in self._entries

    def append(self, links: list[str]) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            for link in links:
                f.write(link + "\n")
                self._entries.add(link)
