
class Metadata():
    def __init__(self, metadata={}):
        self.__dict__ = metadata.copy()

    def __repr__(self):
        return f"<Metadata: {self.__dict__}>"

    def make_dict(self):
        return self.__dict__.copy()
