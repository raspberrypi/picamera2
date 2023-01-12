
class Metadata():
    def __init__(self, metadata: dict = {}) -> None:
        self.__dict__ = metadata.copy()

    def __repr__(self) -> str:
        return f"<Metadata: {self.__dict__}>"

    def make_dict(self) -> dict:
        return self.__dict__.copy()
