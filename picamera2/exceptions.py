class RequeueException(Exception):
    def __init__(self):
        super("This method needs to be run again")
