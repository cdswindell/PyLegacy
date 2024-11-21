from time import time


class ExpiringSet:
    def __init__(self, max_age_seconds=1.0):
        assert max_age_seconds > 0
        self.age = max_age_seconds
        self.container = {}

    def __repr__(self) -> str:
        return f"{self.container}"

    def __len__(self) -> int:
        return len(self.container)

    def __contains__(self, value) -> bool:
        return self.contains(value)

    def contains(self, value):
        if value not in self.container:
            return False
        if time() - self.container[value] > self.age:
            del self.container[value]
            return False
        return True

    def add(self, value):
        self.container[value] = time()

    def clear(self):
        self.container.clear()

    def discard(self, value):
        if value in self.container:
            del self.container[value]

    def remove(self, value):
        if value not in self.container:
            raise KeyError(f"{value} not found in set")
        self.discard(value)
