import os

class Message():
    def __init__(self, st=False, msg=''):
        self.status = st
        self.message = msg
        self.result = {}

class MessagePrinter():
    def __init__(self, file, max_size_MB=10):
        self.file = file
        self.max_size_MB = max_size_MB

    def print2File(self, msg):
        fsize_MB = round(os.path.getsize(self.file)/float(1024*1024), 2)
        if (fsize_MB > self.max_size_MB):
            with open(self.file, "w") as f:
                f.write('')
        with open(self.file, "a") as f:
            f.write("%s" % (str(msg)))

