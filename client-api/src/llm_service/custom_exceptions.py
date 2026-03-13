class LLMServiceException(Exception):
    """Base exception for LLM Service errors."""
    pass

class OrderBuildingException(LLMServiceException):
    """Exception raised when order building fails."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class OrderValidationException(LLMServiceException):
    """Exception raised when order validation fails."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class OrderCreationException(LLMServiceException):
    """Exception raised when order creation fails."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class OrderUpdateException(LLMServiceException):
    """Exception raised when order update fails."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class OrderRemovalException(LLMServiceException):
    """Exception raised when order removal fails."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class OrderNotFoundException(LLMServiceException):
    """Exception raised when an order is not found."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)



