class BusinessException(Exception):
    """业务异常"""

    def __init__(self, code: int, message: str, error: str = None):
        self.code = code
        self.message = message
        self.error = error
        super().__init__(message)
