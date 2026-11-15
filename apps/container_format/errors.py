class ContainerError(Exception):
    """Base class for invalid or unsafe PixelVault containers."""


class ContainerFormatError(ContainerError):
    """The binary structure does not match the PixelVault specification."""


class ContainerLimitError(ContainerError):
    """The container exceeds a configured safety limit."""
