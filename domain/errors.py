class DomainError(Exception):
    pass


class BackendConfigError(DomainError):
    pass


class BackendNotFoundError(DomainError):
    pass
